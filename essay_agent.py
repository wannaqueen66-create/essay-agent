import json
import logging
import os
import smtplib
import sqlite3
import time
import hashlib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import arxiv
import pandas as pd
import requests
import yaml
from dotenv import load_dotenv
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("essay_agent")

DB_PATH = "papers.db"
REQUEST_HEADERS = {"User-Agent": "essay-agent/1.0"}

SCORING_VERSION_V1 = "v1_single"
SCORING_VERSION_V2 = "v2_multi"

RELATION_KEY = "与建筑/体育空间/疗愈环境研究相关性"
LEGACY_RELATION_KEY = "与建筑/体育空间研究相关性"

EXTRACTION_FIELDS = [
    "中文摘要",
    "研究主题",
    "空间/场景类型",
    "研究场景",
    "自变量",
    "因变量",
    "行为指标",
    "生理/感知指标",
    "研究方法",
    "数据/样本",
    "主要结论",
]

SPATIAL_FLAG_KEYS = [
    "是否有明确空间环境要素",
    "研究对象是否为人类用户",
    "实验是否在真实或虚拟空间中进行",
]


def normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    doi = value.strip()
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi = doi.replace("doi.org/", "")
    return doi.lower()


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_env() -> tuple[OpenAI, dict]:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("没有读取到 OPENAI_API_KEY,请检查 .env 文件。")

    base_url = os.getenv("OPENAI_BASE_URL", "").strip()

    fallback_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    runtime = {
        "openai_model": fallback_model,
        "scoring_mode": (os.getenv("SCORING_MODE", "multi").strip().lower() or "multi"),
        "researcher_model": os.getenv("RESEARCHER_MODEL", fallback_model),
        "skeptic_model": os.getenv("SKEPTIC_MODEL", fallback_model),
        "judge_model": os.getenv("JUDGE_MODEL", fallback_model),
        "agent_retries": int(os.getenv("AGENT_RETRIES", "3")),
        "agent_retry_delay": int(os.getenv("AGENT_RETRY_DELAY", "3")),
        "legacy_rescore_enabled": parse_bool(os.getenv("LEGACY_RESCORE_ENABLED"), True),
        "legacy_rescore_per_run": int(os.getenv("LEGACY_RESCORE_PER_RUN", "30")),
        "days_back": int(os.getenv("DAYS_BACK", "2")),
        "max_results_per_query": int(os.getenv("MAX_RESULTS_PER_QUERY", "30")),
        "min_relevance_score": int(os.getenv("MIN_RELEVANCE_SCORE", "60")),
        "force_refresh": parse_bool(os.getenv("FORCE_REFRESH"), False),
        "low_score_refresh_days": int(os.getenv("LOW_SCORE_REFRESH_DAYS", "3")),
        "low_score_refresh_below": int(os.getenv("LOW_SCORE_REFRESH_BELOW", "60")),
        "email_enabled": parse_bool(os.getenv("EMAIL_ENABLED"), False),
        "email_smtp_host": os.getenv("EMAIL_SMTP_HOST", "smtp-relay.brevo.com"),
        "email_smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
        "email_username": os.getenv("EMAIL_USERNAME", ""),
        "email_password": os.getenv("EMAIL_PASSWORD", ""),
        "email_from": os.getenv("EMAIL_FROM", ""),
        "email_to": os.getenv("EMAIL_TO", ""),
        "email_use_tls": parse_bool(os.getenv("EMAIL_USE_TLS"), True),
        "report_top_n": int(os.getenv("REPORT_TOP_N", "10")),
        "email_top_n": int(os.getenv("EMAIL_TOP_N", "5")),
        "pending_pool_days": int(os.getenv("PENDING_POOL_DAYS", "7")),
        "empty_report_email": parse_bool(os.getenv("EMPTY_REPORT_EMAIL"), False),
    }

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    return OpenAI(**client_kwargs), runtime


def ensure_output_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def cleanup_old_outputs(path: str, keep_days: int = 30) -> int:
    if keep_days <= 0 or not os.path.isdir(path):
        return 0
    cutoff = time.time() - keep_days * 86400
    removed = 0
    for name in os.listdir(path):
        if not name.startswith("essay_daily_"):
            continue
        file_path = os.path.join(path, name)
        if not os.path.isfile(file_path):
            continue
        try:
            if os.path.getmtime(file_path) < cutoff:
                os.remove(file_path)
                removed += 1
        except Exception:
            logger.exception("清理旧输出文件失败：%s", file_path)
    return removed


def human_summary_for_empty_report(stats: dict | None) -> str:
    if not stats:
        return "今天没有符合条件的新论文进入最终收录。"
    too_old = stats.get("too_old", 0)
    below = stats.get("below_min_relevance", 0)
    reported = stats.get("already_reported", 0)
    if below > 0 and too_old > 0:
        return "今天有抓到论文，但大多要么发布时间较早，要么相关性不够高，所以没有新的最终收录。"
    if below > 0:
        return "今天有抓到论文，但整体相关性偏低，所以没有新的最终收录。"
    if reported > 0:
        return "今天有符合条件的论文，但已在之前的报告中展示过，所以没有新增收录。"
    return "今天没有符合条件的新论文进入最终收录。"


def truncate_text(text: str, max_chars: int) -> str:
    if not text:
        return ""
    return text[:max_chars]


