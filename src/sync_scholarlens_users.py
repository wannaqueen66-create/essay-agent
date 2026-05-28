#!/usr/bin/env python3
"""Sync ScholarLens application users from email-recipient environment values.

The script keeps app-level access control in Supabase (`public.scholarlens_users`)
aligned with the report-recipient list. It does not store model API keys in
Supabase; shared model credentials should remain in GitHub Secrets or Supabase
Edge Function environment variables.
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timezone
from typing import Any

import requests


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def norm_text(value: Any) -> str:
    return str(value or "").strip()


def parse_emails(*values: str) -> list[str]:
    seen: set[str] = set()
    emails: list[str] = []
    for value in values:
        for raw in re.split(r"[,;\s]+", norm_text(value)):
            email = raw.strip().lower()
            if not email or email in seen:
                continue
            if not EMAIL_RE.match(email):
                continue
            seen.add(email)
            emails.append(email)
    return emails


def as_bool(value: Any, default: bool = False) -> bool:
    text = norm_text(value).lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "y", "on"}


def supabase_headers(service_key: str, *, prefer: str = "") -> dict[str, str]:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def upsert_users(url: str, service_key: str, emails: list[str], source: str) -> None:
    if not emails:
        print("[ScholarLens users] no valid emails found; skip sync", flush=True)
        return

    now = datetime.now(timezone.utc).isoformat()
    rows = [
        {
            "email": email,
            "role": "member",
            "is_active": True,
            "source": source,
            "last_synced_at": now,
            "updated_at": now,
        }
        for email in emails
    ]
    endpoint = f"{url.rstrip('/')}/rest/v1/scholarlens_users?on_conflict=email"
    res = requests.post(
        endpoint,
        headers=supabase_headers(service_key, prefer="resolution=merge-duplicates,return=minimal"),
        json=rows,
        timeout=30,
    )
    if res.status_code >= 400:
        raise RuntimeError(f"upsert scholarlens_users failed: HTTP {res.status_code} {res.text[:300]}")
    print(f"[ScholarLens users] synced {len(rows)} active user(s)", flush=True)


def invite_users(url: str, service_key: str, emails: list[str]) -> None:
    if not emails:
        return
    endpoint = f"{url.rstrip('/')}/auth/v1/admin/invite"
    invited = 0
    skipped = 0
    for email in emails:
        res = requests.post(
            endpoint,
            headers=supabase_headers(service_key),
            json={"email": email, "data": {"scholarlens_role": "member"}},
            timeout=30,
        )
        if 200 <= res.status_code < 300:
            invited += 1
            continue
        if res.status_code in {400, 409, 422}:
            skipped += 1
            continue
        raise RuntimeError(f"invite user failed: HTTP {res.status_code} {res.text[:300]}")
    print(f"[ScholarLens users] invite result: invited={invited}, skipped={skipped}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync ScholarLens users from EMAIL_TO / SCHOLARLENS_USER_EMAILS.")
    parser.add_argument("--supabase-url", default=os.getenv("SUPABASE_URL", ""))
    parser.add_argument("--service-key", default=os.getenv("SUPABASE_SERVICE_KEY", ""))
    parser.add_argument("--emails", default="")
    parser.add_argument("--source", default="email_env")
    parser.add_argument("--invite", action="store_true", default=as_bool(os.getenv("SCHOLARLENS_INVITE_USERS")))
    args = parser.parse_args()

    url = norm_text(args.supabase_url)
    service_key = norm_text(args.service_key)
    if not url or not service_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")

    emails = parse_emails(
        args.emails,
        os.getenv("SCHOLARLENS_USER_EMAILS", ""),
        os.getenv("EMAIL_TO", ""),
    )
    upsert_users(url, service_key, emails, norm_text(args.source) or "email_env")
    if args.invite:
        invite_users(url, service_key, emails)


if __name__ == "__main__":
    main()
