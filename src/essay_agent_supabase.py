from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any

import requests

SRC_DIR = os.path.abspath(os.path.dirname(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    from maintain.sync import (
        attach_embeddings,
        configure_local_embedding_runtime,
        deduplicate_rows_by_id,
        resolve_embed_devices,
        resolve_embed_model,
        to_pgvector_literal,
        upsert_papers,
    )
except Exception:  # pragma: no cover
    from src.maintain.sync import (
        attach_embeddings,
        configure_local_embedding_runtime,
        deduplicate_rows_by_id,
        resolve_embed_devices,
        resolve_embed_model,
        to_pgvector_literal,
        upsert_papers,
    )


DEFAULT_TABLE = "essay_agent_papers"
DEFAULT_RUNS_TABLE = "essay_agent_daily_runs"
DEFAULT_BACKUP_DIR = os.path.join(os.path.abspath(os.path.join(SRC_DIR, "..")), "archive", "essay-agent")


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _headers(service_key: str, prefer: str | None = None, schema: str = "public") -> dict[str, str]:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    if schema:
        headers["Accept-Profile"] = schema
        headers["Content-Profile"] = schema
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _rest_url(url: str) -> str:
    return _norm(url).rstrip("/") + "/rest/v1"


def parse_json_field(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    text = _norm(value)
    if not text:
        return fallback
    try:
        return json.loads(text)
    except Exception:
        return fallback


def stable_paper_id(row: dict[str, Any]) -> str:
    doi = _norm(row.get("doi")).lower()
    if doi:
        return "doi:" + doi
    source = _norm(row.get("source")).lower() or "essay-agent"
    url = _norm(row.get("url"))
    if url:
        return f"{source}:{url}"
    title = _norm(row.get("title")).lower()
    published = _norm(row.get("published_date"))
    return f"{source}:{published}:{title}"


def iso_date(value: Any) -> str | None:
    text = _norm(value)
    if not text:
        return None
    if len(text) == 10:
        return text + "T00:00:00+00:00"
    return text


def load_sqlite_papers(db_path: str) -> list[dict[str, Any]]:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"essay-agent SQLite database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            select
              url, doi, source, title, english_abstract, chinese_summary,
              published_date, query_name, authors, primary_category, categories,
              analysis_json, related_score, analysis_status, meets_threshold,
              eligible_for_pending, first_seen_at, last_seen_at, displayed_at,
              display_count, reported_at, report_count, content_hash, created_at,
              updated_at
            from papers
            order by published_date desc, updated_at desc
            """
        ).fetchall()
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for raw in rows:
        item = dict(raw)
        analysis = parse_json_field(item.get("analysis_json"), {})
        authors = parse_json_field(item.get("authors"), [])
        categories = parse_json_field(item.get("categories"), [])
        if isinstance(authors, str):
            authors = [x.strip() for x in authors.split(";") if x.strip()]
        if isinstance(categories, str):
            categories = [x.strip() for x in categories.split(";") if x.strip()]
        paper_id = stable_paper_id(item)
        out.append(
            {
                "id": paper_id,
                "source": _norm(item.get("source")) or "essay-agent",
                "source_paper_id": _norm(item.get("url")),
                "doi": _norm(item.get("doi")) or None,
                "version": None,
                "title": _norm(item.get("title")),
                "abstract": _norm(item.get("english_abstract")),
                "authors": authors if isinstance(authors, list) else [],
                "primary_category": _norm(item.get("primary_category")) or _norm(item.get("query_name")) or None,
                "categories": categories if isinstance(categories, list) else [],
                "published": iso_date(item.get("published_date")),
                "link": _norm(item.get("url")) or None,
                "analysis": analysis if isinstance(analysis, dict) else {},
                "chinese_summary": _norm(item.get("chinese_summary"))
                or _norm((analysis or {}).get("中文摘要") if isinstance(analysis, dict) else ""),
                "domain_query": _norm(item.get("query_name")),
                "domain_relevance_score": int(item.get("related_score") or 0),
                "analysis_status": _norm(item.get("analysis_status")),
                "meets_threshold": bool(item.get("meets_threshold")),
                "eligible_for_pending": bool(item.get("eligible_for_pending")),
                "displayed_at": _norm(item.get("displayed_at")) or None,
                "reported_at": _norm(item.get("reported_at")) or None,
                "content_hash": _norm(item.get("content_hash")) or None,
                "essay_agent_meta": {
                    "first_seen_at": item.get("first_seen_at"),
                    "last_seen_at": item.get("last_seen_at"),
                    "display_count": item.get("display_count"),
                    "report_count": item.get("report_count"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                },
                "updated_at": _now_iso(),
            }
        )
    deduped, _duplicates = deduplicate_rows_by_id(out)
    return deduped


def build_embedding_text(row: dict[str, Any]) -> str:
    title = _norm(row.get("title"))
    abstract = _norm(row.get("abstract"))
    summary = _norm(row.get("chinese_summary"))
    if summary:
        return f"passage: Title: {title}\n\nAbstract: {abstract}\n\nChinese summary: {summary}"
    if title and abstract:
        return f"passage: Title: {title}\n\nAbstract: {abstract}"
    return f"passage: {title or abstract}"


def attach_essay_embeddings(
    rows: list[dict[str, Any]],
    *,
    model_name: str,
    devices: list[str],
    batch_size: int,
    max_length: int,
    allow_remote: bool,
) -> int:
    shim_rows = [
        {
            "id": row["id"],
            "title": row.get("title", ""),
            "abstract": build_embedding_text(row),
        }
        for row in rows
    ]
    dim = attach_embeddings(
        shim_rows,
        model_name=model_name,
        devices=devices,
        batch_size=batch_size,
        max_length=max_length,
        allow_remote=allow_remote,
    )
    by_id = {row["id"]: row for row in shim_rows}
    now = _now_iso()
    for row in rows:
        embedded = by_id.get(row["id"], {})
        vector = embedded.get("embedding")
        if vector:
            row["embedding"] = vector if isinstance(vector, str) else to_pgvector_literal(vector)
            row["embedding_model"] = model_name
            row["embedding_dim"] = int(dim or embedded.get("embedding_dim") or 0)
            row["embedding_updated_at"] = now
    return dim


def upsert_daily_run(
    *,
    url: str,
    service_key: str,
    table: str,
    schema: str,
    run_row: dict[str, Any],
    timeout: int,
) -> None:
    endpoint = f"{_rest_url(url)}/{table}?on_conflict=id"
    resp = requests.post(
        endpoint,
        headers=_headers(service_key, "resolution=merge-duplicates", schema=schema),
        data=json.dumps([run_row], ensure_ascii=False, separators=(",", ":")),
        timeout=max(int(timeout or 30), 1),
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"daily run upsert failed: HTTP {resp.status_code} {resp.text[:300]}")


def load_stats(stats_path: str) -> dict[str, Any]:
    if not stats_path or not os.path.exists(stats_path):
        return {}
    with open(stats_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def write_backup(rows: list[dict[str, Any]], stats: dict[str, Any], backup_dir: str) -> tuple[str, str]:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    target = os.path.join(backup_dir, day)
    os.makedirs(target, exist_ok=True)
    papers_path = os.path.join(target, "essay_agent_papers.json")
    stats_path = os.path.join(target, "essay_agent_stats.json")
    public_rows = [
        {k: v for k, v in row.items() if k not in {"embedding"}}
        for row in rows
    ]
    with open(papers_path, "w", encoding="utf-8") as f:
        json.dump(public_rows, f, ensure_ascii=False, indent=2)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    return papers_path, stats_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync essay-agent SQLite output to Supabase.")
    parser.add_argument("--db", default=os.getenv("ESSAY_AGENT_DB_PATH", "papers.db"))
    parser.add_argument("--stats", default=os.getenv("ESSAY_AGENT_STATS_PATH", ""))
    parser.add_argument("--supabase-url", default=os.getenv("SUPABASE_URL", ""))
    parser.add_argument("--service-key", default=os.getenv("SUPABASE_SERVICE_KEY", ""))
    parser.add_argument("--schema", default=os.getenv("SUPABASE_SCHEMA", "public"))
    parser.add_argument("--papers-table", default=os.getenv("ESSAY_AGENT_SUPABASE_PAPERS_TABLE", DEFAULT_TABLE))
    parser.add_argument("--runs-table", default=os.getenv("ESSAY_AGENT_SUPABASE_RUNS_TABLE", DEFAULT_RUNS_TABLE))
    parser.add_argument("--backup-dir", default=os.getenv("ESSAY_AGENT_BACKUP_DIR", DEFAULT_BACKUP_DIR))
    parser.add_argument("--with-embeddings", dest="with_embeddings", action="store_true", default=True)
    parser.add_argument("--no-embeddings", dest="with_embeddings", action="store_false")
    parser.add_argument("--embed-model", default=os.getenv("ESSAY_AGENT_EMBED_MODEL", ""))
    parser.add_argument("--embed-device", default=os.getenv("ESSAY_AGENT_EMBED_DEVICE", "auto"))
    parser.add_argument("--embed-devices", default=os.getenv("ESSAY_AGENT_EMBED_DEVICES", ""))
    parser.add_argument("--embed-batch-size", type=int, default=int(os.getenv("ESSAY_AGENT_EMBED_BATCH_SIZE", "16")))
    parser.add_argument("--embed-max-length", type=int, default=int(os.getenv("ESSAY_AGENT_EMBED_MAX_LENGTH", "512")))
    parser.add_argument("--embed-local-only", action="store_true", default=False)
    parser.add_argument("--reserve-upload-cpus", type=int, default=int(os.getenv("ESSAY_AGENT_RESERVE_UPLOAD_CPUS", "1")))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("ESSAY_AGENT_SUPABASE_BATCH_SIZE", "200")))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("ESSAY_AGENT_SUPABASE_TIMEOUT", "120")))
    args = parser.parse_args()

    if not args.supabase_url or not args.service_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")

    started = time.time()
    rows = load_sqlite_papers(args.db)
    stats = load_stats(args.stats)
    print(f"[essay-agent] loaded {len(rows)} rows from {args.db}", flush=True)

    if args.with_embeddings and rows:
        configure_local_embedding_runtime(args.reserve_upload_cpus)
        model_name = resolve_embed_model(args.embed_model)
        devices = resolve_embed_devices(args.embed_devices, args.embed_device)
        dim = attach_essay_embeddings(
            rows,
            model_name=model_name,
            devices=devices,
            batch_size=max(int(args.embed_batch_size or 1), 1),
            max_length=max(int(args.embed_max_length or 0), 0),
            allow_remote=not bool(args.embed_local_only),
        )
        print(f"[essay-agent] attached embeddings dim={dim}", flush=True)

    upsert_papers(
        url=args.supabase_url,
        service_key=args.service_key,
        table=args.papers_table,
        rows=rows,
        schema=args.schema,
        batch_size=max(int(args.batch_size or 1), 1),
        timeout=max(int(args.timeout or 1), 1),
        retries=3,
        retry_wait=2.0,
    )

    run_id = datetime.now(timezone.utc).strftime("essay-agent-%Y%m%d")
    run_row = {
        "id": run_id,
        "run_date": datetime.now(timezone.utc).date().isoformat(),
        "paper_count": len(rows),
        "stats": stats,
        "backup_path": args.backup_dir,
        "updated_at": _now_iso(),
    }
    upsert_daily_run(
        url=args.supabase_url,
        service_key=args.service_key,
        table=args.runs_table,
        schema=args.schema,
        run_row=run_row,
        timeout=args.timeout,
    )
    papers_path, stats_path = write_backup(rows, stats, args.backup_dir)
    print(
        f"[essay-agent] synced rows={len(rows)} run={run_id} "
        f"backup={papers_path},{stats_path} elapsed={time.time() - started:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