def contains_excluded_keyword(text: str, exclude_keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(k.lower() in text_lower for k in exclude_keywords)


def contains_must_have_keyword(text: str, must_have_keywords: list[str]) -> bool:
    if not must_have_keywords:
        return True
    text_lower = text.lower()
    return any(k.lower() in text_lower for k in must_have_keywords)


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS papers (
            url TEXT PRIMARY KEY,
            doi TEXT,
            source TEXT,
            title TEXT,
            english_abstract TEXT,
            chinese_summary TEXT,
            published_date TEXT,
            query_name TEXT,
            authors TEXT,
            primary_category TEXT,
            categories TEXT,
            analysis_json TEXT,
            related_score INTEGER,
            analysis_status TEXT,
            meets_threshold INTEGER,
            eligible_for_pending INTEGER,
            first_seen_at TEXT,
            last_seen_at TEXT,
            displayed_at TEXT,
            display_count INTEGER,
            reported_at TEXT,
            report_count INTEGER,
            content_hash TEXT,
            created_at TEXT,
            updated_at TEXT,
            analyzed_at TEXT,
            scoring_version TEXT,
            skeptic_flags TEXT,
            judge_rationale TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi) WHERE doi != ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_displayed ON papers(displayed_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_reported ON papers(reported_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_pending ON papers(displayed_at, meets_threshold, eligible_for_pending, analysis_status)")
    conn.commit()
    return conn


def ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        conn.commit()


def migrate_db(conn: sqlite3.Connection):
    ensure_column(conn, "papers", "doi", "doi TEXT")
    ensure_column(conn, "papers", "source", "source TEXT")
    ensure_column(conn, "papers", "english_abstract", "english_abstract TEXT")
    ensure_column(conn, "papers", "chinese_summary", "chinese_summary TEXT")
    ensure_column(conn, "papers", "analysis_status", "analysis_status TEXT")
    ensure_column(conn, "papers", "meets_threshold", "meets_threshold INTEGER")
    ensure_column(conn, "papers", "eligible_for_pending", "eligible_for_pending INTEGER")
    ensure_column(conn, "papers", "first_seen_at", "first_seen_at TEXT")
    ensure_column(conn, "papers", "last_seen_at", "last_seen_at TEXT")
    ensure_column(conn, "papers", "displayed_at", "displayed_at TEXT")
    ensure_column(conn, "papers", "display_count", "display_count INTEGER DEFAULT 0")
    ensure_column(conn, "papers", "reported_at", "reported_at TEXT")
    ensure_column(conn, "papers", "report_count", "report_count INTEGER DEFAULT 0")
    ensure_column(conn, "papers", "content_hash", "content_hash TEXT")
    ensure_column(conn, "papers", "analyzed_at", "analyzed_at TEXT")
    ensure_column(conn, "papers", "scoring_version", "scoring_version TEXT")
    ensure_column(conn, "papers", "skeptic_flags", "skeptic_flags TEXT")
    ensure_column(conn, "papers", "judge_rationale", "judge_rationale TEXT")

    # 旧行回填 v1_single（仅对已有 analysis_json 的记录）
    conn.execute(
        "UPDATE papers SET scoring_version = ? "
        "WHERE scoring_version IS NULL AND analysis_json IS NOT NULL AND analysis_json != ''",
        (SCORING_VERSION_V1,),
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_papers_scoring_version ON papers(scoring_version)"
    )
    conn.commit()


def get_paper_record(conn: sqlite3.Connection, url: str, doi: str = "") -> dict | None:
    cols = (
        "url, doi, analysis_json, content_hash, reported_at, displayed_at, "
        "updated_at, last_seen_at, analyzed_at, scoring_version"
    )
    keys = [
        "url", "doi", "analysis_json", "content_hash", "reported_at",
        "displayed_at", "updated_at", "last_seen_at", "analyzed_at", "scoring_version",
    ]
    if doi:
        row = conn.execute(
            f"SELECT {cols} FROM papers WHERE doi = ? LIMIT 1", (doi,),
        ).fetchone()
        if row:
            return {k: row[i] for i, k in enumerate(keys)}
    row = conn.execute(
        f"SELECT {cols} FROM papers WHERE url = ? LIMIT 1", (url,),
    ).fetchone()
    if row:
        return {k: row[i] for i, k in enumerate(keys)}
    return None


def get_cached_analysis(conn: sqlite3.Connection, url: str, doi: str = "") -> dict | None:
    record = get_paper_record(conn, url, doi)
    if not record or not record.get("analysis_json"):
        return None
    try:
        return json.loads(record["analysis_json"])
    except Exception:
        return None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def should_refresh_cached_analysis(record: dict | None, runtime: dict) -> bool:
    if not record:
        return False
    if runtime.get("force_refresh"):
        return True
    analysis_json = record.get("analysis_json")
    if not analysis_json:
        return True
    try:
        analysis = json.loads(analysis_json)
    except Exception:
        return True
    score = analysis.get("相关性分数")
    if score is None:
        return True
    try:
        score = int(score)
    except Exception:
        return True
    threshold = int(runtime.get("low_score_refresh_below", runtime.get("min_relevance_score", 60)))
    refresh_days = int(runtime.get("low_score_refresh_days", 3))
    if score >= threshold:
        return False
    updated_at = _parse_iso_datetime(record.get("analyzed_at")) or _parse_iso_datetime(record.get("updated_at")) or _parse_iso_datetime(record.get("last_seen_at"))
    if updated_at is None:
        return True
    return (datetime.now(timezone.utc) - updated_at) >= timedelta(days=refresh_days)


def was_reported(conn: sqlite3.Connection, url: str, doi: str = "") -> bool:
    if doi:
        row = conn.execute(
            "SELECT reported_at FROM papers WHERE doi = ? AND reported_at IS NOT NULL LIMIT 1", (doi,)
        ).fetchone()
        if row:
            return True
    row = conn.execute(
        "SELECT reported_at FROM papers WHERE url = ?", (url,)
    ).fetchone()
    return bool(row and row[0])


def was_displayed(conn: sqlite3.Connection, url: str, doi: str = "") -> bool:
    if doi:
        row = conn.execute(
            "SELECT displayed_at FROM papers WHERE doi = ? AND displayed_at IS NOT NULL LIMIT 1", (doi,)
        ).fetchone()
        if row:
            return True
    row = conn.execute(
        "SELECT displayed_at FROM papers WHERE url = ?", (url,)
    ).fetchone()
    return bool(row and row[0])


def _batch_update(conn: sqlite3.Connection, sql: str, keys: list[str]):
    if not keys:
        return
    now = datetime.now().isoformat(timespec="seconds")
    placeholders = ",".join("?" * len(keys))
    conn.execute(sql.format(placeholders=placeholders), [now, now] + keys)


def mark_reported(conn: sqlite3.Connection, urls: list[str], dois: list[str]):
    if not urls and not dois:
        return
    _batch_update(conn, "UPDATE papers SET reported_at=?, report_count=COALESCE(report_count,0)+1, updated_at=? WHERE url IN ({placeholders})", urls)
    clean_dois = [d for d in dois if d]
    _batch_update(conn, "UPDATE papers SET reported_at=?, report_count=COALESCE(report_count,0)+1, updated_at=? WHERE doi IN ({placeholders})", clean_dois)
    conn.commit()


def mark_displayed(conn: sqlite3.Connection, urls: list[str], dois: list[str]):
    if not urls and not dois:
        return
    _batch_update(conn, "UPDATE papers SET displayed_at=?, display_count=COALESCE(display_count,0)+1, updated_at=? WHERE url IN ({placeholders})", urls)
    clean_dois = [d for d in dois if d]
    _batch_update(conn, "UPDATE papers SET displayed_at=?, display_count=COALESCE(display_count,0)+1, updated_at=? WHERE doi IN ({placeholders})", clean_dois)
    conn.commit()


def select_legacy_rescore_candidates(conn: sqlite3.Connection, limit: int) -> list[dict]:
    """按优先级挑选待重评分的 legacy 论文：
    A. meets_threshold=1 AND displayed_at IS NULL (pending pool, 假阳性风险最高)
    B. meets_threshold=1 AND displayed_at 在最近 14 天内
    C. 其余
    """
    if limit <= 0:
        return []
    recent_cut = (datetime.now() - timedelta(days=14)).isoformat(timespec="seconds")
    rows = conn.execute(
        """
        SELECT url, doi, title, english_abstract, related_score, scoring_version,
               CASE
                   WHEN COALESCE(meets_threshold,0)=1 AND displayed_at IS NULL THEN 0
                   WHEN COALESCE(meets_threshold,0)=1 AND displayed_at >= ? THEN 1
                   ELSE 2
               END AS priority
        FROM papers
        WHERE (scoring_version IS NULL OR scoring_version != ?)
          AND english_abstract IS NOT NULL AND english_abstract != ''
          AND analysis_status = 'success'
        ORDER BY priority ASC, related_score DESC, last_seen_at DESC
        LIMIT ?
        """,
        (recent_cut, SCORING_VERSION_V2, limit),
    ).fetchall()
    return [
        {
            "url": r[0],
            "doi": r[1] or "",
            "title": r[2] or "",
            "english_abstract": r[3] or "",
            "old_score": r[4] or 0,
            "old_version": r[5] or SCORING_VERSION_V1,
            "priority": r[6],
        }
        for r in rows
    ]


def rescore_legacy_batch(
    conn: sqlite3.Connection,
    client: OpenAI,
    runtime: dict,
    limit: int,
    max_chars_per_paper: int,
) -> dict:
    """按优先级对 limit 篇 legacy 论文重跑多 agent 评分并原地更新。"""
    candidates = select_legacy_rescore_candidates(conn, limit)
    result = {"picked": len(candidates), "upgraded": 0, "downgraded": 0, "unchanged": 0, "failed": 0}
    if not candidates:
        return result

    min_relevance = int(runtime.get("min_relevance_score", 55))

    for cand in candidates:
        title = cand["title"]
        abstract = truncate_text(cand["english_abstract"], max_chars_per_paper)
        try:
            analysis = analyze_paper_multi_agent(client, runtime, title, abstract)
        except Exception:
            logger.exception("legacy rescore 失败：%s", cand["url"])
            result["failed"] += 1
            continue

        new_score = int(analysis.get("相关性分数", 0) or 0)
        old_score = int(cand["old_score"])
        meets_threshold = 1 if new_score >= min_relevance else 0
        eligible = 1 if (analysis.get("分析状态") == "success" and meets_threshold) else 0
        scoring_version = analysis.get("__scoring_version") or SCORING_VERSION_V2
        skeptic_payload = analysis.get("__skeptic")
        skeptic_flags_str = (
            json.dumps(skeptic_payload, ensure_ascii=False) if isinstance(skeptic_payload, dict) else None
        )
        judge_payload = analysis.get("__judge") or {}
        judge_rationale_str = (
            str(judge_payload.get("评分理由", "")) if isinstance(judge_payload, dict) else ""
        )
        now_iso = datetime.now().isoformat(timespec="seconds")

        conn.execute(
            """
            UPDATE papers
            SET analysis_json=?,
                related_score=?,
                analysis_status=?,
                meets_threshold=?,
                eligible_for_pending=?,
                scoring_version=?,
                skeptic_flags=?,
                judge_rationale=?,
                chinese_summary=COALESCE(NULLIF(?, ''), chinese_summary),
                analyzed_at=?,
                updated_at=?
            WHERE url=?
            """,
            (
                json.dumps(analysis, ensure_ascii=False),
                new_score,
                analysis.get("分析状态", "unknown"),
                meets_threshold,
                eligible,
                scoring_version,
                skeptic_flags_str,
                judge_rationale_str,
                analysis.get("中文摘要", ""),
                now_iso,
                now_iso,
                cand["url"],
            ),
        )

        if new_score > old_score:
            result["upgraded"] += 1
        elif new_score < old_score:
            result["downgraded"] += 1
        else:
            result["unchanged"] += 1

        logger.info(
            "[legacy rescore] %s -> %s | %d -> %d | %s",
            cand["old_version"], scoring_version, old_score, new_score,
            (title or "")[:80],
        )

    conn.commit()
    return result


def load_pending_pool(conn: sqlite3.Connection, days: int, limit: int) -> list[dict]:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        """
        SELECT doi, source, query_name, published_date, title, url, authors, primary_category, categories,
               english_abstract, chinese_summary, analysis_json, related_score, scoring_version
        FROM papers
        WHERE displayed_at IS NULL
          AND published_date >= ?
          AND COALESCE(meets_threshold, 0) = 1
          AND COALESCE(eligible_for_pending, 0) = 1
          AND analysis_status = 'success'
        ORDER BY related_score DESC, published_date DESC
        LIMIT ?
        """,
        (cutoff, limit),
    ).fetchall()

    if not rows:
        return []

    items = []
    for row in rows:
        analysis = {}
        try:
            analysis = json.loads(row[11])
        except Exception:
            pass
        items.append(
            {
                "doi": row[0],
                "source": row[1],
                "query_name": row[2],
                "published_date": row[3],
                "title": row[4],
                "url": row[5],
                "authors": row[6],
                "primary_category": row[7],
                "categories": row[8],
                "english_abstract": row[9],
                "中文摘要": row[10],
                "研究主题": analysis.get("研究主题", ""),
                "空间/场景类型": analysis.get("空间/场景类型", ""),
                "研究场景": analysis.get("研究场景", ""),
                "自变量": analysis.get("自变量", ""),
                "因变量": analysis.get("因变量", ""),
                "行为指标": analysis.get("行为指标", ""),
                "生理/感知指标": analysis.get("生理/感知指标", ""),
                "研究方法": analysis.get("研究方法", ""),
                "数据/样本": analysis.get("数据/样本", ""),
                "主要结论": analysis.get("主要结论", ""),
                "与建筑/体育空间/疗愈环境研究相关性": analysis.get("与建筑/体育空间/疗愈环境研究相关性", ""),
                "相关性分数": row[12],
                "可借鉴启发": analysis.get("可借鉴启发", ""),
                "原始分析": analysis.get("原始分析", ""),
                "Judge评语": _summarize_judge(analysis),
                "Skeptic质疑": _summarize_skeptic(analysis),
                "scoring_version": row[13] or SCORING_VERSION_V1,
            }
        )
    return items


def upsert_paper(
    conn: sqlite3.Connection,
    source: str,
    url: str,
    doi: str,
    title: str,
    english_abstract: str,
    chinese_summary: str,
    published_date: str,
    query_name: str,
    authors: list[str],
    primary_category: str,
    categories: list[str],
    analysis: dict,
    meets_threshold: bool,
    eligible_for_pending: bool,
    content_hash: str,
    analyzed_at: str | None = None,
):
    now = datetime.now().isoformat(timespec="seconds")
    if doi:
        existing = conn.execute(
            "SELECT first_seen_at, report_count, reported_at FROM papers WHERE url = ? OR doi = ? LIMIT 1",
            (url, doi),
        ).fetchone()
    else:
        existing = conn.execute(
            "SELECT first_seen_at, report_count, reported_at FROM papers WHERE url = ? LIMIT 1",
            (url,),
        ).fetchone()
    first_seen_at = existing[0] if existing and existing[0] else now
    report_count = existing[1] if existing and existing[1] is not None else 0
    reported_at = existing[2] if existing else None

    scoring_version = analysis.get("__scoring_version") or SCORING_VERSION_V1
    skeptic_payload = analysis.get("__skeptic")
    skeptic_flags_str = (
        json.dumps(skeptic_payload, ensure_ascii=False)
        if isinstance(skeptic_payload, dict)
        else None
    )
    judge_payload = analysis.get("__judge") or {}
    judge_rationale_str = str(judge_payload.get("评分理由", "")) if isinstance(judge_payload, dict) else ""

    conn.execute(
        """
        INSERT INTO papers (
            url, doi, source, title, english_abstract, chinese_summary, published_date, query_name, authors,
            primary_category, categories, analysis_json, related_score, analysis_status, meets_threshold,
            eligible_for_pending, first_seen_at, last_seen_at, displayed_at, display_count, reported_at, report_count, content_hash, created_at, updated_at, analyzed_at,
            scoring_version, skeptic_flags, judge_rationale
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            doi=excluded.doi,
            source=excluded.source,
            title=excluded.title,
            english_abstract=excluded.english_abstract,
            chinese_summary=excluded.chinese_summary,
            published_date=excluded.published_date,
            query_name=excluded.query_name,
            authors=excluded.authors,
            primary_category=excluded.primary_category,
            categories=excluded.categories,
            analysis_json=excluded.analysis_json,
            related_score=excluded.related_score,
            analysis_status=excluded.analysis_status,
            meets_threshold=excluded.meets_threshold,
            eligible_for_pending=excluded.eligible_for_pending,
            last_seen_at=excluded.last_seen_at,
            content_hash=excluded.content_hash,
            updated_at=excluded.updated_at,
            analyzed_at=COALESCE(excluded.analyzed_at, papers.analyzed_at),
            scoring_version=excluded.scoring_version,
            skeptic_flags=excluded.skeptic_flags,
            judge_rationale=excluded.judge_rationale
        """,
        (
            url,
            doi,
            source,
            title,
            english_abstract,
            chinese_summary,
            published_date,
            query_name,
            "; ".join(authors),
            primary_category,
            "; ".join(categories),
            json.dumps(analysis, ensure_ascii=False),
            analysis.get("相关性分数", 0),
            analysis.get("分析状态", "unknown"),
            1 if meets_threshold else 0,
            1 if eligible_for_pending else 0,
            first_seen_at,
            now,
            None,
            0,
            reported_at,
            report_count,
            content_hash,
            now,
            now,
            analyzed_at,
            scoring_version,
            skeptic_flags_str,
            judge_rationale_str,
        ),
    )


def parse_analysis_text(text: str) -> dict:
    relation_key = "与建筑/体育空间/疗愈环境研究相关性"
    legacy_relation_key = "与建筑/体育空间研究相关性"
    result = {
        "中文摘要": "",
        "研究主题": "",
        "空间/场景类型": "",
        "研究场景": "",
        "自变量": "",
        "因变量": "",
        "行为指标": "",
        "生理/感知指标": "",
        "研究方法": "",
        "数据/样本": "",
        "主要结论": "",
        relation_key: "",
        "相关性分数": 0,
        "可借鉴启发": "",
        "原始分析": text,
    }

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for key in list(result.keys()):
                if key == "原始分析":
                    continue
                if key in data and data[key] is not None:
                    result[key] = data[key]
            if not result[relation_key] and legacy_relation_key in data and data[legacy_relation_key] is not None:
                result[relation_key] = data[legacy_relation_key]
            try:
                result["相关性分数"] = int(result.get("相关性分数", 0))
            except Exception:
                result["相关性分数"] = 0
            result[legacy_relation_key] = result[relation_key]
            return result
    except Exception:
        pass

    current_key = None
    alias_keys = [relation_key, legacy_relation_key]
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        matched = False
        for key in list(result.keys()) + [legacy_relation_key]:
            if key == "原始分析":
                continue
            if line.startswith(f"{key}：") or line.startswith(f"{key}:"):
                current_key = relation_key if key in alias_keys else key
                value = line.split("：", 1)[-1] if "：" in line else line.split(":", 1)[-1]
                value = value.strip()
                if current_key == "相关性分数":
                    digits = ''.join(ch for ch in value if ch.isdigit())
                    try:
                        result[current_key] = int(digits) if digits else 0
                    except Exception:
                        result[current_key] = 0
                else:
                    result[current_key] = value
                matched = True
                break
        if not matched and current_key and current_key != "原始分析":
            if current_key == "相关性分数":
                continue
            result[current_key] = (result[current_key] + " " + line).strip()

    result[legacy_relation_key] = result[relation_key]
    return result


SINGLE_AGENT_PROMPT_TEMPLATE = """
你是一个建筑学、体育空间、VR环境、行为轨迹与疗愈空间领域的专业文献分析助手。

你的任务是：基于论文标题和英文摘要，判断这篇论文对“空间环境—行为/感知/健康结果”研究是否具有直接价值、可迁移价值，或基本无关。

【硬性约束 - 必须遵守】
A. 严禁仅因关键词命中就给高分。必须确认：(i) 研究问题是否真正关于环境/空间/场景；(ii) 空间/环境变量是否进入了实验设计或作为自变量/因变量；(iii) 结论是否涉及环境-行为、环境-感知或环境-健康。
B. 若论文属于以下之一，最终分数不得超过 39：
   - 纯机器学习/计算机视觉/NLP 方法或基线论文，仅在室内/街景数据集上做分割/检测/生成
   - 机器人导航、自动驾驶、SLAM 中的 "environment" 指物理状态空间而非人因
   - 临床试验或药物/手术研究，干预手段不涉及空间或环境
   - GIS 或社会物理研究只做数据挖掘，无人因/行为/感知维度
C. 若标题和摘要中没有明确提到空间/环境变量，即使关键词"spatial"/"environment"出现也必须判为 0-39。

判断原则：
1. 只能根据标题和摘要中明确提供的信息作答，不得补充外部常识；没有提到的内容一律写"未明确说明"。
2. 即使论文不是直接研究建筑/体育/疗愈空间，只要其方法、指标、变量、实验场景或结论对这些领域有明确可迁移价值，也可以给中等分数。

评分准则（严格遵守，每档给出锚定示例）：
- 90-100 高度直接相关：真实建筑/体育/疗愈空间里的人因实验或观察研究。例：EEG 测量参与者在疗愈花园 vs 普通花园的压力恢复差异。
- 70-89 较强可迁移：非同一应用域，但方法、变量、场景可直接迁移。例：VR 中操纵房间层高对空间感知的影响。
- 50-69 有间接参考：只在某一侧（方法 or 场景 or 变量）与本领域相关。例：一般性占用行为建模但未针对具体建筑类型。
- 40-49 边缘相关：仅有少量可借鉴之处。例：用步态识别改进康复，但未涉及空间维度。
- 0-39 基本无关：纯 ML/CV 基线、一般心理或医学治疗、机器人 SLAM、GIS 数据挖掘，即使包含 "spatial"/"environment"/"indoor" 关键词。

请全部使用简洁中文，并仅输出一个有效 JSON 对象（不要 Markdown 代码块），必须包含以下字段：
- 中文摘要
- 研究主题
- 空间/场景类型
- 研究场景
- 自变量
- 因变量
- 行为指标
- 生理/感知指标
- 研究方法
- 数据/样本
- 主要结论
- 与建筑/体育空间/疗愈环境研究相关性
- 相关性分数（0-100 整数，严格遵守上述硬性约束）
- 可借鉴启发

没有提到的信息一律写"未明确说明"；可借鉴启发只能基于摘要已出现的方法、变量、场景或结论来写。

标题：{title}

英文摘要：{abstract}
"""


def _empty_extraction_dict() -> dict:
    result = {key: "" for key in EXTRACTION_FIELDS}
    result[RELATION_KEY] = ""
    result[LEGACY_RELATION_KEY] = ""
    result["相关性分数"] = 0
    result["可借鉴启发"] = ""
    result["原始分析"] = ""
    return result


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _extract_json_obj(text: str) -> dict | None:
    candidate = _strip_code_fence(text)
    try:
        data = json.loads(candidate)
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(candidate[start : end + 1])
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


def _call_llm(client: OpenAI, model: str, prompt: str, retries: int, retry_delay: int) -> str:
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            last_error = e
            logger.warning("LLM 调用(%s) 第 %d 次失败: %s", model, attempt, e)
            if attempt < retries:
                time.sleep(retry_delay * (2 ** (attempt - 1)))
    raise RuntimeError(f"LLM 调用全部失败：{last_error}")


def analyze_paper(client: OpenAI, model: str, title: str, abstract: str, retries: int = 3, retry_delay: int = 3) -> dict:
    prompt = SINGLE_AGENT_PROMPT_TEMPLATE.format(title=title, abstract=abstract)

    try:
        text = _call_llm(client, model, prompt, retries, retry_delay)
    except Exception as e:
        result = _empty_extraction_dict()
        result["原始分析"] = f"分析失败：{e}"
        result["分析状态"] = "failed"
        result["__scoring_version"] = SCORING_VERSION_V1
        return result

    result = parse_analysis_text(text)
    result["分析状态"] = "success"
    result["__scoring_version"] = SCORING_VERSION_V1
    return result


# ============================================================
# 多 Agent 评分：Researcher -> Skeptic -> Judge
# ============================================================

RESEARCHER_PROMPT_TEMPLATE = """
你是"事实抽取 Agent"。只负责从论文标题和英文摘要中提取结构化事实，不做评分、不做价值判断。

严格规则：
1. 只能使用标题和摘要明确提到的信息，禁止推断或补充外部常识。
2. 未提到的内容必须填写"未明确说明"。
3. 以下 3 个布尔字段必须基于摘要原文判定，任何一个为 true 都必须在"关键词证据"里给出对应的英文原句片段：
   - 是否有明确空间环境要素：必须明确提到 built environment / indoor / room / space / architecture / landscape / garden / virtual environment / VR scene / 特定建筑类型等真实物理或虚拟空间，并参与了研究设计
   - 研究对象是否为人类用户：实验或观察对象包括真实人类参与者
   - 实验是否在真实或虚拟空间中进行：研究情境是真实空间/VR/AR/仿真环境，而不是仅在纸面或纯算法层面
4. "关键词证据"是英文片段列表，每条 20-80 字，直接摘抄摘要原文。
5. 若无法在摘要中定位证据，对应布尔字段必须为 false。

仅输出一个有效 JSON（不要 Markdown 代码块），字段固定为：
{{
  "中文摘要": "...",
  "研究主题": "...",
  "空间/场景类型": "...",
  "研究场景": "...",
  "自变量": "...",
  "因变量": "...",
  "行为指标": "...",
  "生理/感知指标": "...",
  "研究方法": "...",
  "数据/样本": "...",
  "主要结论": "...",
  "是否有明确空间环境要素": true/false,
  "研究对象是否为人类用户": true/false,
  "实验是否在真实或虚拟空间中进行": true/false,
  "关键词证据": ["...", "..."]
}}

标题：{title}

英文摘要：{abstract}
"""


SKEPTIC_PROMPT_TEMPLATE = """
你是"质疑 Agent"（Skeptic）。你的核心任务是识别假阳性——即看似相关但其实对"建筑学/体育空间/VR 环境/行为轨迹/疗愈空间"研究无实质价值的论文。

典型假阳性模式（请逐条核查，命中则列入"假阳性信号"）：
(a) 纯 ML/CV/NLP 基线、方法论文；仅将 "spatial"/"environment" 作描述词或数据集属性。
(b) 一般心理学/医学治疗/临床试验，没有空间或环境变量参与设计。
(c) 机器人导航、自动驾驶、SLAM 把 "environment" 当物理状态空间。
(d) GIS、社会物理或城市计算研究只做数据挖掘，无行为/感知/健康维度。
(e) 健康干预研究，但干预手段不是空间/环境本身。
(f) 元分析/综述/观点文章，缺乏可操作的空间-行为证据。
(g) 关键词命中但核心研究问题与空间/人因无关。

硬性规则：
- 如果 Researcher 给出 `是否有明确空间环境要素=false`，你的 `建议分数上限` 必须 ≤ 45。
- 如果 Researcher 3 个布尔字段全部为 false，`建议分数上限` 必须 ≤ 39。
- 若 Researcher 已列出充分的空间/人因证据（≥2 条具体英文证据），可给出较宽松的上限（例如 ≤ 89）。

Researcher 的输出：
{researcher_json}

标题：{title}
英文摘要：{abstract}

仅输出一个有效 JSON（不要 Markdown 代码块）：
{{
  "假阳性信号": ["..."],
  "缺失要素": ["..."],
  "反驳论据": "简短总结，说明为什么这篇论文可能被误判为高相关",
  "建议分数上限": 0-100 的整数
}}

如果确实没有明显假阳性信号，请把 "假阳性信号" 留空 [] 并给出较宽松的 "建议分数上限"。
"""


JUDGE_PROMPT_TEMPLATE = """
你是"主审 Agent"（Judge）。综合 Researcher 的事实抽取和 Skeptic 的质疑，给出最终相关性分数与评语。

评分 Rubric（严格锚定）：
- 90-100 真实建筑/体育/疗愈空间里的人因实验/观察研究（例：EEG+VR 测量疗愈花园的压力恢复）
- 70-89 跨域但方法/变量/场景可直接迁移（例：VR 中操纵房间层高对空间感知影响）
- 50-69 只在某一侧（方法 or 场景 or 变量）相关（例：一般性占用行为建模，无具体建筑类型）
- 40-49 仅边缘参考（例：用步态识别改进康复，无空间维度）
- 0-39 纯 ML/CV 基线、一般心理/医学治疗、机器人 SLAM、GIS 数据挖掘（即使包含空间关键词）

硬性约束（不得违反）：
1. 如果 Researcher 3 个布尔字段全部为 false，最终分数 ≤ 39。
2. 如果 Researcher `是否有明确空间环境要素=false`，最终分数 ≤ 45。
3. 如果 Skeptic 列出 ≥2 条明确"假阳性信号"，你必须 `是否采纳Skeptic上限=true`，且最终分数 ≤ Skeptic 建议分数上限。
4. 只有当你能在 `核心匹配点` 给出 ≥2 条来自摘要原文的具体空间/人因证据时，分数才能 ≥70。
5. 纯综述/观点/元分析最高 ≤ 59。

Researcher 输出：
{researcher_json}

Skeptic 输出：
{skeptic_json}

标题：{title}
英文摘要：{abstract}

仅输出一个有效 JSON（不要 Markdown 代码块）：
{{
  "最终分数": 0-100 整数,
  "评分理由": "综合 Researcher 事实与 Skeptic 质疑得出的结论，2-4 句",
  "核心匹配点": ["具体空间/人因证据 1", "..."],
  "主要风险": ["如何可能是假阳性，或评分上限的依据"],
  "是否采纳Skeptic上限": true/false,
  "采纳说明": "为什么采纳或反驳 Skeptic 的建议上限"
}}
"""


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value).strip().lower()
    return s in {"true", "1", "yes", "y", "是", "有", "t"}


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return default


def researcher_agent(
    client: OpenAI, model: str, title: str, abstract: str, retries: int, retry_delay: int
) -> dict:
    prompt = RESEARCHER_PROMPT_TEMPLATE.format(title=title, abstract=abstract)
    text = _call_llm(client, model, prompt, retries, retry_delay)
    data = _extract_json_obj(text) or {}

    out = {key: str(data.get(key, "未明确说明") or "未明确说明") for key in EXTRACTION_FIELDS}
    for key in SPATIAL_FLAG_KEYS:
        out[key] = _coerce_bool(data.get(key, False))
    evidence = data.get("关键词证据", [])
    if isinstance(evidence, list):
        out["关键词证据"] = [str(x) for x in evidence if x]
    else:
        out["关键词证据"] = [str(evidence)] if evidence else []
    out["__raw"] = text
    return out


def skeptic_agent(
    client: OpenAI,
    model: str,
    title: str,
    abstract: str,
    researcher_out: dict,
    retries: int,
    retry_delay: int,
) -> dict:
    visible = {k: researcher_out.get(k) for k in EXTRACTION_FIELDS + SPATIAL_FLAG_KEYS + ["关键词证据"]}
    prompt = SKEPTIC_PROMPT_TEMPLATE.format(
        researcher_json=json.dumps(visible, ensure_ascii=False, indent=2),
        title=title,
        abstract=abstract,
    )
    text = _call_llm(client, model, prompt, retries, retry_delay)
    data = _extract_json_obj(text) or {}

    flags = data.get("假阳性信号") or []
    if not isinstance(flags, list):
        flags = [str(flags)]
    missing = data.get("缺失要素") or []
    if not isinstance(missing, list):
        missing = [str(missing)]

    cap = _coerce_int(data.get("建议分数上限"), default=100)
    cap = max(0, min(100, cap))

    # 安全护栏：若 Researcher bool 都为 false，强制压低 cap
    all_false = not any(researcher_out.get(k) for k in SPATIAL_FLAG_KEYS)
    no_spatial = not researcher_out.get("是否有明确空间环境要素", False)
    if all_false:
        cap = min(cap, 39)
    elif no_spatial:
        cap = min(cap, 45)

    return {
        "假阳性信号": [str(x) for x in flags if x],
        "缺失要素": [str(x) for x in missing if x],
        "反驳论据": str(data.get("反驳论据", "") or ""),
        "建议分数上限": cap,
        "__raw": text,
    }


def judge_agent(
    client: OpenAI,
    model: str,
    title: str,
    abstract: str,
    researcher_out: dict,
    skeptic_out: dict,
    retries: int,
    retry_delay: int,
) -> dict:
    researcher_visible = {
        k: researcher_out.get(k) for k in EXTRACTION_FIELDS + SPATIAL_FLAG_KEYS + ["关键词证据"]
    }
    skeptic_visible = {k: skeptic_out.get(k) for k in ["假阳性信号", "缺失要素", "反驳论据", "建议分数上限"]}
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        researcher_json=json.dumps(researcher_visible, ensure_ascii=False, indent=2),
        skeptic_json=json.dumps(skeptic_visible, ensure_ascii=False, indent=2),
        title=title,
        abstract=abstract,
    )
    text = _call_llm(client, model, prompt, retries, retry_delay)
    data = _extract_json_obj(text) or {}

    score = _coerce_int(data.get("最终分数"), default=0)
    score = max(0, min(100, score))

    matches = data.get("核心匹配点") or []
    if not isinstance(matches, list):
        matches = [str(matches)]
    risks = data.get("主要风险") or []
    if not isinstance(risks, list):
        risks = [str(risks)]

    accept_cap = _coerce_bool(data.get("是否采纳Skeptic上限", False))
    cap = skeptic_out.get("建议分数上限", 100)

    # 硬性护栏
    all_false = not any(researcher_out.get(k) for k in SPATIAL_FLAG_KEYS)
    no_spatial = not researcher_out.get("是否有明确空间环境要素", False)
    flags_count = len(skeptic_out.get("假阳性信号", []))

    enforced_ceiling = 100
    if all_false:
        enforced_ceiling = min(enforced_ceiling, 39)
    if no_spatial:
        enforced_ceiling = min(enforced_ceiling, 45)
    if flags_count >= 2:
        enforced_ceiling = min(enforced_ceiling, cap)
        accept_cap = True
    if accept_cap:
        enforced_ceiling = min(enforced_ceiling, cap)

    if score > enforced_ceiling:
        logger.info(
            "Judge 分数 %d 被硬性上限压到 %d (skeptic_cap=%s flags=%d all_false=%s no_spatial=%s)",
            score, enforced_ceiling, cap, flags_count, all_false, no_spatial,
        )
        score = enforced_ceiling

    return {
        "最终分数": score,
        "评分理由": str(data.get("评分理由", "") or ""),
        "核心匹配点": [str(x) for x in matches if x],
        "主要风险": [str(x) for x in risks if x],
        "是否采纳Skeptic上限": accept_cap,
        "采纳说明": str(data.get("采纳说明", "") or ""),
        "__raw": text,
    }


