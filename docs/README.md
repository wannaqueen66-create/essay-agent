# ScholarLens

ScholarLens is the web workspace for the `essay-agent` literature pipeline. It focuses on architecture, sports space, VR, spatial behavior, movement traces, healing space, and the other research directions defined in `config.essay-agent.yaml`.

## Start Here

- Open the paper workspace: [essay-agent Workbench](essay-agent-workbench)
- Review the fusion design: [ScholarLens fusion notes](essay-agent-fusion)
- Configure research domains in `config.essay-agent.yaml`
- Configure Supabase and GitHub Actions secrets before scheduled runs

## Core Capabilities

- Multi-source monitoring from arXiv, OpenAlex, Crossref, Semantic Scholar, Europe PMC, and optional CORE.
- Chinese structured analysis and daily paper reports.
- Domain relevance scoring from `essay-agent` keywords, ISSN targets, and source metadata.
- Semantic recall, intelligent reranking, and AI reading for workspace discovery.
- Optional knowledge-base sync and share snapshots when the corresponding secrets are configured.
- Email digest and daily JSON/CSV backups.

The product domain is decided by `essay-agent`; the web base only provides reading, retrieval, automation, and storage infrastructure.
