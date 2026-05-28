from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_MODE = "essay-agent"
DEFAULT_INDEX_PATH = os.path.join(ROOT_DIR, "docs", "essay-agent-reader-index.json")


def _norm(value: Any) -> str:
    return str(value or "").strip()


def parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_int(value: Any, default: int) -> int:
    try:
        parsed = int(str(value).strip())
        return parsed if parsed >= 0 else default
    except Exception:
        return default


def date_token(value: str) -> str:
    text = _norm(value)
    if re.fullmatch(r"\d{8}", text):
        return text
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text.replace("-", "")
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def slugify(value: str) -> str:
    text = _norm(value).lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9\-]+", "", text)
    return text or "paper"


def stable_source_paper_id(row: dict[str, Any]) -> str:
    doi = _norm(row.get("doi")).lower()
    if doi:
        return "doi:" + doi
    source = _norm(row.get("source")).lower() or "essay-agent"
    url = _norm(row.get("url") or row.get("link"))
    if url:
        return f"{source}:{url}"
    title = _norm(row.get("title")).lower()
    published = _norm(row.get("published_date") or row.get("published"))
    return f"{source}:{published}:{title}"


def stable_reader_id(row: dict[str, Any]) -> str:
    key = stable_source_paper_id(row)
    digest = hashlib.sha1(key.encode("utf-8", errors="ignore")).hexdigest()[:12]
    source = slugify(_norm(row.get("source")) or "essay-agent")[:20]
    return f"essay-agent-{source}-{digest}"


def score_to_10(value: Any) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.0
    score = max(0.0, min(100.0, score))
    return round(score / 10.0, 2)


def normalize_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_norm(item) for item in value if _norm(item)]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [_norm(item) for item in parsed if _norm(item)]
        except Exception:
            pass
        return [part.strip() for part in re.split(r";|,|，", text) if part.strip()]
    return []


def analysis_from_row(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("analysis")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    out: dict[str, Any] = {}
    for key in [
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
        "与建筑/体育空间/疗愈环境研究相关性",
        "与建筑/体育空间研究相关性",
        "相关性分数",
        "可借鉴启发",
    ]:
        if key in row and row.get(key) not in (None, ""):
            out[key] = row.get(key)
    return out


def row_score(row: dict[str, Any]) -> float:
    for key in ("相关性分数", "domain_relevance_score", "related_score"):
        if key in row:
            try:
                return float(row.get(key) or 0)
            except Exception:
                return 0.0
    analysis = analysis_from_row(row)
    if "相关性分数" in analysis:
        try:
            return float(analysis.get("相关性分数") or 0)
        except Exception:
            return 0.0
    return 0.0


def row_date(row: dict[str, Any]) -> str:
    return _norm(row.get("published_date") or row.get("published"))[:10]


def sort_final_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (row_score(row), row_date(row)),
        reverse=True,
    )


def infer_pdf_url(row: dict[str, Any]) -> str:
    link = _norm(row.get("url") or row.get("link"))
    source = _norm(row.get("source")).lower()
    if source == "arxiv" and link:
        if "/abs/" in link:
            return link.replace("/abs/", "/pdf/").replace(".pdf", "")
        if "/pdf/" in link:
            return link.replace(".pdf", "")
    if link.lower().endswith(".pdf") or "/pdf/" in link.lower():
        return link
    return ""


def relation_text(row: dict[str, Any], analysis: dict[str, Any]) -> str:
    return _norm(
        row.get("与建筑/体育空间/疗愈环境研究相关性")
        or row.get("与建筑/体育空间研究相关性")
        or analysis.get("与建筑/体育空间/疗愈环境研究相关性")
        or analysis.get("与建筑/体育空间研究相关性")
    )