def analyze_paper_multi_agent(
    client: OpenAI,
    runtime: dict,
    title: str,
    abstract: str,
) -> dict:
    retries = int(runtime.get("agent_retries", 3))
    retry_delay = int(runtime.get("agent_retry_delay", 3))
    models = {
        "researcher": runtime.get("researcher_model") or runtime.get("openai_model"),
        "skeptic": runtime.get("skeptic_model") or runtime.get("openai_model"),
        "judge": runtime.get("judge_model") or runtime.get("openai_model"),
    }

    try:
        researcher_out = researcher_agent(client, models["researcher"], title, abstract, retries, retry_delay)
    except Exception as e:
        logger.warning("Researcher 失败，降级到 single agent: %s", e)
        return analyze_paper(client, runtime.get("openai_model"), title, abstract, retries, retry_delay)

    try:
        skeptic_out = skeptic_agent(
            client, models["skeptic"], title, abstract, researcher_out, retries, retry_delay
        )
    except Exception as e:
        logger.warning("Skeptic 失败，使用默认质疑: %s", e)
        skeptic_out = {
            "假阳性信号": ["skeptic_agent 调用失败"],
            "缺失要素": [],
            "反驳论据": f"Skeptic 不可用：{e}",
            "建议分数上限": 50,
            "__raw": "",
        }

    try:
        judge_out = judge_agent(
            client, models["judge"], title, abstract, researcher_out, skeptic_out, retries, retry_delay
        )
    except Exception as e:
        logger.warning("Judge 失败，基于 skeptic 上限保守估分: %s", e)
        judge_out = {
            "最终分数": min(50, int(skeptic_out.get("建议分数上限", 50))),
            "评分理由": f"Judge 不可用：{e}；采用 skeptic 建议上限作为保守估分。",
            "核心匹配点": [],
            "主要风险": skeptic_out.get("假阳性信号", []),
            "是否采纳Skeptic上限": True,
            "采纳说明": "Judge 调用失败，被动采纳。",
            "__raw": "",
        }

    merged = _empty_extraction_dict()
    for key in EXTRACTION_FIELDS:
        merged[key] = str(researcher_out.get(key, "未明确说明") or "未明确说明")
    merged[RELATION_KEY] = judge_out.get("评分理由", "") or ""
    merged[LEGACY_RELATION_KEY] = merged[RELATION_KEY]
    merged["相关性分数"] = int(judge_out.get("最终分数", 0))
    inspirations = researcher_out.get("主要结论", "") or ""
    merged["可借鉴启发"] = inspirations if inspirations and inspirations != "未明确说明" else str(judge_out.get("核心匹配点") or "")
    merged["原始分析"] = json.dumps(
        {
            "researcher": {k: researcher_out.get(k) for k in EXTRACTION_FIELDS + SPATIAL_FLAG_KEYS + ["关键词证据"]},
            "skeptic": {k: skeptic_out.get(k) for k in ["假阳性信号", "缺失要素", "反驳论据", "建议分数上限"]},
            "judge": {k: judge_out.get(k) for k in ["最终分数", "评分理由", "核心匹配点", "主要风险", "是否采纳Skeptic上限", "采纳说明"]},
        },
        ensure_ascii=False,
        indent=2,
    )
    merged["分析状态"] = "success"
    merged["__scoring_version"] = SCORING_VERSION_V2
    merged["__researcher"] = {k: researcher_out.get(k) for k in EXTRACTION_FIELDS + SPATIAL_FLAG_KEYS + ["关键词证据"]}
    merged["__skeptic"] = {k: skeptic_out.get(k) for k in ["假阳性信号", "缺失要素", "反驳论据", "建议分数上限"]}
    merged["__judge"] = {k: judge_out.get(k) for k in ["最终分数", "评分理由", "核心匹配点", "主要风险", "是否采纳Skeptic上限", "采纳说明"]}
    return merged


