# ScholarLens

ScholarLens is a paper reading workspace built around the `essay-agent` data pipeline. It uses GitHub Actions, Supabase, GitHub Pages, semantic retrieval, reranking, AI reading, optional knowledge-base sync, and share snapshots as the technical base, while `essay-agent` remains the source of truth for research domains, keywords, ISSN monitoring, multi-source crawling, Chinese structured analysis, reports, and email delivery.

## What It Does

- Monitors architecture, sports space, VR, spatial behavior, movement traces, healing space, and other domains defined in `config.essay-agent.yaml`.
- Crawls papers from arXiv, OpenAlex, Crossref, Semantic Scholar, Europe PMC, and optional CORE.
- Scores papers with `essay-agent` domain relevance, target journal/ISSN hits, and keyword evidence.
- Generates Chinese structured analysis, Markdown/Excel/JSON daily reports, and email digests.
- Writes public paper and report data to Supabase for the web workspace.
- Keeps advanced reading capabilities: semantic recall, intelligent reranking, AI reading, paper Q&A, knowledge-base sync, and share snapshots.
- Exports daily JSON/CSV backups so Supabase does not become the only copy of the historical library.

## Architecture

```text
essay-agent config
  -> GitHub Actions scheduled/manual run
  -> multi-source crawl, dedupe, relevance scoring
  -> Chinese structured analysis and daily report generation
  -> Supabase upsert, Pages data, email digest, JSON/CSV backup
  -> ScholarLens web workspace
```

The web layer is intentionally a technical shell. The academic scope is not inherited from the upstream base project; it is controlled by `essay-agent` configuration.

## Main Entry Points

- Web workspace: `#/essay-agent-workbench`
- Domain configuration: `config.essay-agent.yaml`
- Runtime frontend source config: `config.yaml` and `index.html`
- Supabase schema: `sql/create_essay_agent_fusion_schema.sql`
- Actions workflow: `.github/workflows/essay-agent-fusion.yml`
- Integration notes: `docs/essay-agent-fusion.md`

## Setup

1. Run `sql/create_essay_agent_fusion_schema.sql` in Supabase.
2. Configure `config.yaml` so `source_backends.essay_agent` points to your Supabase project.
3. Add GitHub Actions secrets for the model API, Supabase, email provider, and optional knowledge/share integrations.
4. Enable GitHub Pages and GitHub Actions.
5. Trigger `essay-agent-fusion.yml` manually once, then verify the ScholarLens workspace can read papers from Supabase.

Required secrets usually include:

- `OPENAI_API_KEY` or another OpenAI-compatible model key used by `essay-agent`.
- `OPENAI_BASE_URL` and `OPENAI_MODEL` when using a custom model endpoint.
- `LLM_API_MODE` is optional: `auto` prefers OpenAI `/v1/responses` for new OpenAI models, keeps `/v1/chat/completions` for compatible third-party endpoints, and can be set to `messages` for `/v1/messages` providers.
- `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, and `ANTHROPIC_MODEL` are optional when `LLM_API_MODE=messages`.
- `ARXIV_RETRIES`, `ARXIV_PAGE_SIZE`, `ARXIV_DELAY_SECONDS`, `ARXIV_BACKOFF_BASE_SECONDS`, and `ARXIV_QUERY_DELAY_SECONDS` can be tuned when GitHub Actions hits arXiv HTTP 429 limits.
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and frontend anon key in config.
- `ESSAY_AGENT_READER_TOP_N`, `ESSAY_AGENT_READER_DEEP_TOP_N`, and `ESSAY_AGENT_READER_FULLTEXT` are optional controls for generated in-site reading pages.
- SMTP/Brevo secrets for email reports.
- Optional Zotero/Gist tokens when enabling knowledge-base sync or share snapshots.

## No-Regression Rule

ScholarLens keeps the advanced technical capabilities from its web base. Product-facing names changed for clarity, but the underlying embedding, rerank, LLM refine, Zotero, and Gist call chains, parameters, and data structures must not be changed unless a separate migration and test proves equivalent or stronger behavior.

## Attribution

ScholarLens is adapted from the open-source `daily-paper-reader` technical base and preserves the original license. See `NOTICE.md` for attribution and scope of modification.