def build_recommend_item(row: dict[str, Any]) -> dict[str, Any]:
    analysis = analysis_from_row(row)
    source_id = stable_source_paper_id(row)
    reader_id = stable_reader_id(row)
    source = _norm(row.get("source")) or "essay-agent"
    domain = _norm(row.get("query_name") or row.get("domain_query"))
    score100 = row_score(row)
    summary = _norm(row.get("中文摘要") or row.get("chinese_summary") or analysis.get("中文摘要"))
    inspiration = _norm(row.get("可借鉴启发") or analysis.get("可借鉴启发"))
    relation = relation_text(row, analysis)
    evidence = inspiration or relation or summary
    title = _norm(row.get("title")) or source_id
    link = _norm(row.get("url") or row.get("link"))
    pdf_url = infer_pdf_url(row)
    tags = []
    if domain:
        tags.append(f"query:{domain}")
    if source:
        tags.append(f"paper:{source}")
    return {
        "id": reader_id,
        "paper_id": reader_id,
        "essay_agent_source_id": source_id,
        "source": source,
        "title": title,
        "abstract": _norm(row.get("english_abstract") or row.get("abstract")),
        "published": row_date(row),
        "authors": normalize_authors(row.get("authors")),
        "link": pdf_url or link,
        "pdf_url": pdf_url,
        "doi": _norm(row.get("doi")),
        "primary_category": _norm(row.get("primary_category") or domain),
        "categories": normalize_authors(row.get("categories")),
        "llm_score": score_to_10(score100),
        "domain_relevance_score": score100,
        "canonical_evidence": evidence,
        "llm_tldr_cn": summary,
        "chinese_summary": summary,
        "llm_tags": tags,
        "selection_source": "essay-agent",
        "_essay_agent_analysis": analysis,
        "_essay_agent_relation": relation,
        "_essay_agent_inspiration": inspiration,
    }