def analyze_paper_dispatch(
    client: OpenAI,
    runtime: dict,
    title: str,
    abstract: str,
) -> dict:
    mode = (runtime.get("scoring_mode") or "multi").lower()
    if mode == "single":
        return analyze_paper(
            client,
            runtime.get("openai_model"),
            title,
            abstract,
            int(runtime.get("agent_retries", 3)),
            int(runtime.get("agent_retry_delay", 3)),
        )
    return analyze_paper_multi_agent(client, runtime, title, abstract)


def normalize_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return value[:10]


def fetch_arxiv_results(query_text: str, max_results: int, retries: int = 3) -> list[dict]:
    for attempt in range(1, retries + 1):
        try:
            items = []
            search = arxiv.Search(
                query=query_text,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
            )
            for result in search.results():
                published = result.published
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                items.append(
                    {
                        "source": "arxiv",
                        "doi": normalize_doi(getattr(result, 'doi', '') or ''),
                        "title": (result.title or "").strip(),
                        "abstract": (result.summary or "").strip(),
                        "url": result.entry_id,
                        "published": published,
                        "authors": [a.name for a in getattr(result, "authors", [])],
                        "primary_category": getattr(result, "primary_category", "") or "",
                        "categories": getattr(result, "categories", []) or [],
                    }
                )
            return items
        except Exception as e:
            if attempt < retries and "503" in str(e):
                wait = 5 * (2 ** (attempt - 1))
                logger.warning("arXiv 503 限流，%d秒后重试 (%d/%d)", wait, attempt, retries)
                time.sleep(wait)
            else:
                raise
    return []


