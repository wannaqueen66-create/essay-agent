# essay-agent

> Multi-source academic literature monitoring and AI-structured analysis tool for architecture, sports space, VR environment, and behavior trajectory research.
> 面向建筑学、体育空间、VR 环境与行为轨迹研究的多源文献监测与 AI 结构化分析工具。

---

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Features](#2-features)
- [3. Supported Sources](#3-supported-sources)
- [4. Target Journal Monitoring](#4-target-journal-monitoring)
- [5. Project Structure](#5-project-structure)
- [6. Quick Start](#6-quick-start)
- [7. One-Click Deployment (VPS)](#7-one-click-deployment-vps)
- [8. Environment Variables](#8-environment-variables)
- [9. Configuration File](#9-configuration-file)
- [10. Output Files](#10-output-files)
- [11. Utility Scripts](#11-utility-scripts)
- [12. Email Delivery](#12-email-delivery)
- [13. Recommended Default Setup](#13-recommended-default-setup)
- [14. Systemd Service](#14-systemd-service)
- [15. License](#15-license)

---

## 1. Project Overview

**essay-agent** is a production-ready academic monitoring tool that fetches recent papers from multiple scholarly sources and target journals, analyzes them with an OpenAI-compatible model, and produces structured daily reports.

It is designed for topics such as:

- Architecture / built environment
- Sports space / sports facilities
- Virtual reality environments (VR + EEG + eye tracking)
- Behavioral trajectory / spatial behavior
- Environmental perception

Core workflow:

1. Fetch recent papers from 6 data sources + target journals
2. Run AI-based structured analysis (Chinese summaries + 14 structured fields)
3. Filter by relevance score
4. Store history in SQLite with caching
5. Generate Markdown / Excel / JSON reports
6. Optionally send reports by email (Brevo SMTP)

---

## 2. Features

- **6 data sources** — arXiv, OpenAlex, Crossref, Semantic Scholar, Europe PMC, CORE
- **Target journal monitoring** — directly track 16+ top journals via ISSN filtering
- **AI structured analysis** — Chinese summary + research topic, IV/DV, methods, relevance score, and more
- **SQLite caching** — content-hash based deduplication and analysis cache
- **SQLite optimized** — WAL mode, indexes, batch commits for low-IOPS VPS
- **Structured logging** — timestamps, levels, full exception tracebacks
- **Diagnostic reports** — when 0 papers found, email/markdown shows full diagnostic chain with per-source status
- **Rate limiting** — built-in delays between API calls to avoid 429 errors
- **Pending pool** — supplements daily reports with recent qualifying papers
- **Markdown / Excel / JSON** output
- **Brevo SMTP** email delivery with attachments
- **Systemd service + timer** — ready for production cron scheduling
- **One-click deployment** — `deploy.sh` for Ubuntu/Debian VPS
- **Memory-safe** — designed for 1CPU / 1GB RAM VPS (MemoryMax=768M)

---

## 3. Supported Sources

| Source | Type | Auth Required | Notes |
|--------|------|---------------|-------|
| **arXiv** | Preprint | No | Category-specific queries (cs.HC, physics.soc-ph, etc.) |
| **OpenAlex** | Aggregator | No | Broad academic coverage, inverted index abstracts |
| **Crossref** | Metadata | No | DOI-based, journal articles |
| **Semantic Scholar** | Aggregator | No | AI/NLP focus, rate-limited (1 req/sec) |
| **Europe PMC** | Biomedical | No | VR + EEG/eye-tracking papers, neuroscience |
| **CORE** | Open Access | Free API key | 300M+ documents, grey literature, conference papers |

Configure enabled sources in `config.yaml` → `sources`.

---

## 4. Target Journal Monitoring

In addition to keyword-based searching, essay-agent can directly monitor specific journals via OpenAlex ISSN filtering. This ensures you never miss papers from top journals in your field, regardless of keyword matching.

Pre-configured journals (in `config.yaml` → `target_journals`):

**Architecture & Built Environment:**
- Building and Environment (0360-1323)
- Environment and Behavior (0013-9165)
- Journal of Environmental Psychology (0272-4944)
- Architectural Science Review (0003-8628)
- Indoor Air (1600-0668)

**Sports Science & Sports Space:**
- Journal of Sports Sciences (0264-0414)
- International Review for the Sociology of Sport (1012-6902)
- European Sport Management Quarterly (1618-4742)

**VR / HCI / Perception:**
- Virtual Reality (1359-4338)
- Computers in Human Behavior (0747-5632)
- International Journal of Human-Computer Studies (1071-5819)
- Presence: Teleoperators and Virtual Environments (1054-7460)

**Behavioral Trajectory / Urban Space:**
- Transportation Research Part C (0968-090X)
- Journal of Transport Geography (0966-6923)
- Computers, Environment and Urban Systems (0198-9715)
- Applied Geography (0143-6228)

To add more journals, simply add entries with `name` and `issn` to the `target_journals` list. Find ISSNs at [OpenAlex Sources](https://openalex.org/sources) or the journal's official website.

---

## 5. Project Structure

```text
essay-agent/
├── arxiv_agent.py          # Main application
├── config.yaml             # Configuration (queries, sources, journals)
├── requirements.txt        # Pinned Python dependencies
├── .env.example            # Environment variable template
├── deploy.sh               # One-click deployment script
├── deploy/
│   ├── arxiv-agent.service # systemd service unit
│   └── arxiv-agent.timer   # systemd daily timer
├── inspect_db.py           # Database inspection utility
├── reset_reported.py       # Reset display/report status
├── send_output_email.py    # Resend existing reports
├── show_pending_pool.py    # View pending pool
├── test_email.py           # Test SMTP configuration
├── README.md
├── README.zh-CN.md
└── LICENSE
```

Runtime-generated:

```text
papers.db                   # SQLite database (WAL mode)
output/                     # Daily reports
```

---

## 6. Quick Start

```bash
# 1. Install system dependencies
apt update && apt install -y python3 python3-pip python3-venv

# 2. Clone the repository
git clone git@github.com:wannaqueen66-create/essay-agent.git
cd essay-agent

# 3. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Create and edit .env
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, OPENAI_MODEL, etc.

# 6. Run
python arxiv_agent.py
```

---

## 7. One-Click Deployment (VPS)

For production deployment on Ubuntu/Debian VPS (1CPU/1GB RAM or above):

```bash
sudo bash deploy.sh
```

This script will:
1. Install system dependencies (python3, pip, venv)
2. Create a dedicated service user (`arxiv-agent`)
3. Deploy the application to `/opt/arxiv-agent`
4. Create Python virtual environment and install dependencies
5. Set up `.env` from template (you need to edit it)
6. Install systemd service and daily timer (runs at 07:00)
7. Set file permissions (`.env` is chmod 600)

After deployment:

```bash
# Edit configuration
sudo nano /opt/arxiv-agent/.env

# Manual run
sudo -u arxiv-agent /opt/arxiv-agent/.venv/bin/python /opt/arxiv-agent/arxiv_agent.py

# View logs
journalctl -u arxiv-agent -f

# Timer status
systemctl status arxiv-agent.timer
```

---

## 8. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI or compatible API key |
| `OPENAI_BASE_URL` | *(empty)* | Optional compatible API base URL |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Model name |
| `DAYS_BACK` | `2` | Fetch papers from recent N days |
| `MAX_RESULTS_PER_QUERY` | `30` | Max papers per query per source |
| `MIN_RELEVANCE_SCORE` | `70` | Minimum relevance threshold (0-100) |
| `FORCE_REFRESH` | `false` | Ignore cache, re-analyze all |
| `CORE_API_KEY` | *(empty)* | Free API key for CORE source |
| `EMAIL_ENABLED` | `false` | Enable email delivery |
| `EMAIL_SMTP_HOST` | `smtp-relay.brevo.com` | SMTP host |
| `EMAIL_SMTP_PORT` | `587` | SMTP port |
| `EMAIL_USERNAME` | | SMTP username |
| `EMAIL_PASSWORD` | | SMTP password |
| `EMAIL_FROM` | | Sender email |
| `EMAIL_TO` | | Recipient(s), comma-separated |
| `EMAIL_USE_TLS` | `true` | Enable TLS |
| `REPORT_TOP_N` | `10` | Top N in Markdown report |
| `EMAIL_TOP_N` | `5` | Top N in email body |
| `PENDING_POOL_DAYS` | `7` | Pending pool time window |
| `EMPTY_REPORT_EMAIL` | `true` | Send email even when empty (with diagnostics) |

---

## 9. Configuration File

Main configuration is in `config.yaml`:

| Section | Description |
|---------|-------------|
| `queries` | arXiv-specific query expressions (with `cat:` syntax) |
| `generic_queries` | Natural language queries for OpenAlex/Crossref/Semantic Scholar/Europe PMC |
| `target_journals` | ISSN-based journal monitoring list |
| `sources` | Enabled data sources |
| `exclude_keywords` | Keywords to filter out noise |
| `must_have_keywords` | Optional must-match keywords |
| `db_path` | SQLite database path |
| `analysis_retries` | LLM retry count |
| `retry_delay_seconds` | Retry interval (exponential backoff) |

---

## 10. Output Files

After each run:

```text
output/arxiv_daily_YYYY-MM-DD.xlsx       # Sortable/filterable table
output/arxiv_daily_YYYY-MM-DD.md         # Readable report with TOP N
output/arxiv_daily_YYYY-MM-DD_stats.json # Runtime statistics + per-source status
```

When 0 papers are found, the Markdown and email reports include a full diagnostic chain showing fetch counts, filter breakdown, per-source status, and suggested remediation.

---

## 11. Utility Scripts

```bash
python inspect_db.py                          # Database overview
python show_pending_pool.py                   # View pending pool
python reset_reported.py all|displayed|both   # Reset tracking flags
python test_email.py                          # Test SMTP connection
python send_output_email.py --mark-db         # Resend today's report
python send_output_email.py --date 2026-03-08 # Resend historical report
```

---

## 12. Email Delivery

Set `EMAIL_ENABLED=true` in `.env` and configure SMTP credentials.

The email includes:
- Summary in body (TOP N papers with scores and links)
- Markdown attachment
- Excel attachment (if non-empty)
- JSON stats attachment
- **Full diagnostic info when 0 papers found** (per-source status, filter breakdown, suggested causes)

---

## 13. Recommended Default Setup

For first-time setup, use conservative parameters:

```env
OPENAI_MODEL=gpt-4.1-mini
DAYS_BACK=1
MAX_RESULTS_PER_QUERY=5
MIN_RELEVANCE_SCORE=70
FORCE_REFRESH=false
EMAIL_ENABLED=false
```

Gradually increase `DAYS_BACK` and `MAX_RESULTS_PER_QUERY` after verifying everything works.

---

## 14. Systemd Service

The project includes ready-to-use systemd files in `deploy/`:

- `arxiv-agent.service` — oneshot service with memory/CPU limits
  - `MemoryMax=768M` (protects 1GB VPS)
  - `CPUQuota=80%` (prevents monopolizing single core)
  - `TimeoutStartSec=600` (10-minute kill switch)
- `arxiv-agent.timer` — daily trigger at 07:00 with `Persistent=true`

Install manually:

```bash
sudo cp deploy/arxiv-agent.service deploy/arxiv-agent.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now arxiv-agent.timer
```

Or use `sudo bash deploy.sh` for automatic setup.

---

## 15. License

This repository uses the existing `LICENSE` file.

For Chinese documentation, see: [README.zh-CN.md](./README.zh-CN.md)