def read_final_rows(path: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        return "", [row for row in payload if isinstance(row, dict)], {}
    if not isinstance(payload, dict):
        return "", [], {}
    rows = payload.get("rows")
    if not isinstance(rows, list):
        rows = payload.get("papers")
    if not isinstance(rows, list):
        rows = []
    return _norm(payload.get("date")), [row for row in rows if isinstance(row, dict)], payload


def build_recommend_payload(
    rows: list[dict[str, Any]],
    *,
    top_n: int,
    deep_top_n: int,
    date: str,
    mode: str = DEFAULT_MODE,
) -> dict[str, Any]:
    ordered = sort_final_rows(rows)
    if top_n > 0:
        ordered = ordered[:top_n]
    items = [build_recommend_item(row) for row in ordered]
    deep_count = max(0, min(int(deep_top_n), len(items)))
    return {
        "date": date,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "essay-agent",
        "deep_dive": items[:deep_count],
        "quick_skim": items[deep_count:],
    }


def recommend_path_for_date(date8: str, mode: str = DEFAULT_MODE) -> str:
    return os.path.join(ROOT_DIR, "archive", date8, "recommend", f"arxiv_papers_{date8}.{mode}.json")


def write_recommend_payload(payload: dict[str, Any], path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def route_for_item(date8: str, item: dict[str, Any]) -> str:
    title = _norm(item.get("title"))
    paper_id = _norm(item.get("id") or item.get("paper_id"))
    basename = f"{paper_id}-{slugify(title)}" if paper_id else slugify(title)
    return f"{date8[:6]}/{date8[6:]}/{basename}"


def update_reader_index(payload: dict[str, Any], *, date8: str, index_path: str) -> str:
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        except Exception:
            index = {}
    else:
        index = {}
    if not isinstance(index, dict):
        index = {}

    papers = index.get("papers") if isinstance(index.get("papers"), dict) else {}
    routes = index.get("routes") if isinstance(index.get("routes"), dict) else {}

    for section in ("deep_dive", "quick_skim"):
        for item in payload.get(section) or []:
            if not isinstance(item, dict):
                continue
            source_id = _norm(item.get("essay_agent_source_id"))
            if not source_id:
                continue
            route = route_for_item(date8, item)
            record = {
                "route": route,
                "title": _norm(item.get("title")),
                "source": _norm(item.get("source")),
                "score": item.get("domain_relevance_score"),
                "section": section,
                "date": date8,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            papers[source_id] = record
            routes[source_id] = route
            doi = _norm(item.get("doi")).lower()
            if doi:
                routes[f"doi:{doi}"] = route
            link = _norm(item.get("link"))
            source = _norm(item.get("source")).lower()
            if link and source:
                routes[f"{source}:{link}"] = route

    index.update(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "papers": papers,
            "routes": routes,
        }
    )
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return index_path


def run_generate_docs(*, date8: str, mode: str, docs_dir: str, fulltext: bool, concurrency: int) -> None:
    env = os.environ.copy()
    if not env.get("SUMMARY_API_KEY"):
        env["SUMMARY_API_KEY"] = env.get("OPENAI_API_KEY") or env.get("DEEPSEEK_API_KEY") or ""
    if not env.get("SUMMARY_BASE_URL"):
        env["SUMMARY_BASE_URL"] = env.get("OPENAI_BASE_URL") or env.get("DEEPSEEK_BASE_URL") or ""
    if not env.get("SUMMARY_MODEL"):
        env["SUMMARY_MODEL"] = env.get("OPENAI_MODEL") or env.get("DEEPSEEK_MODEL") or ""
    cmd = [
        sys.executable,
        os.path.join(ROOT_DIR, "src", "6.generate_docs.py"),
        "--date",
        date8,
        "--mode",
        mode,
        "--docs-dir",
        docs_dir,
        "--docs-concurrency",
        str(max(int(concurrency or 1), 1)),
    ]
    if not fulltext:
        cmd.append("--glance-only")
    subprocess.run(cmd, check=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reader pages from essay-agent final daily papers.")
    parser.add_argument("--final-json", required=True)
    parser.add_argument("--date", default="")
    parser.add_argument("--mode", default=DEFAULT_MODE)
    parser.add_argument("--recommend-path", default="")
    parser.add_argument("--docs-dir", default=os.path.join(ROOT_DIR, "docs"))
    parser.add_argument("--reader-index", default=DEFAULT_INDEX_PATH)
    parser.add_argument("--top-n", type=int, default=-1)
    parser.add_argument("--deep-top-n", type=int, default=-1)
    parser.add_argument("--generate-docs", action="store_true", default=False)
    parser.add_argument("--fulltext", default=os.getenv("ESSAY_AGENT_READER_FULLTEXT", "true"))
    parser.add_argument("--docs-concurrency", type=int, default=parse_int(os.getenv("ESSAY_AGENT_READER_DOCS_CONCURRENCY"), 2))
    args = parser.parse_args()

    payload_date, rows, _payload = read_final_rows(args.final_json)
    date8 = date_token(args.date or payload_date)
    report_top_n = parse_int(os.getenv("REPORT_TOP_N"), 10)
    email_top_n = parse_int(os.getenv("EMAIL_TOP_N"), 5)
    top_n = args.top_n if args.top_n >= 0 else parse_int(os.getenv("ESSAY_AGENT_READER_TOP_N"), max(report_top_n, email_top_n))
    deep_top_n = args.deep_top_n if args.deep_top_n >= 0 else parse_int(os.getenv("ESSAY_AGENT_READER_DEEP_TOP_N"), email_top_n)
    recommend = build_recommend_payload(rows, top_n=top_n, deep_top_n=deep_top_n, date=date8, mode=args.mode)
    recommend_path = args.recommend_path or recommend_path_for_date(date8, args.mode)
    write_recommend_payload(recommend, recommend_path)
    print(f"[essay-agent-reader] recommend={recommend_path}", flush=True)

    if args.generate_docs:
        run_generate_docs(
            date8=date8,
            mode=args.mode,
            docs_dir=args.docs_dir,
            fulltext=parse_bool(args.fulltext, True),
            concurrency=args.docs_concurrency,
        )

    index_path = update_reader_index(recommend, date8=date8, index_path=args.reader_index)
    print(f"[essay-agent-reader] index={index_path}", flush=True)


if __name__ == "__main__":
    main()