def fetch_openalex_results(query_text: str, max_results: int) -> list[dict]:
    items = []
    try:
        url = "https://api.openalex.org/works"
        params = {
            "search": query_text,
            "per-page": min(max_results, 25),
            "sort": "publication_date:desc",
        }
        data = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=30).json()
        for work in data.get("results", []):
            abstract = ""
            inverted = work.get("abstract_inverted_index")
            if inverted:
                terms = []
                for word, positions in inverted.items():
                    for p in positions:
                        terms.append((p, word))
                abstract = " ".join(word for _, word in sorted(terms))
            if not abstract:
                abstract = work.get("title", "")
            items.append(
                {
                    "source": "openalex",
                    "doi": normalize_doi(work.get("doi") or ""),
                    "title": work.get("title", "").strip(),
                    "abstract": abstract.strip(),
                    "url": work.get("primary_location", {}).get("landing_page_url")
                    or work.get("doi")
                    or f"https://openalex.org/{work.get('id','').split('/')[-1]}",
                    "published": datetime.fromisoformat((work.get("publication_date") or "1970-01-01") + "T00:00:00+00:00"),
                    "authors": [a.get("author", {}).get("display_name", "") for a in work.get("authorships", []) if a.get("author", {}).get("display_name")],
                    "primary_category": (work.get("primary_topic") or {}).get("display_name", ""),
                    "categories": [c.get("display_name", "") for c in work.get("concepts", [])[:8] if c.get("display_name")],
                }
            )
    except Exception:
        logger.exception("OpenAlex 抓取失败, query: %s", query_text[:100])
        return []
    return items


def fetch_crossref_results(query_text: str, max_results: int) -> list[dict]:
    items = []
    try:
        url = "https://api.crossref.org/works"
        params = {"query": query_text, "rows": min(max_results, 20), "sort": "published", "order": "desc"}
        data = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=30).json()
        for work in data.get("message", {}).get("items", []):
            abstract = work.get("abstract", "") or ""
            abstract = abstract.replace("<jats:p>", "").replace("</jats:p>", " ").strip()
            title = (work.get("title") or [""])[0]
            published_parts = (((work.get("published-print") or work.get("published-online") or {}).get("date-parts") or [[1970, 1, 1]])[0])
            while len(published_parts) < 3:
                published_parts.append(1)
            items.append(
                {
                    "source": "crossref",
                    "doi": normalize_doi(work.get("DOI") or work.get("doi") or ""),
                    "title": title.strip(),
                    "abstract": (abstract or title).strip(),
                    "url": work.get("URL", ""),
                    "published": datetime(published_parts[0], published_parts[1], published_parts[2], tzinfo=timezone.utc),
                    "authors": [" ".join(filter(None, [a.get("given", ""), a.get("family", "")])).strip() for a in work.get("author", []) if (a.get("given") or a.get("family"))],
                    "primary_category": (work.get("subject") or [""])[0],
                    "categories": work.get("subject", [])[:8],
                }
            )
    except Exception:
        logger.exception("Crossref 抓取失败, query: %s", query_text[:100])
        return []
    return items


def fetch_semantic_scholar_results(query_text: str, max_results: int) -> list[dict]:
    items = []
    try:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query_text,
            "limit": min(max_results, 20),
            "fields": "title,abstract,url,year,authors,publicationDate,fieldsOfStudy,externalIds",
        }
        data = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=30).json()
        for paper in data.get("data", []):
            date_str = paper.get("publicationDate") or f"{paper.get('year', 1970)}-01-01"
            fields_of_study = paper.get("fieldsOfStudy") or []
            if not isinstance(fields_of_study, list):
                fields_of_study = []
            items.append(
                {
                    "source": "semantic_scholar",
                    "doi": normalize_doi(paper.get("externalIds", {}).get("DOI", "") if isinstance(paper.get("externalIds"), dict) else ""),
                    "title": (paper.get("title") or "").strip(),
                    "abstract": (paper.get("abstract") or paper.get("title") or "").strip(),
                    "url": paper.get("url") or f"https://www.semanticscholar.org/paper/{paper.get('paperId','')}",
                    "published": datetime.fromisoformat(normalize_date(date_str) + "T00:00:00+00:00"),
                    "authors": [a.get("name", "") for a in paper.get("authors", []) if a.get("name")],
                    "primary_category": fields_of_study[0] if fields_of_study else "",
                    "categories": fields_of_study[:8],
                }
            )
    except Exception:
        logger.exception("Semantic Scholar 抓取失败, query: %s", query_text[:100])
        return []
    return items


def fetch_europepmc_results(query_text: str, max_results: int) -> list[dict]:
    items = []
    try:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query_text,
            "resultType": "core",
            "pageSize": min(max_results, 25),
            "sort": "P_PDATE_D desc",
            "format": "json",
        }
        data = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=30).json()
        for work in data.get("resultList", {}).get("result", []):
            abstract = (work.get("abstractText") or work.get("title") or "").strip()
            title = (work.get("title") or "").strip()
            date_str = work.get("firstPublicationDate") or "1970-01-01"
            doi = normalize_doi(work.get("doi") or "")
            paper_url = f"https://europepmc.org/article/{work.get('source', 'MED')}/{work.get('id', '')}"
            if doi:
                paper_url = f"https://doi.org/{doi}"
            authors_str = work.get("authorString") or ""
            items.append(
                {
                    "source": "europepmc",
                    "doi": doi,
                    "title": title,
                    "abstract": abstract,
                    "url": paper_url,
                    "published": datetime.fromisoformat(date_str + "T00:00:00+00:00"),
                    "authors": [a.strip() for a in authors_str.split(",") if a.strip()][:20],
                    "primary_category": work.get("journalTitle") or "",
                    "categories": [kw.strip() for kw in (work.get("keywordList", {}).get("keyword") or [])[:8]],
                }
            )
    except Exception:
        logger.exception("Europe PMC 抓取失败, query: %s", query_text[:100])
        return []
    return items


def fetch_core_results(query_text: str, max_results: int) -> list[dict]:
    api_key = os.getenv("CORE_API_KEY", "").strip()
    if not api_key:
        return []
    items = []
    try:
        url = "https://api.core.ac.uk/v3/search/works"
        headers = {**REQUEST_HEADERS, "Authorization": f"Bearer {api_key}"}
        params = {"q": query_text, "limit": min(max_results, 20)}
        data = requests.get(url, params=params, headers=headers, timeout=30).json()
        for work in data.get("results", []):
            abstract = (work.get("abstract") or work.get("title") or "").strip()
            title = (work.get("title") or "").strip()
            date_str = (work.get("publishedDate") or work.get("yearPublished") or "1970") [:10]
            if len(date_str) == 4:
                date_str += "-01-01"
            doi = normalize_doi(work.get("doi") or "")
            paper_url = work.get("downloadUrl") or work.get("sourceFulltextUrls", [""])[0] if work.get("sourceFulltextUrls") else ""
            if not paper_url and doi:
                paper_url = f"https://doi.org/{doi}"
            if not paper_url:
                paper_url = f"https://core.ac.uk/works/{work.get('id', '')}"
            authors_list = work.get("authors") or []
            items.append(
                {
                    "source": "core",
                    "doi": doi,
                    "title": title,
                    "abstract": abstract,
                    "url": paper_url,
                    "published": datetime.fromisoformat(date_str + "T00:00:00+00:00"),
                    "authors": [a.get("name", "") if isinstance(a, dict) else str(a) for a in authors_list][:20],
                    "primary_category": "",
                    "categories": [],
                }
            )
    except Exception:
        logger.exception("CORE 抓取失败, query: %s", query_text[:100])
        return []
    return items


