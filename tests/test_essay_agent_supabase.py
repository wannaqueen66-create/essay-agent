from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.essay_agent_supabase import load_sqlite_papers, stable_paper_id


def test_stable_paper_id_prefers_doi():
    row = {"doi": " https://doi.org/10.1000/ABC ", "source": "crossref", "url": "https://example.test/p"}
    assert stable_paper_id(row) == "doi:10.1000/abc"


def test_load_sqlite_papers_maps_essay_agent_schema(tmp_path: Path):
    db_path = tmp_path / "papers.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        create table papers (
            url text primary key,
            doi text,
            source text,
            title text,
            english_abstract text,
            chinese_summary text,
            published_date text,
            query_name text,
            authors text,
            primary_category text,
            categories text,
            analysis_json text,
            related_score integer,
            analysis_status text,
            meets_threshold integer,
            eligible_for_pending integer,
            first_seen_at text,
            last_seen_at text,
            displayed_at text,
            display_count integer,
            reported_at text,
            report_count integer,
            content_hash text,
            created_at text,
            updated_at text
        )
        """
    )
    conn.execute(
        """
        insert into papers values (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            "https://example.test/paper",
            "10.1/demo",
            "openalex",
            "Spatial behavior in VR",
            "Abstract text",
            "中文摘要",
            "2026-05-27",
            "vr_environment",
            json.dumps(["A", "B"]),
            "journal",
            json.dumps(["VR", "space"]),
            json.dumps({"研究主题": "VR", "中文摘要": "中文摘要"}, ensure_ascii=False),
            88,
            "success",
            1,
            1,
            "2026-05-27T00:00:00",
            "2026-05-27T00:00:00",
            None,
            0,
            None,
            0,
            "hash",
            "2026-05-27T00:00:00",
            "2026-05-27T00:00:00",
        ),
    )
    conn.commit()
    conn.close()

    rows = load_sqlite_papers(str(db_path))

    assert len(rows) == 1
    assert rows[0]["id"] == "doi:10.1/demo"
    assert rows[0]["domain_relevance_score"] == 88
    assert rows[0]["authors"] == ["A", "B"]
    assert rows[0]["analysis"]["研究主题"] == "VR"
