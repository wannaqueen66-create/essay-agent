# ScholarLens Fusion

ScholarLens uses `essay-agent` as the domain and data-production core, and reuses the web, automation, Supabase, semantic retrieval, reranking, AI reading, knowledge-base sync, and share-snapshot capabilities from the existing technical base.

## Capability Matrix

| Capability | Owner | ScholarLens status | Notes |
|---|---|---|---|
| Research domains and keywords | essay-agent | Source of truth | Controlled by `config.essay-agent.yaml`, not by upstream default domains. |
| ISSN target journal monitoring | essay-agent | Preserved | Target journal hits are stored with paper metadata. |
| Multi-source retrieval | essay-agent | Preserved | arXiv, OpenAlex, Crossref, Semantic Scholar, Europe PMC, and optional CORE. |
| Chinese structured analysis | essay-agent | Preserved | `src/essay_agent_core.py` remains the analysis engine. |
| Domain relevance scoring | essay-agent | Preserved and enhanced | Stored as `domain_relevance_score`, threshold flags, keyword evidence, and target journal metadata. |
| Markdown / Excel / JSON reports | essay-agent | Preserved | Generated under `output/` and uploaded as GitHub Actions artifacts. |
| Email digest | essay-agent | Preserved | Uses GitHub Secrets for SMTP/Brevo or compatible email providers. |
| SQLite runtime cache | essay-agent | Replaced without weakening history | Runtime artifacts may still be produced; Supabase plus JSON/CSV exports become the deployable history layer. |
| VPS/systemd schedule | essay-agent | Replaced without weakening scheduling | GitHub Actions provides scheduled runs, manual reruns, logs, and failure visibility. |
| GitHub Pages reading site | technical base | Preserved | Rebranded as ScholarLens. |
| Supabase paper store | technical base | Extended | `essay_agent_papers` stores domain-specific papers and Chinese analysis. |
| pgvector and embedding | technical base | Preserved as semantic recall | Product-facing label: 语义召回. |
| rerank | technical base | Preserved as intelligent reranking | Product-facing label: 智能重排. |
| LLM refine | technical base | Preserved as AI reading | Product-facing label: AI 精读. |
| Zotero optional integration | technical base | Preserved as knowledge-base sync | Product-facing label: 知识库同步. |
| Gist optional integration | technical base | Preserved as share snapshot | Product-facing label: 分享快照. |
| Daily backups | ScholarLens | Added | `src/supabase_backup.py` exports Supabase tables to JSON and CSV. |
| User favorites/read notes | ScholarLens | Added | `user_paper_states` uses RLS policies for per-user state. |

## Required Setup

1. Run `sql/create_essay_agent_fusion_schema.sql` in Supabase.
2. Configure `source_backends.essay_agent` in `config.yaml` and keep the matching runtime config in `index.html`.
3. Configure GitHub Secrets for model API, Supabase service role key, SMTP/Brevo, and optional knowledge-base/share integrations.
4. Enable `.github/workflows/essay-agent-fusion.yml`.
5. Open `#/essay-agent-workbench` and verify papers load from `essay_agent_papers`.

## Data Flow

`essay-agent-fusion.yml` runs `src/essay_agent_actions_runner.py`, temporarily uses `config.essay-agent.yaml`, runs `src/essay_agent_core.py`, keeps Markdown/Excel/JSON/SQLite outputs, then calls `src/essay_agent_supabase.py` to upsert papers and daily run metadata into Supabase. The backup step exports Supabase tables to JSON/CSV artifacts.

## No-Regression Rule

Do not delete semantic recall, intelligent reranking, AI reading, knowledge-base sync, share snapshot, Supabase retrieval, or existing workflow support when modifying the `essay-agent` integration. Product-facing labels may change, but call chains, parameters, data structures, and availability must remain compatible unless a separate migration and test proves equivalent or stronger behavior.