def fetch_source_results(source_name: str, query_text: str, max_results: int) -> list[dict]:
    if source_name == "arxiv":
        return fetch_arxiv_results(query_text, max_results)
    if source_name == "openalex":
        return fetch_openalex_results(query_text, max_results)
    if source_name == "crossref":
        return fetch_crossref_results(query_text, max_results)
    if source_name == "semantic_scholar":
        return fetch_semantic_scholar_results(query_text, max_results)
    if source_name == "europepmc":
        return fetch_europepmc_results(query_text, max_results)
    if source_name == "core":
        return fetch_core_results(query_text, max_results)
    return []


def resolve_query_for_source(source_name: str, query_name: str, queries: dict, generic_queries: dict) -> str:
    if source_name == "arxiv":
        return queries.get(query_name, "")
    if source_name == "semantic_scholar":
        # Semantic Scholar API works best with short natural-language queries
        ss_queries = generic_queries.get("_semantic_scholar", {})
        if isinstance(ss_queries, dict) and query_name in ss_queries:
            return ss_queries[query_name]
    return generic_queries.get(query_name) or queries.get(query_name, "")


def fetch_journal_papers(journals: list[dict], days_back: int, max_per_journal: int,
                         relevance_keywords: list[str] | None = None) -> list[dict]:
    """Fetch recent papers from specific journals via OpenAlex ISSN filtering.

    If relevance_keywords is provided, only papers whose title or abstract
    contain at least one keyword will be included. This avoids sending
    irrelevant papers to the LLM for analysis.
    """
    items = []
    kw_lower = [k.lower() for k in (relevance_keywords or [])]
    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    for journal in journals:
        issn = journal.get("issn", "").strip()
        name = journal.get("name", issn)
        if not issn:
            continue
        try:
            url = "https://api.openalex.org/works"
            params = {
                "filter": f"primary_location.source.issn:{issn},from_publication_date:{from_date}",
                "per-page": min(max_per_journal, 25),
                "sort": "publication_date:desc",
            }
            data = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=30).json()
            fetched = 0
            kept = 0
            for work in data.get("results", []):
                abstract = ""
                inverted = work.get("abstract_inverted_index")
                if inverted:
                    terms = []
                    for word, positions in inverted.items():
                        for p in positions:
                            terms.append((p, word))
                    abstract = " ".join(word for _, word in sorted(terms))
                if not abstract:
                    abstract = work.get("title", "")
                title = work.get("title", "").strip()
                fetched += 1

                # Keyword pre-filtering: skip papers unrelated to research direction
                if kw_lower:
                    combined = f"{title}\n{abstract}".lower()
                    if not any(kw in combined for kw in kw_lower):
                        continue

                items.append(
                    {
                        "source": "journal",
                        "doi": normalize_doi(work.get("doi") or ""),
                        "title": title,
                        "abstract": abstract.strip(),
                        "url": work.get("primary_location", {}).get("landing_page_url")
                        or work.get("doi")
                        or f"https://openalex.org/{work.get('id', '').split('/')[-1]}",
                        "published": datetime.fromisoformat((work.get("publication_date") or "1970-01-01") + "T00:00:00+00:00"),
                        "authors": [a.get("author", {}).get("display_name", "") for a in work.get("authorships", []) if a.get("author", {}).get("display_name")],
                        "primary_category": name,
                        "categories": [c.get("display_name", "") for c in work.get("concepts", [])[:8] if c.get("display_name")],
                    }
                )
                kept += 1
            logger.info("  期刊 %s (ISSN %s): 获取 %d 篇, 关键词命中 %d 篇", name, issn, fetched, kept)
            time.sleep(1.5)
        except Exception:
            logger.exception("期刊 %s (ISSN %s) 抓取失败", name, issn)
    return items


def _summarize_judge(analysis: dict) -> str:
    judge = analysis.get("__judge") or {}
    if not isinstance(judge, dict):
        return ""
    parts = []
    rationale = judge.get("评分理由")
    if rationale:
        parts.append(f"理由：{rationale}")
    matches = judge.get("核心匹配点") or []
    if matches:
        parts.append("核心匹配点：" + "；".join(str(x) for x in matches))
    risks = judge.get("主要风险") or []
    if risks:
        parts.append("主要风险：" + "；".join(str(x) for x in risks))
    return " | ".join(parts)


def _summarize_skeptic(analysis: dict) -> str:
    skeptic = analysis.get("__skeptic") or {}
    if not isinstance(skeptic, dict):
        return ""
    parts = []
    flags = skeptic.get("假阳性信号") or []
    if flags:
        parts.append("假阳性信号：" + "；".join(str(x) for x in flags))
    missing = skeptic.get("缺失要素") or []
    if missing:
        parts.append("缺失要素：" + "；".join(str(x) for x in missing))
    reason = skeptic.get("反驳论据")
    if reason:
        parts.append(f"反驳论据：{reason}")
    cap = skeptic.get("建议分数上限")
    if cap is not None:
        parts.append(f"建议分数上限：{cap}")
    return " | ".join(parts)


def result_to_row(query_name: str, item: dict, analysis: dict) -> dict:
    related_text = analysis.get("与建筑/体育空间/疗愈环境研究相关性") or analysis.get("与建筑/体育空间研究相关性", "")
    return {
        "doi": item.get("doi", ""),
        "source": item["source"],
        "query_name": query_name,
        "published_date": item["published"].strftime("%Y-%m-%d"),
        "title": item["title"],
        "url": item["url"],
        "authors": "; ".join(item["authors"]),
        "primary_category": item["primary_category"],
        "categories": "; ".join(item["categories"]),
        "english_abstract": item["abstract"],
        "中文摘要": analysis.get("中文摘要", ""),
        "研究主题": analysis.get("研究主题", ""),
        "空间/场景类型": analysis.get("空间/场景类型", ""),
        "研究场景": analysis.get("研究场景", ""),
        "自变量": analysis.get("自变量", ""),
        "因变量": analysis.get("因变量", ""),
        "行为指标": analysis.get("行为指标", ""),
        "生理/感知指标": analysis.get("生理/感知指标", ""),
        "研究方法": analysis.get("研究方法", ""),
        "数据/样本": analysis.get("数据/样本", ""),
        "主要结论": analysis.get("主要结论", ""),
        "与建筑/体育空间/疗愈环境研究相关性": related_text,
        "相关性分数": analysis.get("相关性分数", 0),
        "可借鉴启发": analysis.get("可借鉴启发", ""),
        "原始分析": analysis.get("原始分析", ""),
        "Judge评语": _summarize_judge(analysis),
        "Skeptic质疑": _summarize_skeptic(analysis),
        "scoring_version": analysis.get("__scoring_version") or SCORING_VERSION_V1,
    }


def _format_stats_diagnostic(stats: dict | None) -> list[str]:
    if not stats:
        return ["(无运行统计信息)"]
    lines = [
        "本次运行诊断：",
        f"  - 总抓取:{stats.get('fetched', 0)} 篇",
        f"  - 日期过旧被过滤:{stats.get('too_old', 0)} 篇",
        f"  - 重复去除:{stats.get('duplicate', 0)} 篇",
        f"  - 排除关键词命中:{stats.get('excluded', 0)} 篇",
        f"  - 必含关键词未命中:{stats.get('must_have_filtered', 0)} 篇",
        f"  - 首次见到论文:{stats.get('first_seen', 0)} 篇",
        f"  - 历史已见论文:{stats.get('seen_before', 0)} 篇",
        f"  - 缓存命中(已分析):{stats.get('cache_hit', 0)} 篇",
        f"  - 低分缓存触发重分析:{stats.get('cache_refresh', 0)} 篇",
        f"  - 新分析:{stats.get('analyzed', 0)} 篇",
        f"  - 分析失败:{stats.get('analysis_failed', 0)} 篇",
        f"  - 低于相关性阈值:{stats.get('below_min_relevance', 0)} 篇",
        f"  - 已报告/已展示:{stats.get('already_reported', 0)} 篇",
    ]
    source_details = stats.get("source_details", {})
    if source_details:
        lines.append("")
        lines.append("各数据源状态：")
        for key, detail in source_details.items():
            err = detail.get("error", "")
            if err:
                status = f"抓取失败：{err}"
            elif detail.get("fetched", 0) == 0:
                status = "获取 0 篇"
            else:
                status = f"获取 {detail.get('fetched', 0)} 篇"
            lines.append(f"  - {key}: {status}")
    legacy = stats.get("legacy_rescore") or {}
    if legacy and legacy.get("picked", 0) > 0:
        lines.append("")
        lines.append(
            "Legacy 重评分：拾取 {picked} 篇, 升级 {upgraded}, 降级 {downgraded}, 维持 {unchanged}, 失败 {failed}".format(
                picked=legacy.get("picked", 0),
                upgraded=legacy.get("upgraded", 0),
                downgraded=legacy.get("downgraded", 0),
                unchanged=legacy.get("unchanged", 0),
                failed=legacy.get("failed", 0),
            )
        )
    lines.append("")
    fetched = stats.get("fetched", 0)
    reasons = []
    if fetched == 0:
        reasons.append("所有数据源均未返回结果，请检查网络连通性和 API 可用性。")
    else:
        if stats.get("cache_hit", 0) > 0 and stats.get("analyzed", 0) == 0:
            reasons.append("今日候选主要来自历史缓存结果，未触发新的 AI 分析。")
        if stats.get("first_seen", 0) == 0 and stats.get("seen_before", 0) > 0:
            reasons.append("今日候选论文几乎全部在历史中见过，候选集合高度重复。")
        if stats.get("too_old", 0) > fetched * 0.5:
            reasons.append("大量论文因日期过旧被过滤，可考虑增大 DAYS_BACK。")
        if stats.get("below_min_relevance", 0) > 0:
            reasons.append(f"有 {stats.get('below_min_relevance', 0)} 篇低于相关性阈值，可考虑降低 MIN_RELEVANCE_SCORE。")
        if stats.get("analysis_failed", 0) > 0:
            reasons.append("AI 分析失败较多，请检查 API key 和模型可用性。")
        if stats.get("excluded", 0) > fetched * 0.3:
            reasons.append("大量论文被排除关键词过滤，检查 exclude_keywords 是否过于宽泛。")
        if stats.get("already_reported", 0) > 0:
            reasons.append(f"有 {stats.get('already_reported', 0)} 篇已在之前报告中展示过。")
    if reasons:
        lines.append("可能原因：")
        for r in reasons:
            lines.append(f"  - {r}")
    return lines


