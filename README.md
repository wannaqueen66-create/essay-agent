# essay-agent / Essay Agent

> Multi-source academic literature monitoring and AI-structured analysis tool for architecture, sports space, VR environment, and behavior trajectory research.  
> 面向建筑学、体育空间、VR 环境与行为轨迹研究的多源文献监测与 AI 结构化分析工具。

---

## Table of Contents / 目录

- [1. Project Overview / 项目简介](#1-project-overview--项目简介)
- [2. Features / 功能特性](#2-features--功能特性)
- [3. Supported Sources / 支持的数据源](#3-supported-sources--支持的数据源)
- [4. Project Structure / 项目结构](#4-project-structure--项目结构)
- [5. Quick Start / 快速开始](#5-quick-start--快速开始)
- [6. Environment Variables / 环境变量](#6-environment-variables--环境变量)
- [7. Configuration File / 配置文件](#7-configuration-file--配置文件)
- [8. Output Files / 输出结果](#8-output-files--输出结果)
- [9. Utility Scripts / 辅助脚本](#9-utility-scripts--辅助脚本)
- [10. Email Delivery / 邮件推送](#10-email-delivery--邮件推送)
- [11. Recommended Default Setup / 推荐默认配置](#11-recommended-default-setup--推荐默认配置)
- [12. Limitations / 当前限制](#12-limitations--当前限制)
- [13. License / 许可证](#13-license--许可证)

---

## 1. Project Overview / 项目简介

**essay-agent** is a practical academic monitoring tool that fetches recent papers from multiple scholarly sources, analyzes them with an OpenAI-compatible model, and produces structured daily reports.

**essay-agent** 是一个面向实际科研使用场景的文献监测工具。它会从多个学术数据源抓取近期论文，调用 OpenAI 或兼容接口进行结构化分析，并输出日报结果。

It is especially designed for topics such as:

- architecture / 建筑学
- sports space / 体育空间
- virtual reality environments / VR 环境
- behavioral trajectory / 行为轨迹
- spatial behavior / 空间行为
- environmental perception / 环境感知

Core workflow:

1. Fetch recent papers from multiple sources  
   从多个来源抓取近期论文
2. Run AI-based structured analysis  
   执行 AI 结构化分析
3. Filter by relevance score  
   按相关性分数过滤
4. Store history in SQLite  
   将历史结果写入 SQLite
5. Generate Markdown / Excel / JSON report  
   生成 Markdown / Excel / JSON 日报
6. Optionally send the report by email  
   可选发送邮件推送

---

## 2. Features / 功能特性

### English

- Multi-source literature retrieval
- Chinese summary + structured analysis for each paper
- Original English abstract preserved
- SQLite database for caching and history tracking
- Relevance threshold filtering
- Pending pool mechanism for supplementing daily reports
- Markdown / Excel / JSON output
- Brevo SMTP email delivery
- Utility scripts for inspection and status reset

### 中文

- 多源文献抓取
- 每篇论文自动生成中文摘要与结构化分析
- 保留英文原始摘要
- 使用 SQLite 做缓存与历史记录
- 支持相关性阈值过滤
- 支持待展示池补位逻辑
- 输出 Markdown / Excel / JSON 日报
- 支持 Brevo SMTP 邮件推送
- 提供数据库检查与状态重置脚本

---

## 3. Supported Sources / 支持的数据源

Currently supported sources:

- **arXiv**
- **OpenAlex**
- **Crossref**
- **Semantic Scholar**

当前支持的数据源：

- **arXiv**
- **OpenAlex**
- **Crossref**
- **Semantic Scholar**

---

## 4. Project Structure / 项目结构

```text
essay-agent/
├── arxiv_agent.py
├── config.yaml
├── requirements.txt
├── .env.example
├── inspect_db.py
├── reset_reported.py
├── send_output_email.py
├── show_pending_pool.py
├── test_email.py
├── README.md
├── README.zh-CN.md
└── LICENSE
```

Runtime-generated files:

```text
papers.db
output/
```

运行时会额外生成：

```text
papers.db
output/
```

---

## 5. Quick Start / 快速开始

### 5.1 Install system dependencies / 安装系统依赖

```bash
apt update && apt install -y python3 python3-pip python3-venv
```

### 5.2 Clone the repository / 克隆仓库

```bash
git clone git@github.com:wannaqueen66-create/essay-agent.git
cd essay-agent
```

### 5.3 Create a virtual environment / 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 5.4 Install Python dependencies / 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 5.5 Create `.env` / 创建 `.env`

```bash
cp .env.example .env
```

Then edit the file and provide your model API key and optional email settings.  
然后编辑该文件，填写模型 API Key，以及可选的邮件配置。

### 5.6 Run the agent / 运行主程序

```bash
python arxiv_agent.py
```

---

## 6. Environment Variables / 环境变量

The following variables are commonly used in `.env`:

| Variable | Description | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI or OpenAI-compatible API key | OpenAI 或兼容提供商 API Key |
| `OPENAI_BASE_URL` | Optional compatible API base URL | 可选的兼容接口 Base URL |
| `OPENAI_MODEL` | Model name | 模型名称 |
| `DAYS_BACK` | Search recent N days | 抓取最近 N 天 |
| `MAX_RESULTS_PER_QUERY` | Max papers per query per source | 每个 query 在每个源抓取的最大条数 |
| `MIN_RELEVANCE_SCORE` | Minimum relevance threshold | 最低相关性阈值 |
| `FORCE_REFRESH` | Ignore cache and re-analyze | 是否忽略缓存强制重跑 |
| `EMAIL_ENABLED` | Enable email delivery | 是否启用邮件推送 |
| `EMAIL_SMTP_HOST` | SMTP host | SMTP 主机 |
| `EMAIL_SMTP_PORT` | SMTP port | SMTP 端口 |
| `EMAIL_USERNAME` | SMTP username | SMTP 用户名 |
| `EMAIL_PASSWORD` | SMTP password | SMTP 密码 |
| `EMAIL_FROM` | Sender email | 发件人邮箱 |
| `EMAIL_TO` | Recipient list | 收件人列表 |
| `EMAIL_USE_TLS` | Enable TLS | 是否启用 TLS |
| `REPORT_TOP_N` | Top N shown in Markdown report | Markdown 展示前 N 条 |
| `EMAIL_TOP_N` | Top N shown in email body | 邮件正文展示前 N 条 |
| `PENDING_POOL_DAYS` | Pending pool window | 待展示池时间窗口 |
| `EMPTY_REPORT_EMAIL` | Send email even when empty | 当日报为空时是否也发送邮件 |

---

## 7. Configuration File / 配置文件

Main configuration is stored in `config.yaml`.

主要配置放在 `config.yaml` 中。

Key sections include:

- `queries`: arXiv-specific query expressions  
  `queries`：arXiv 专用检索式
- `generic_queries`: natural language queries for general literature sources  
  `generic_queries`：通用文献源检索式
- `sources`: enabled source list  
  `sources`：启用的数据源列表
- `exclude_keywords`: noisy keywords to exclude  
  `exclude_keywords`：排噪关键词
- `must_have_keywords`: optional must-hit keywords  
  `must_have_keywords`：必须命中关键词
- `db_path`: SQLite database path  
  `db_path`：SQLite 数据库路径
- `analysis_retries`: retry count for model analysis  
  `analysis_retries`：AI 分析重试次数
- `retry_delay_seconds`: retry interval  
  `retry_delay_seconds`：重试间隔秒数

---

## 8. Output Files / 输出结果

After a successful run, the tool generates:

```text
output/arxiv_daily_YYYY-MM-DD.xlsx
output/arxiv_daily_YYYY-MM-DD.md
output/arxiv_daily_YYYY-MM-DD_stats.json
```

Each file serves a different purpose:

- **Excel**: sorting, filtering, manual review  
  **Excel**：排序、筛选、人工复核
- **Markdown**: quick reading and reporting  
  **Markdown**：快速阅读与汇报
- **stats.json**: runtime statistics and debugging  
  **stats.json**：运行统计与调试

---

## 9. Utility Scripts / 辅助脚本

Available helper scripts:

```bash
python inspect_db.py
python show_pending_pool.py
python reset_reported.py all
python reset_reported.py displayed
python reset_reported.py both
python test_email.py
```

If report files already exist and you only want to resend email output:

```bash
python send_output_email.py --mark-db
python send_output_email.py --date 2026-03-08 --mark-db
```

如果日报文件已经生成，只想补发邮件，也可以直接使用 `send_output_email.py`。

---

## 10. Email Delivery / 邮件推送

To enable Brevo email delivery, set:

```env
EMAIL_ENABLED=true
EMAIL_SMTP_HOST=smtp-relay.brevo.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_brevo_smtp_username
EMAIL_PASSWORD=your_brevo_smtp_password
EMAIL_FROM=you@example.com
EMAIL_TO=you@example.com
EMAIL_USE_TLS=true
```

The email includes:

- brief summary in body  
  邮件正文简报
- Markdown attachment  
  Markdown 附件
- Excel attachment  
  Excel 附件
- JSON stats attachment  
  JSON 统计附件

---

## 11. Recommended Default Setup / 推荐默认配置

Recommended beginner setup:

```env
OPENAI_MODEL=gpt-4.1-mini
DAYS_BACK=1
MAX_RESULTS_PER_QUERY=5
MIN_RELEVANCE_SCORE=70
FORCE_REFRESH=false
EMAIL_ENABLED=false
```

推荐先用较保守的配置跑通，再逐步放大抓取范围。

---

## 12. Limitations / 当前限制

### English

- Main logic is still concentrated in a single Python file.
- Exception handling is practical but not yet highly observable.
- Dependency versions are not pinned.
- The project is suitable as a personal research tool, but still needs further engineering for long-term production use.

### 中文

- 主逻辑仍然集中在单个 Python 文件中。
- 错误处理偏实用型，还不够可观测。
- 依赖版本尚未锁定。
- 目前更适合个人科研使用，若长期生产运行仍建议继续工程化整理。

---

## 13. License / 许可证

This repository currently keeps the existing `LICENSE` file from the target repository.  
当前仓库保留目标仓库中已有的 `LICENSE` 文件。

For a Chinese-only document, please see:

- [README.zh-CN.md](./README.zh-CN.md)
