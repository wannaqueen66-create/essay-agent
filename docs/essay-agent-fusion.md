# essay-agent Fusion

This fork keeps the Daily Paper Reader web, GitHub Pages, Actions, Supabase, pgvector, embedding, rerank, LLM refine, Zotero, and Gist capabilities, while adding essay-agent as a domain-specific production lane.

## Capability Matrix

| Capability | Source | Fusion status | Replacement or enhancement |
|---|---|---|---|
| Multi-source retrieval | essay-agent | Preserved | Runs from GitHub Actions using arXiv, OpenAlex, Crossref, Semantic Scholar, Europe PMC, and optional CORE. |
| ISSN target journal monitoring | essay-agent | Preserved | Uses `config.essay-agent.yaml` and stores journal hits in Supabase. |
| Chinese structured analysis | essay-agent | Preserved | `src/essay_agent_core.py` remains the analysis engine. |
| Relevance threshold filtering | essay-agent | Preserved | Stored as `domain_relevance_score`, `meets_threshold`, and `eligible_for_pending`. |
| Pending pool | essay-agent | Preserved | SQLite runtime behavior remains; synced rows include pending eligibility metadata. |
| Markdown / Excel / JSON reports | essay-agent | Preserved | Generated under `output/` and uploaded as Actions artifacts. |
| Brevo/SMTP email delivery | essay-agent | Preserved | Runs inside Actions via GitHub Secrets. |
| SQLite cache/history | essay-agent | Enhanced replacement | Runtime SQLite is still produced, while Supabase becomes the main history store and daily exports provide restore files. |
| VPS/systemd scheduling | essay-agent | Enhanced replacement | GitHub Actions provides scheduled and manual execution without a VPS. |
| GitHub Pages reading site | daily-paper-reader | Preserved | Existing Pages workflow is untouched. |
| Supabase paper store | daily-paper-reader | Enhanced | Existing tables remain; `essay_agent_papers` adds domain-specific papers and Chinese analysis. |
| pgvector semantic recall | daily-paper-reader | Preserved and extended | `essay_agent_papers` has `embedding vector(384)` and `match_essay_agent_papers`. |
| BM25 / embedding / RRF / rerank / LLM refine | daily-paper-reader | Preserved | Existing pipeline is untouched; essay-agent scores can be used as an additional ranking signal. |
| Zotero/Gist optional extensions | daily-paper-reader | Preserved | Existing optional front-end and workflow code remains enabled by secrets. |
| Daily backups | new | Enhanced | `src/supabase_backup.py` exports Supabase tables to JSON and CSV. |
| User favorites/read notes | new | Added | `user_paper_states` table has RLS policies for per-user state. |

## Required Setup

1. Run `sql/create_essay_agent_fusion_schema.sql` in Supabase.
2. Configure GitHub Secrets:
   `OPENAI_API_KEY` or `DEEPSEEK_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, optional `CORE_API_KEY`, SMTP/Brevo secrets, and optional Zotero/Gist secrets used by the upstream project.
3. Keep the original Daily Paper Reader workflows enabled for the web reading site and recommendation stack.
4. Enable `.github/workflows/essay-agent-fusion.yml` for the essay-agent production lane.

## Data Flow

`essay-agent-fusion.yml` runs `src/essay_agent_actions_runner.py`, which temporarily uses `config.essay-agent.yaml`, runs `src/essay_agent_core.py`, keeps Markdown/Excel/JSON/SQLite outputs, then calls `src/essay_agent_supabase.py` to upsert papers and daily run metadata into Supabase. The backup step exports Supabase tables to JSON/CSV artifacts.

## No-Regression Rule

Do not delete upstream Daily Paper Reader workflows, SQL, Zotero/Gist utilities, rerank scripts, or Supabase retrieval scripts when modifying essay-agent integration. Any future replacement must update this matrix and include a test or workflow log proving equivalent or stronger behavior.