def build_email_body(df: pd.DataFrame, today_str: str, top_n: int = 5, stats: dict | None = None) -> str:
    lines = []
    lines.append(f"essay_agent 文献简报｜{today_str}")
    lines.append("")

    if df.empty:
        lines.append("今天没有符合条件的新论文进入最终收录。")
        if stats and stats.get("cache_hit", 0) > 0 and stats.get("analyzed", 0) == 0:
            lines.append("今日候选主要来自历史缓存结果,未触发新的 AI 分析。")
        lines.append("")
        lines.extend(_format_stats_diagnostic(stats))
        return "\n".join(lines)

    lines.append(f"今日最终收录：{len(df)} 篇")
    lines.append(f"高相关（>=80分）：{len(df[df['相关性分数'] >= 80])} 篇")
    lines.append(f"数据源：{', '.join(sorted(df['source'].dropna().unique()))}")
    lines.append("")
    lines.append(f"TOP {top_n} 论文概览")
    lines.append("-" * 24)

    top_df = df.sort_values(by=["相关性分数", "published_date"], ascending=[False, False]).head(top_n)
    for idx, (_, row) in enumerate(top_df.iterrows(), start=1):
        version = row.get("scoring_version", SCORING_VERSION_V1) if "scoring_version" in row else SCORING_VERSION_V1
        lines.append(f"{idx}. {row['title']}")
        lines.append(
            f"   来源：{row['source']}｜日期：{row['published_date']}｜分数：{row['相关性分数']}｜评分版本：{version}"
        )
        lines.append(f"   链接：{row['url']}")
        lines.append(f"   中文摘要：{row['中文摘要']}")
        lines.append(f"   启发：{row['可借鉴启发']}")
        judge_text = row.get("Judge评语", "") if "Judge评语" in row else ""
        if judge_text:
            lines.append(f"   Judge评语：{judge_text}")
        skeptic_text = row.get("Skeptic质疑", "") if "Skeptic质疑" in row else ""
        if skeptic_text:
            lines.append(f"   Skeptic质疑：{skeptic_text}")
        lines.append("")

    lines.append("附件中包含完整 Markdown、Excel 和运行统计。")
    return "\n".join(lines)


def parse_recipients(value: str) -> list[str]:
    if not value:
        return []
    parts = [v.strip() for v in value.split(",")]
    return [p for p in parts if p]


def send_email_via_brevo(runtime: dict, subject: str, body: str, attachments: list[str] | None = None):
    attachments = attachments or []
    required = ["email_username", "email_password", "email_from", "email_to"]
    missing = [k for k in required if not runtime.get(k)]
    if missing:
        raise ValueError(f"邮件推送缺少必要环境变量:{', '.join(missing)}")

    recipients = parse_recipients(runtime["email_to"])
    if not recipients:
        raise ValueError("EMAIL_TO 没有可用收件人")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = runtime["email_from"]
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    for file_path in attachments:
        if not file_path or not os.path.exists(file_path):
            continue
        with open(file_path, "rb") as f:
            data = f.read()
        filename = os.path.basename(file_path)
        maintype = "application"
        subtype = "octet-stream"
        if filename.endswith(".md"):
            maintype, subtype = "text", "markdown"
        elif filename.endswith(".xlsx"):
            maintype, subtype = "application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif filename.endswith(".json"):
            maintype, subtype = "application", "json"
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    with smtplib.SMTP(runtime["email_smtp_host"], runtime["email_smtp_port"], timeout=30) as server:
        if runtime.get("email_use_tls", True):
            server.starttls()
        server.login(runtime["email_username"], runtime["email_password"])
        server.send_message(msg)


def write_markdown(md_path: str, df: pd.DataFrame, today_str: str, report_top_n: int = 10, stats: dict | None = None):
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 文献简报({today_str})\n\n")

        if df.empty:
            f.write(human_summary_for_empty_report(stats) + "\n\n")
            for line in _format_stats_diagnostic(stats):
                f.write(f"{line}\n")
            return

        f.write("## 概览\n\n")
        f.write(f"- 今日最终收录：{len(df)} 篇\n")
        f.write(f"- 高相关（>=80分）：{len(df[df['相关性分数'] >= 80])} 篇\n")
        f.write(f"- 中高相关（>=60分）：{len(df[df['相关性分数'] >= 60])} 篇\n")
        f.write(f"- 数据源：{', '.join(sorted(df['source'].dropna().unique()))}\n\n")

        top_df = df.sort_values(by=["相关性分数", "published_date"], ascending=[False, False]).head(report_top_n)
        f.write(f"## TOP {report_top_n} 优先关注\n\n")
        for idx, (_, row) in enumerate(top_df.iterrows(), start=1):
            f.write(f"### {idx}. {row['title']}\n\n")
            f.write(f"- 分数:{row['相关性分数']}\n")
            version = row.get("scoring_version", SCORING_VERSION_V1) if "scoring_version" in row else SCORING_VERSION_V1
            f.write(f"- 评分版本：{version}\n")
            f.write(f"- 来源：{row['source']}\n")
            f.write(f"- 分组:{row['query_name']}\n")
            f.write(f"- 链接：{row['url']}\n")
            f.write(f"- 中文摘要：{row['中文摘要']}\n")
            f.write(f"- 可借鉴启发：{row['可借鉴启发']}\n")
            judge_text = row.get("Judge评语", "") if "Judge评语" in row else ""
            if judge_text:
                f.write(f"- Judge评语：{judge_text}\n")
            skeptic_text = row.get("Skeptic质疑", "") if "Skeptic质疑" in row else ""
            if skeptic_text:
                f.write(f"- Skeptic质疑：{skeptic_text}\n")
            f.write("\n")

        grouped = df.sort_values(by=["query_name", "相关性分数"], ascending=[True, False]).groupby("query_name")
        for group_name, sub_df in grouped:
            f.write(f"## 分组:{group_name}\n\n")
            for _, row in sub_df.iterrows():
                f.write(f"### {row['title']}\n\n")
                f.write(f"- 来源：{row['source']}\n")
                f.write(f"- 日期:{row['published_date']}\n")
                f.write(f"- 作者:{row['authors']}\n")
                f.write(f"- 分类:{row['primary_category']}\n")
                f.write(f"- 链接：{row['url']}\n")
                f.write(f"- 中文摘要：{row['中文摘要']}\n")
                f.write(f"- 英文摘要:{truncate_text(str(row['english_abstract']), 1200)}\n")
                f.write(f"- 研究主题:{row['研究主题']}\n")
                f.write(f"- 空间/场景类型:{row['空间/场景类型']}\n")
                f.write(f"- 研究场景:{row['研究场景']}\n")
                f.write(f"- 自变量:{row['自变量']}\n")
                f.write(f"- 因变量:{row['因变量']}\n")
                f.write(f"- 行为指标:{row['行为指标']}\n")
                f.write(f"- 生理/感知指标:{row['生理/感知指标']}\n")
                f.write(f"- 研究方法:{row['研究方法']}\n")
                f.write(f"- 数据/样本:{row['数据/样本']}\n")
                f.write(f"- 主要结论:{row['主要结论']}\n")
                f.write(f"- 相关性:{row['与建筑/体育空间/疗愈环境研究相关性']}\n")
                f.write(f"- 相关性分数:{row['相关性分数']}\n")
                version = row.get("scoring_version", SCORING_VERSION_V1) if "scoring_version" in row else SCORING_VERSION_V1
                f.write(f"- 评分版本：{version}\n")
                f.write(f"- 可借鉴启发：{row['可借鉴启发']}\n")
                judge_text = row.get("Judge评语", "") if "Judge评语" in row else ""
                if judge_text:
                    f.write(f"- Judge评语：{judge_text}\n")
                skeptic_text = row.get("Skeptic质疑", "") if "Skeptic质疑" in row else ""
                if skeptic_text:
                    f.write(f"- Skeptic质疑：{skeptic_text}\n")
                f.write("\n")


