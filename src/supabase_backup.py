from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from typing import Any

import requests


DEFAULT_TABLES = "essay_agent_papers,essay_agent_daily_runs,user_paper_states"


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _headers(service_key: str, schema: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Accept": "application/json",
        "Accept-Profile": schema,
        "Content-Profile": schema,
    }


def fetch_table(url: str, service_key: str, schema: str, table: str, page_size: int) -> list[dict[str, Any]]:
    rest = _norm(url).rstrip("/") + "/rest/v1"
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        endpoint = f"{rest}/{table}?select=*&limit={page_size}&offset={offset}"
        resp = requests.get(endpoint, headers=_headers(service_key, schema), timeout=120)
        if resp.status_code >= 300:
            raise RuntimeError(f"backup {table} failed: HTTP {resp.status_code} {resp.text[:300]}")
        rows = resp.json() or []
        if not isinstance(rows, list) or not rows:
            break
        out.extend(rows)
        if len(rows) < page_size:
            break
        offset += len(rows)
    return out


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("")
        return
    fields = sorted({key for row in rows for key in row.keys()})
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()})


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Supabase tables to JSON and CSV backups.")
    parser.add_argument("--supabase-url", default=os.getenv("SUPABASE_URL", ""))
    parser.add_argument("--service-key", default=os.getenv("SUPABASE_SERVICE_KEY", ""))
    parser.add_argument("--schema", default=os.getenv("SUPABASE_SCHEMA", "public"))
    parser.add_argument("--tables", default=os.getenv("SUPABASE_BACKUP_TABLES", DEFAULT_TABLES))
    parser.add_argument("--out-dir", default=os.getenv("SUPABASE_BACKUP_DIR", "archive/supabase-backups"))
    parser.add_argument("--page-size", type=int, default=int(os.getenv("SUPABASE_BACKUP_PAGE_SIZE", "1000")))
    parser.add_argument("--strict", action="store_true", default=False)
    args = parser.parse_args()

    if not args.supabase_url or not args.service_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")

    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    target = os.path.join(args.out_dir, day)
    os.makedirs(target, exist_ok=True)
    manifest: dict[str, Any] = {"created_at": datetime.now(timezone.utc).isoformat(), "tables": {}}

    for table in [x.strip() for x in args.tables.split(",") if x.strip()]:
        try:
            rows = fetch_table(args.supabase_url, args.service_key, args.schema, table, max(int(args.page_size), 1))
        except RuntimeError as exc:
            message = str(exc)
            is_missing_table = "PGRST205" in message or "Could not find the table" in message
            if args.strict or not is_missing_table:
                raise
            manifest["tables"][table] = {"rows": 0, "skipped": True, "reason": message}
            print(f"[backup] skip missing table {table}: {message}", flush=True)
            continue
        json_path = os.path.join(target, f"{table}.json")
        csv_path = os.path.join(target, f"{table}.csv")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        write_csv(csv_path, rows)
        manifest["tables"][table] = {"rows": len(rows), "json": json_path, "csv": csv_path}
        print(f"[backup] {table}: rows={len(rows)}", flush=True)

    with open(os.path.join(target, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
