#!/usr/bin/env python3
"""send_output_email.py

Send an essay_agent daily report email using EXISTING output files (xlsx/md/stats),
without re-running fetch/analyze.

- Email body format matches essay_agent.py::build_email_body()
- Optional: reset DB displayed/reported flags (ALL) before sending (testing)
- Optional: after successful send, mark DB displayed+reported for rows in the XLSX

Run inside /root/essay_agent (needs .env, config.yaml, papers.db, output/...).

Examples:
  python3 send_output_email.py --mark-db
  python3 send_output_email.py --reset-all-flags --mark-db
  python3 send_output_email.py --date 2026-03-08 --mark-db
"""

import argparse
import os
import smtplib
import mimetypes
import sqlite3
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage

import pandas as pd

try:
    import yaml
except Exception:
    yaml = None


def load_env_file(path: str = ".env") -> dict:
    env = {}
    p = Path(path)
    if not p.exists():
        return env
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        env[k] = v
    return env


def need(env: dict, k: str) -> str:
    v = (env.get(k) or "").strip()
    if not v:
        raise SystemExit(f"Missing {k} in .env")
    return v


def parse_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_recipients(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def load_config_yaml(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists() or yaml is None:
        return {}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


# === Match essay_agent.py::build_email_body ===
def build_email_body(df: pd.DataFrame, today_str: str, top_n: int = 5) -> str:
    lines: list[str] = []
    lines.append(f"essay_agent 文献简报｜{today_str}")
    lines.append("")

    if df is None or df.empty:
        lines.append("今天没有符合条件的新论文进入最终收录。")
        lines.append("可检查抓取窗口、相关性阈值、数据源配置或 API 调用情况。")
        return "\n".join(lines)

    lines.append(f"今日最终收录：{len(df)} 篇")
    lines.append(f"高相关（>=80分）：{len(df[df['相关性分数'] >= 80])} 篇")
    lines.append(f"数据源：{', '.join(sorted(df['source'].dropna().unique()))}")
    lines.append("")
    lines.append(f"TOP {top_n} 论文概览")
    lines.append("-" * 24)

    top_df = df.sort_values(by=["相关性分数", "published_date"], ascending=[False, False]).head(top_n)
    for idx, (_, row) in enumerate(top_df.iterrows(), start=1):
        lines.append(f"{idx}. {row['title']}")
        lines.append(f"   来源：{row['source']}｜日期：{row['published_date']}｜分数：{row['相关性分数']}")
        lines.append(f"   链接：{row['url']}")
        lines.append(f"   中文摘要：{row['中文摘要']}")
        lines.append(f"   启发：{row['可借鉴启发']}")
        lines.append("")

    lines.append("附件中包含完整 Markdown、Excel 和运行统计。")
    return "\n".join(lines)


def guess_paths(cfg: dict, date_str: str):
    output_dir = cfg.get("output_dir", "output")
    prefix = cfg.get("output_prefix", "arxiv_daily")
    xlsx = os.path.join(output_dir, f"{prefix}_{date_str}.xlsx")
    md = os.path.join(output_dir, f"{prefix}_{date_str}.md")
    stats = os.path.join(output_dir, f"{prefix}_{date_str}_stats.json")
    return xlsx, md, stats


def attach_file(msg: EmailMessage, path: str):
    if not path or not os.path.exists(path):
        return
    data = Path(path).read_bytes()
    ctype, _ = mimetypes.guess_type(path)
    if not ctype:
        ctype = "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=os.path.basename(path))


def reset_all_flags(conn: sqlite3.Connection):
    conn.execute(
        "UPDATE papers SET reported_at = NULL, report_count = 0, displayed_at = NULL, display_count = 0"
    )
    conn.commit()


def mark_from_xlsx(conn: sqlite3.Connection, df: pd.DataFrame):
    if df is None or df.empty:
        return

    now = datetime.now().isoformat(timespec="seconds")

    urls = []
    dois = []
    if "url" in df.columns:
        urls = [str(u).strip() for u in df["url"].fillna("").tolist() if str(u).strip()]
    if "doi" in df.columns:
        dois = [str(d).strip().lower() for d in df["doi"].fillna("").tolist() if str(d).strip()]

    cur = conn.cursor()

    if urls:
        cur.executemany(
            """
            UPDATE papers
            SET displayed_at = ?, display_count = COALESCE(display_count,0)+1,
                reported_at  = ?, report_count  = COALESCE(report_count,0)+1,
                updated_at   = ?
            WHERE url = ?
            """,
            [(now, now, now, u) for u in urls],
        )

    if dois:
        cur.executemany(
            """
            UPDATE papers
            SET displayed_at = ?, display_count = COALESCE(display_count,0)+1,
                reported_at  = ?, report_count  = COALESCE(report_count,0)+1,
                updated_at   = ?
            WHERE lower(doi) = ?
            """,
            [(now, now, now, d) for d in dois],
        )

    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument(
        "--reset-all-flags",
        action="store_true",
        help="清空 DB 所有 displayed/reported 标记（危险，用于测试）",
    )
    ap.add_argument(
        "--mark-db",
        action="store_true",
        help="发送成功后，把本次 xlsx 对应条目标记回 displayed+reported",
    )
    ap.add_argument("--dry-run", action="store_true", help="只打印将发送的信息，不实际发邮件")
    args = ap.parse_args()

    env = load_env_file(".env")
    cfg = load_config_yaml("config.yaml")

    # Locate files
    xlsx_path, md_path, stats_path = guess_paths(cfg, args.date)
    if not os.path.exists(xlsx_path):
        raise SystemExit(f"XLSX 不存在：{xlsx_path}")

    df = pd.read_excel(xlsx_path).fillna("")

    # Email content (match main program)
    subject = f"[essay_agent] 文献简报 {args.date}｜收录 {len(df)} 篇"
    top_n = int((env.get("EMAIL_TOP_N") or "5").strip())
    body = build_email_body(df, args.date, top_n=top_n)

    # SMTP
    host = (env.get("EMAIL_SMTP_HOST") or "smtp-relay.brevo.com").strip()
    port = int((env.get("EMAIL_SMTP_PORT") or "587").strip())
    username = need(env, "EMAIL_USERNAME")
    password = need(env, "EMAIL_PASSWORD")
    email_from = need(env, "EMAIL_FROM")
    recipients = parse_recipients(need(env, "EMAIL_TO"))
    use_tls = parse_bool(env.get("EMAIL_USE_TLS", "true"), True)

    attachments = [p for p in [md_path, xlsx_path, stats_path] if p and os.path.exists(p)]

    if args.dry_run:
        print("DRY RUN")
        print("Subject:", subject)
        print("From:", email_from)
        print("To:", recipients)
        print("Attachments:", attachments)
        print("Body preview:\n", body[:800])
        return

    # DB ops (optional)
    db_path = cfg.get("db_path") or env.get("DB_PATH") or "papers.db"
    conn = None
    if args.reset_all_flags or args.mark_db:
        if not os.path.exists(db_path):
            raise SystemExit(f"DB 不存在：{db_path}")
        conn = sqlite3.connect(db_path)
        if args.reset_all_flags:
            reset_all_flags(conn)
            print("OK: db flags cleared (ALL displayed/reported reset)")

    # Build email
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    for p in attachments:
        attach_file(msg, p)

    # Send
    with smtplib.SMTP(host, port, timeout=30) as s:
        if use_tls:
            s.starttls()
        s.login(username, password)
        s.send_message(msg)

    print("OK: email sent")

    # Mark DB after successful send
    if conn is not None and args.mark_db:
        mark_from_xlsx(conn, df)
        print("OK: db marked displayed+reported for rows in xlsx")

    if conn is not None:
        conn.close()


if __name__ == "__main__":
    main()