def main():
    start_time = time.time()
    logger.info("essay_agent started")

    config = load_config("config.yaml")
    client, runtime = load_env()

    output_dir = config.get("output_dir", "output")
    output_prefix = config.get("output_prefix", "essay_daily")
    max_chars_per_paper = config.get("max_chars_per_paper", 6000)
    openai_model = runtime["openai_model"]
    days_back = runtime["days_back"]
    max_results_per_query = runtime["max_results_per_query"]
    queries = config.get("queries", {})
    generic_queries = config.get("generic_queries", {})
    exclude_keywords = config.get("exclude_keywords", [])
    must_have_keywords = config.get("must_have_keywords", [])
    db_path = config.get("db_path", DB_PATH)
    analysis_retries = config.get("analysis_retries", 3)
    retry_delay_seconds = config.get("retry_delay_seconds", 3)
    min_relevance_score = runtime["min_relevance_score"]
    force_refresh = runtime["force_refresh"]
    sources = config.get("sources", ["arxiv"])

    ensure_output_dir(output_dir)
    conn = init_db(db_path)
    migrate_db(conn)

    legacy_rescore_stats = {"picked": 0, "upgraded": 0, "downgraded": 0, "unchanged": 0, "failed": 0}
    if runtime.get("legacy_rescore_enabled", True) and runtime.get("scoring_mode", "multi") == "multi":
        rescore_limit = int(runtime.get("legacy_rescore_per_run", 30))
        if rescore_limit > 0:
            logger.info("[legacy rescore] 启动渐进式重评分，上限 %d 篇", rescore_limit)
            legacy_rescore_stats = rescore_legacy_batch(
                conn=conn,
                client=client,
                runtime=runtime,
                limit=rescore_limit,
                max_chars_per_paper=max_chars_per_paper,
            )
            logger.info(
                "[legacy rescore] 完成: picked=%d upgraded=%d downgraded=%d unchanged=%d failed=%d",
                legacy_rescore_stats["picked"],
                legacy_rescore_stats["upgraded"],
                legacy_rescore_stats["downgraded"],
                legacy_rescore_stats["unchanged"],
                legacy_rescore_stats["failed"],
            )

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    all_rows = []
    today_new_rows = []
    seen_urls = set()
    seen_keys = set()
    stats = {
        "fetched": 0,
        "too_old": 0,
        "duplicate": 0,
        "excluded": 0,
        "must_have_filtered": 0,
        "first_seen": 0,
        "seen_before": 0,
        "cache_hit": 0,
        "cache_refresh": 0,
        "analyzed": 0,
        "analysis_success": 0,
        "analysis_failed": 0,
        "below_min_relevance": 0,
        "already_reported": 0,
        "kept": 0,
        "source_details": {},
        "legacy_rescore": legacy_rescore_stats,
    }

    for query_name, query_text in queries.items():
        logger.info("正在抓取 query：%s", query_name)

        for source_name in sources:
            source_key = f"{source_name}/{query_name}"
            effective_query = resolve_query_for_source(source_name, query_name, queries, generic_queries)
            logger.info("  来源：%s", source_name)
            logger.info("  使用检索式：%s", effective_query[:160])
            try:
                source_items = fetch_source_results(source_name, effective_query, max_results_per_query)
            except Exception as e:
                logger.exception("抓取 %s 失败", source_key)
                stats["source_details"][source_key] = {"fetched": 0, "error": str(e)}
                continue
            stats["source_details"][source_key] = {"fetched": len(source_items), "error": ""}

            # Rate limiting between API calls
            if source_name == "semantic_scholar":
                time.sleep(3)
            elif source_name != "arxiv":
                time.sleep(1.5)

            for item in source_items:
                stats["fetched"] += 1
                title = (item.get("title") or "").strip()
                abstract = (item.get("abstract") or "").strip()
                url = item.get("url") or ""
                published = item.get("published")

                if not url or not title or not published:
                    continue
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)

                if published < cutoff_date:
                    stats["too_old"] += 1
                    continue

                dedupe_key = ("doi", item.get("doi")) if item.get("doi") else ("url", url)
                if dedupe_key in seen_keys or url in seen_urls:
                    stats["duplicate"] += 1
                    continue

                combined_text = f"{title}\n{abstract}"

                if exclude_keywords and contains_excluded_keyword(combined_text, exclude_keywords):
                    stats["excluded"] += 1
                    continue

                if not contains_must_have_keyword(combined_text, must_have_keywords):
                    stats["must_have_filtered"] += 1
                    continue

                seen_urls.add(url)
                seen_keys.add(dedupe_key)
                short_abstract = truncate_text(abstract, max_chars_per_paper)
                content_hash = hashlib.sha256(f"{title}\n{short_abstract}".encode("utf-8", errors="ignore")).hexdigest()

                record = get_paper_record(conn, url, item.get("doi", ""))
                if record:
                    stats["seen_before"] += 1
                else:
                    stats["first_seen"] += 1
                cached = None
                refresh_cache = False
                if record and record.get("content_hash") == content_hash:
                    refresh_cache = should_refresh_cached_analysis(record, runtime)
                    if not refresh_cache:
                        cached = get_cached_analysis(conn, url, item.get("doi", ""))
                if cached:
                    analysis = cached
                    stats["cache_hit"] += 1
                else:
                    if refresh_cache:
                        stats["cache_refresh"] += 1
                    analysis = analyze_paper_dispatch(
                        client=client,
                        runtime=runtime,
                        title=title,
                        abstract=short_abstract,
                    )
                    stats["analyzed"] += 1

                if analysis.get("分析状态") == "failed" or str(analysis.get("原始分析", "")).startswith("分析失败"):
                    stats["analysis_failed"] += 1
                else:
                    stats["analysis_success"] += 1

                row = result_to_row(query_name, item, analysis)
                meets_threshold = row["相关性分数"] >= min_relevance_score
                eligible_for_pending = analysis.get("分析状态") == "success" and meets_threshold

                upsert_paper(
                    conn=conn,
                    source=item["source"],
                    url=url,
                    doi=item.get("doi", ""),
                    title=title,
                    english_abstract=abstract,
                    chinese_summary=analysis.get("中文摘要", ""),
                    published_date=published.strftime("%Y-%m-%d"),
                    query_name=query_name,
                    authors=item.get("authors", []),
                    primary_category=item.get("primary_category", ""),
                    categories=item.get("categories", []),
                    analysis=analysis,
                    meets_threshold=meets_threshold,
                    eligible_for_pending=eligible_for_pending,
                    content_hash=content_hash,
                    analyzed_at=datetime.now().isoformat(timespec="seconds") if not cached else None,
                )

                if not meets_threshold:
                    stats["below_min_relevance"] += 1
                    continue

                if was_displayed(conn, url, item.get("doi", "")) or was_reported(conn, url, item.get("doi", "")):
                    stats["already_reported"] += 1
                    continue

                stats["kept"] += 1
                today_new_rows.append(row)

            # Batch commit per source-query instead of per paper
            conn.commit()

    # --- 顶刊监控 ---
    target_journals = config.get("target_journals", [])
    journal_filter_keywords = config.get("journal_filter_keywords", [])
    if target_journals:
        logger.info("正在抓取目标期刊 (%d 本), 关键词预筛: %s ...",
                     len(target_journals), journal_filter_keywords[:5] if journal_filter_keywords else "无")
        journal_items = fetch_journal_papers(
            target_journals, days_back, max_results_per_query,
            relevance_keywords=journal_filter_keywords or None,
        )
        stats["source_details"]["journal"] = {"fetched": len(journal_items), "error": ""}

        for item in journal_items:
            stats["fetched"] += 1
            title = (item.get("title") or "").strip()
            abstract = (item.get("abstract") or "").strip()
            url = item.get("url") or ""
            published = item.get("published")

            if not url or not title or not published:
                continue
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)

            if published < cutoff_date:
                stats["too_old"] += 1
                continue

            dedupe_key = ("doi", item.get("doi")) if item.get("doi") else ("url", url)
            if dedupe_key in seen_keys or url in seen_urls:
                stats["duplicate"] += 1
                continue

            combined_text = f"{title}\n{abstract}"

            if exclude_keywords and contains_excluded_keyword(combined_text, exclude_keywords):
                stats["excluded"] += 1
                continue

            seen_urls.add(url)
            seen_keys.add(dedupe_key)
            short_abstract = truncate_text(abstract, max_chars_per_paper)
            content_hash = hashlib.sha256(f"{title}\n{short_abstract}".encode("utf-8", errors="ignore")).hexdigest()

            record = get_paper_record(conn, url, item.get("doi", ""))
            if record:
                stats["seen_before"] += 1
            else:
                stats["first_seen"] += 1
            cached = None
            refresh_cache = False
            if record and record.get("content_hash") == content_hash:
                refresh_cache = should_refresh_cached_analysis(record, runtime)
                if not refresh_cache:
                    cached = get_cached_analysis(conn, url, item.get("doi", ""))
            if cached:
                analysis = cached
                stats["cache_hit"] += 1
            else:
                if refresh_cache:
                    stats["cache_refresh"] += 1
                analysis = analyze_paper_dispatch(
                    client=client,
                    runtime=runtime,
                    title=title,
                    abstract=short_abstract,
                )
                stats["analyzed"] += 1

            if analysis.get("分析状态") == "failed" or str(analysis.get("原始分析", "")).startswith("分析失败"):
                stats["analysis_failed"] += 1
            else:
                stats["analysis_success"] += 1

            journal_name = item.get("primary_category", "journal")
            row = result_to_row(journal_name, item, analysis)
            meets_threshold = row["相关性分数"] >= min_relevance_score
            eligible_for_pending = analysis.get("分析状态") == "success" and meets_threshold

            upsert_paper(
                conn=conn,
                source=item["source"],
                url=url,
                doi=item.get("doi", ""),
                title=title,
                english_abstract=abstract,
                chinese_summary=analysis.get("中文摘要", ""),
                published_date=published.strftime("%Y-%m-%d"),
                query_name=journal_name,
                authors=item.get("authors", []),
                primary_category=item.get("primary_category", ""),
                categories=item.get("categories", []),
                analysis=analysis,
                meets_threshold=meets_threshold,
                eligible_for_pending=eligible_for_pending,
                content_hash=content_hash,
                analyzed_at=datetime.now().isoformat(timespec="seconds") if not cached else None,
            )

            if not meets_threshold:
                stats["below_min_relevance"] += 1
                continue

            if was_displayed(conn, url, item.get("doi", "")) or was_reported(conn, url, item.get("doi", "")):
                stats["already_reported"] += 1
                continue

            stats["kept"] += 1
            today_new_rows.append(row)

        conn.commit()

    today_str = datetime.now().strftime("%Y-%m-%d")
    excel_path = os.path.join(output_dir, f"{output_prefix}_{today_str}.xlsx")
    md_path = os.path.join(output_dir, f"{output_prefix}_{today_str}.md")
    stats_path = os.path.join(output_dir, f"{output_prefix}_{today_str}_stats.json")

    all_rows = list(today_new_rows)
    target_size = max(runtime.get("report_top_n", 10), runtime.get("email_top_n", 5))
    if len(all_rows) < target_size:
        pending_pool = load_pending_pool(conn, runtime.get("pending_pool_days", 7), target_size - len(all_rows) + 10)
        if pending_pool:
            existing_keys = {(r.get('doi') or '', r.get('url')) for r in all_rows}
            for prow in pending_pool:
                key = (prow.get('doi') or '', prow.get('url'))
                if key in existing_keys:
                    continue
                all_rows.append(prow)
                existing_keys.add(key)
                if len(all_rows) >= target_size:
                    break

    df = pd.DataFrame(all_rows)

    if not df.empty:
        df = df.sort_values(by=["相关性分数", "published_date"], ascending=[False, False])
        df.to_excel(excel_path, index=False)

    write_markdown(md_path, df, today_str, runtime.get("report_top_n", 10), stats=stats)

    if not df.empty:
        mark_displayed(conn, df["url"].tolist(), df.get("doi", pd.Series(dtype=str)).fillna("").tolist())

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    if runtime.get("email_enabled") and (not df.empty or runtime.get("empty_report_email", True)):
        try:
            email_subject = f"[essay_agent] 文献简报 {today_str}｜收录 {len(df)} 篇"
            email_body = build_email_body(df, today_str, runtime.get("email_top_n", 5), stats=stats)
            send_email_via_brevo(
                runtime=runtime,
                subject=email_subject,
                body=email_body,
                attachments=[md_path, excel_path if not df.empty else "", stats_path],
            )
            if not df.empty:
                mark_reported(conn, df["url"].tolist(), df.get("doi", pd.Series(dtype=str)).fillna("").tolist())
            logger.info("邮件推送已发送。")
        except Exception:
            logger.exception("邮件推送失败")

    if df.empty:
        logger.info("没有抓到符合条件的新论文。")
    else:
        logger.info("已生成 Excel：%s", excel_path)
    logger.info("已生成 Markdown：%s", md_path)
    removed_outputs = cleanup_old_outputs(output_dir, int(os.getenv("OUTPUT_RETENTION_DAYS", "30")))
    if removed_outputs > 0:
        logger.info("已清理旧输出文件：%d 个", removed_outputs)
    logger.info("已生成统计：%s", stats_path)
    logger.info("运行统计：%s", stats)
    elapsed = time.time() - start_time
    logger.info("总耗时：%.1f 秒（%.1f 分钟）", elapsed, elapsed / 60)


if __name__ == "__main__":
    main()
