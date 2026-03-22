# essay-agent / Essay Agent

> A complete, newbie-friendly academic monitoring and AI analysis toolkit for architecture, sports space, VR environments, spatial behavior, and behavior trajectory research.  
> 一个面向建筑学、体育空间、VR 环境、空间行为与行为轨迹研究的完整文献监测与 AI 结构化分析工具，强调**结构完整、信息充分、对新手友好**。

---

## Table of Contents / 目录

- [1. What This Project Is / 项目是什么](#1-what-this-project-is--项目是什么)
- [2. Who This Project Is For / 适合谁用](#2-who-this-project-is-for--适合谁用)
- [3. What Problem It Solves / 解决什么问题](#3-what-problem-it-solves--解决什么问题)
- [4. Why It Is Useful / 为什么它有用](#4-why-it-is-useful--为什么它有用)
- [5. Core Features / 核心功能](#5-core-features--核心功能)
- [6. Supported Sources / 支持的数据源](#6-supported-sources--支持的数据源)
- [7. Target Journal Monitoring / 目标期刊监控](#7-target-journal-monitoring--目标期刊监控)
- [8. Project Structure / 项目结构](#8-project-structure--项目结构)
- [9. One-Command VPS Install / 一条命令部署到 VPS](#9-one-command-vps-install--一条命令部署到-vps)
- [10. Manual Installation / 手动安装](#10-manual-installation--手动安装)
- [11. Interactive Environment Configuration / 交互式环境配置](#11-interactive-environment-configuration--交互式环境配置)
- [12. Configuration Reference / 配置说明](#12-configuration-reference--配置说明)
- [13. How to Run / 如何运行](#13-how-to-run--如何运行)
- [14. Update and Upgrade / 更新与升级](#14-update-and-upgrade--更新与升级)
- [15. Output Files / 输出结果](#15-output-files--输出结果)
- [16. Utility Scripts / 辅助脚本](#16-utility-scripts--辅助脚本)
- [17. systemd Timer and Service / systemd 定时服务](#17-systemd-timer-and-service--systemd-定时服务)
- [18. Suggested Beginner Setup / 新手建议配置](#18-suggested-beginner-setup--新手建议配置)
- [19. FAQ / 常见问题](#19-faq--常见问题)
- [20. Notes and Limitations / 注意事项与当前限制](#20-notes-and-limitations--注意事项与当前限制)
- [21. Chinese Documentation / 中文文档](#21-chinese-documentation--中文文档)
- [22. License / 许可证](#22-license--许可证)

---

## 1. What This Project Is / 项目是什么

**essay-agent** is a multi-source paper monitoring pipeline built for practical research work. It automatically collects recent papers, analyzes them with an OpenAI-compatible model, generates Chinese summaries plus structured research fields, stores results in SQLite, and outputs readable daily reports.

**essay-agent** 是一个面向实际科研工作的多源文献监测流水线。它会自动抓取近期论文，调用 OpenAI 或兼容接口进行分析，生成中文摘要与结构化研究字段，将结果写入 SQLite，并输出适合日常阅读和汇报的日报文件。

It is especially suitable for topics such as:

- architecture / 建筑学
- sports space / 体育空间
- VR environments / VR 环境
- spatial behavior / 空间行为
- behavioral trajectory / 行为轨迹
- environmental perception / 环境感知
- VR + EEG / eye tracking related studies / VR + EEG / 眼动相关研究

---

## 2. Who This Project Is For / 适合谁用

This project is especially suitable for:

- researchers who need daily paper monitoring;
- users who want Chinese summaries instead of reading every abstract manually;
- architecture / sports space / behavior / VR researchers;
- VPS users who want a low-maintenance scheduled workflow;
- people who prefer a **copy-one-command-and-deploy** style setup.

这个项目尤其适合：

- 需要每天监测新论文的研究者；
- 希望先看中文摘要，而不是逐篇手动读英文摘要的人；
- 建筑学 / 体育空间 / 空间行为 / VR 方向的研究者；
- 想把任务稳定跑在 VPS 上的人；
- 喜欢“复制一条命令就部署”的使用方式的人。

---

## 3. What Problem It Solves / 解决什么问题

### English

If you work in interdisciplinary research, paper monitoring is often annoying for three reasons:

1. papers are scattered across multiple sources;
2. keyword search alone is noisy;
3. even after finding papers, manual abstract reading is slow.

This project solves that by turning paper monitoring into a repeatable workflow:

- collect recent papers from multiple sources,
- apply domain-focused filtering,
- ask a model to produce structured Chinese analysis,
- keep history in a database,
- generate Markdown / Excel / JSON outputs,
- optionally send reports by email.

### 中文

如果你做的是跨学科研究，文献监测通常会遇到三类问题：

1. 论文分散在多个数据源里；
2. 单纯靠关键词检索噪音很大；
3. 即使抓到了论文，人工逐篇读摘要也很慢。

这个项目的目标，就是把“每天找文献”变成一条可重复、可积累、可自动化的工作流：

- 从多个数据源抓取近期论文；
- 做领域定向过滤；
- 用模型输出中文结构化分析；
- 把历史结果存入数据库；
- 自动生成 Markdown / Excel / JSON 报告；
- 可选发送邮件日报。

---

## 4. Why It Is Useful / 为什么它有用

Compared with a normal paper crawler, this project is useful because it does not stop at “collecting titles.” It continues through analysis, filtering, storage, reporting, and optional email delivery.

和普通“抓论文标题”的脚本相比，这个项目有用的地方在于：它不止停留在“抓到东西”，而是继续做了分析、过滤、存储、报告和推送，形成了完整闭环。

In practice, that means:

- less manual reading;
- less repetitive searching;
- more structured daily review;
- easier accumulation of a domain-specific paper database.

在实际使用里，这意味着：

- 少手工读摘要；
- 少重复做检索；
- 更容易形成稳定的日报习惯；
- 更容易积累自己的领域文献数据库。

---

## 5. Core Features / 核心功能

### English

- Multi-source literature retrieval
- ISSN-based target journal monitoring
- Chinese summary + structured analysis for each paper
- Original English abstract preserved
- SQLite cache and history database
- Relevance threshold filtering
- Pending pool for supplementing daily reports
- Markdown / Excel / JSON output
- Brevo SMTP email delivery
- One-command interactive deployment for VPS
- systemd timer for scheduled execution
- low-resource VPS-friendly design

### 中文

- 多源文献抓取
- 基于 ISSN 的目标期刊监控
- 每篇论文自动生成中文摘要与结构化分析
- 保留英文原始摘要
- SQLite 缓存与历史数据库
- 相关性阈值过滤
- 待展示池补位机制
- 输出 Markdown / Excel / JSON 日报
- 支持 Brevo SMTP 邮件推送
- 支持 VPS 一键交互式部署
- 自带 systemd 定时运行方案
- 针对低配 VPS 做了适配

---

## 6. Supported Sources / 支持的数据源

| Source | Type | Auth Required | Notes |
|---|---|---|---|
| arXiv | Preprint | No | Supports category-based search |
| OpenAlex | Aggregator | No | Broad academic coverage |
| Crossref | Metadata | No | DOI / journal-heavy metadata |
| Semantic Scholar | Aggregator | No | Good for AI / NLP / CS crossover |
| Europe PMC | Biomedical | No | Useful for VR, EEG, perception papers |
| CORE | Open Access Aggregator | Free API key optional | Massive OA coverage |

在 `config.yaml -> sources` 中可以控制启用哪些数据源。

---

## 7. Target Journal Monitoring / 目标期刊监控

Besides keyword-based search, the project can directly monitor selected journals through ISSN filtering. This helps you catch important papers even if their titles do not fully match your generic search queries.

除了关键词检索，这个项目还支持通过 ISSN 直接监控目标期刊。这样即使论文标题没有完整命中你的检索式，只要发表在目标期刊上，也仍然能被抓到。

Pre-configured examples include journals from:

- architecture and built environment (including Building and Environment, Journal of Building Engineering)
- sports science and sports space
- VR / HCI / perception
- mobility / trajectory / urban space

具体列表请查看 `config.yaml` 中的 `target_journals`。

---

## 8. Project Structure / 项目结构

```text
essay-agent/
├── essay_agent.py              # Main program / 主程序
├── config.yaml                 # Search queries, source list, journal list / 配置文件
├── requirements.txt            # Python dependencies / Python 依赖
├── .env.example                # Environment variable template / 环境变量模板
├── deploy.sh                   # Interactive installer / 安装部署脚本
├── esag                        # Interactive operations panel / 交互式运维管理脚本
├── deploy/
│   ├── essay-agent.service     # systemd service unit
│   └── essay-agent.timer       # systemd timer unit
├── inspect_db.py               # Database overview
├── reset_reported.py           # Reset displayed/reported flags
├── send_output_email.py        # Resend existing report files
├── show_pending_pool.py        # Show pending pool
├── test_email.py               # Test SMTP delivery
├── README.md                   # Bilingual README / 中英双语 README
├── README.zh-CN.md             # Chinese-only documentation / 独立中文文档
└── LICENSE
```

Runtime-generated files:

```text
papers.db
output/
```

---

## 9. One-Command VPS Install / 一条命令部署到 VPS

If your VPS already has `curl` and `sudo`, you can deploy the project with **one bash command**.

如果你的 VPS 上已经有 `curl` 和 `sudo`，你可以直接用**一条 bash 命令**部署这个项目。

### Recommended unified entry / 推荐统一入口

The intended user-facing entry is now the `esag` console itself.

现在面向用户的推荐统一入口已经改成了 `esag` 控制台本身。

For first-time bootstrap on a fresh VPS, use:

```bash
curl -fsSL https://raw.githubusercontent.com/wannaqueen66-create/essay-agent/main/esag | bash
```

If you are not root, use:

```bash
curl -fsSL https://raw.githubusercontent.com/wannaqueen66-create/essay-agent/main/esag | sudo bash
```

After launch, `esag` will show a top-level menu such as:

- install / reinstall
- enter operations console
- upgrade program (keep current config)
- full reconfigure
- uninstall

也就是说，首次安装不再强调“用户直接操作 deploy.sh”，而是：

- 进入 `esag`
- 由 `esag` 的顶层菜单来调度安装、运维、升级、卸载

### What it does / 这条命令会做什么

This installer is designed to work correctly even when run through a pipe such as:

```bash
curl -fsSL ... | sudo bash
```

It reads interactive answers from `/dev/tty`, so you can still type values normally during the setup process.

这个安装脚本已经专门适配了下面这种管道执行方式：

```bash
curl -fsSL ... | sudo bash
```

它会从 `/dev/tty` 读取交互输入，因此在安装过程中你仍然可以正常键盘输入配置值。

The installer will:

1. install system dependencies;
2. pull the latest repository code;
3. launch an **interactive configuration flow**;
4. show prompts with visible defaults;
5. let you press **Enter** to accept the default whenever a prompt displays `[default]`;
6. use the default choice directly for prompts like `[Y/n]` or `[y/N]` if you just press Enter;
7. ask you for OpenAI API settings;
8. optionally ask you for email settings;
9. ask for runtime parameters such as `DAYS_BACK` and `MIN_RELEVANCE_SCORE`;
10. create the `.env` file automatically;
11. install a Python virtual environment;
12. install systemd service and timer;
13. optionally run a first test execution.

More concretely, during setup:

- if you see `[default]`, pressing Enter means **use that default value**;
- if you see `[Y/n]` or `[y/N]`, pressing Enter means **use the shown default choice**;
- email delivery is optional and defaults to **disabled**;
- CORE API is optional and defaults to **not configured**.

部署脚本会自动完成：

1. 安装系统依赖；
2. 拉取最新仓库代码；
3. 启动**交互式配置流程**；
4. 询问 OpenAI API 配置；
5. 可选询问邮件推送配置；
6. 询问运行参数（如 `DAYS_BACK`、`MIN_RELEVANCE_SCORE`）；
7. 自动生成 `.env`；
8. 创建 Python 虚拟环境；
9. 安装 systemd 服务与定时器；
10. 可选立即试运行一次。

So the expected experience is:

> paste one command into the VPS → finish installation → enter interactive env configuration → deployment completes.

也就是说，预期体验就是：

> 把一条命令复制到 VPS 执行 → 自动安装 → 进入交互式 env 配置界面 → 部署完成。

---

## 10. Manual Installation / 手动安装

If you prefer manual setup, use the following steps.

如果你不想用一键脚本，也可以手动安装。

### 10.1 Install system packages / 安装系统依赖

```bash
apt update && apt install -y python3 python3-pip python3-venv git
```

### 10.2 Clone repository / 克隆仓库

```bash
git clone git@github.com:wannaqueen66-create/essay-agent.git
cd essay-agent
```

### 10.3 Create virtual environment / 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 10.4 Install dependencies / 安装依赖

```bash
pip install -r requirements.txt
```

### 10.5 Create `.env` / 创建 `.env`

```bash
cp .env.example .env
nano .env
```

### 10.6 Run the program / 运行程序

```bash
python essay_agent.py
```

---

## 11. Interactive Environment Configuration / 交互式环境配置

If you use the one-command installer, the script will ask you for:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` (optional)
- `OPENAI_MODEL`
- after `API key + base URL` are filled, the script will try to fetch the available model list automatically and show candidates for easier selection
- if a model list is found, you can input either the **model number** (such as `1`, `2`, `3`) or the full model name
- whether email should be enabled
- SMTP settings if enabled
- `DAYS_BACK`
- `MAX_RESULTS_PER_QUERY`
- `MIN_RELEVANCE_SCORE`
- `REPORT_TOP_N`
- `EMAIL_TOP_N`
- `PENDING_POOL_DAYS`
- optional `CORE_API_KEY`
- daily run time for the timer

如果你使用一键安装脚本，脚本会交互式询问你：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`（可选）
- `OPENAI_MODEL`
- 是否启用邮件
- 若启用邮件，则继续询问 SMTP 配置
- `DAYS_BACK`
- `MAX_RESULTS_PER_QUERY`
- `MIN_RELEVANCE_SCORE`
- `REPORT_TOP_N`
- `EMAIL_TOP_N`
- `PENDING_POOL_DAYS`
- 可选的 `CORE_API_KEY`
- 每日定时运行时间

This means you do **not** need to manually write the `.env` file during deployment unless you want to adjust settings later.

这意味着在部署过程中，你**不需要自己手写 `.env`**，除非后面想手动调整参数。

---

## 12. Configuration Reference / 配置说明

### CORE API registration / CORE API 注册流程

If you want to use the CORE source, you need a CORE API key.

如果你想启用 CORE 数据源，需要先申请 CORE API Key。

Typical process:

1. visit <https://core.ac.uk/services/api>
2. register or sign in
3. create an API key
4. copy the key into `.env` as `CORE_API_KEY`

通常流程就是：

1. 打开 <https://core.ac.uk/services/api>
2. 注册或登录 CORE
3. 创建 API key
4. 把拿到的 key 填进 `.env` 里的 `CORE_API_KEY`

If you do not have a CORE key yet, the project can still run with the other enabled sources.

如果你暂时没有 CORE key，项目依然可以依靠其他数据源正常运行。

### 12.1 `.env` runtime parameters / `.env` 运行时参数

| Variable | Description | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI or compatible API key | OpenAI 或兼容接口 API Key |
| `OPENAI_BASE_URL` | Optional compatible API base URL | 可选兼容接口 Base URL |
| `OPENAI_MODEL` | Model name | 模型名称 |
| `DAYS_BACK` | How many recent days to fetch | 抓取最近多少天论文 |
| `MAX_RESULTS_PER_QUERY` | Max fetch size per query per source | 每个 query 每个源最大抓取数量 |
| `MIN_RELEVANCE_SCORE` | Minimum score threshold | 最低相关性阈值 |
| `FORCE_REFRESH` | Ignore cache and re-run analysis | 忽略缓存强制重跑 |
| `CORE_API_KEY` | Optional CORE API key | 可选 CORE API Key |
| `EMAIL_ENABLED` | Enable SMTP delivery | 是否启用 SMTP 推送 |
| `EMAIL_SMTP_HOST` | SMTP host | SMTP 主机 |
| `EMAIL_SMTP_PORT` | SMTP port | SMTP 端口 |
| `EMAIL_USERNAME` | SMTP username | SMTP 用户名 |
| `EMAIL_PASSWORD` | SMTP password | SMTP 密码 |
| `EMAIL_FROM` | Sender email | 发件邮箱 |
| `EMAIL_TO` | Recipient list | 收件人列表 |
| `EMAIL_USE_TLS` | TLS switch | TLS 开关 |
| `REPORT_TOP_N` | Number of top papers in Markdown | Markdown 展示前 N 条 |
| `EMAIL_TOP_N` | Number of top papers in email body | 邮件正文展示前 N 条 |
| `PENDING_POOL_DAYS` | Pending pool window | 待展示池窗口天数 |
| `EMPTY_REPORT_EMAIL` | Send email even when empty | 为空时是否也发邮件 |

### 12.2 `config.yaml` project parameters / `config.yaml` 项目参数

| Section | Description | 说明 |
|---|---|---|
| `queries` | arXiv-specific search expressions | arXiv 专用检索式 |
| `generic_queries` | generic search queries for other sources | 其他来源的通用检索式 |
| `target_journals` | ISSN-based journal monitoring list | 基于 ISSN 的期刊监控列表 |
| `sources` | enabled sources | 启用的数据源 |
| `exclude_keywords` | noise filtering keywords | 排噪关键词 |
| `must_have_keywords` | optional must-have terms | 必须命中关键词 |
| `db_path` | SQLite path | SQLite 数据库路径 |
| `analysis_retries` | retry count | 分析重试次数 |
| `retry_delay_seconds` | retry interval | 重试间隔 |

---

## 13. How to Run / 如何运行

### Manual one-time run / 手动运行一次

```bash
python essay_agent.py
```

### If deployed through `deploy.sh` / 如果通过 `deploy.sh` 部署

```bash
sudo -u essay-agent /opt/essay-agent/.venv/bin/python /opt/essay-agent/essay_agent.py
```

### Follow logs / 查看日志

```bash
journalctl -u essay-agent -f
```

---

## 14. Update and Upgrade / 更新与升级

After the first installation, the recommended daily operations entry is:

```bash
sudo esag
```

首次安装完成后，推荐的日常运维入口就是：

```bash
sudo esag
```

With `esag`, you now get a more panel-like terminal experience with:

- a status homepage,
- current installed commit and recent upgrade time on the homepage,
- a latest run stats summary on the homepage,
- submenus for core settings,
- submenus for email settings,
- submenus for sources / CORE,
- submenus for logs and diagnostics,
- a maintenance section for run / upgrade / uninstall.

In practice, `esag` can interactively:

- show a dashboard-like overview,
- run the program manually,
- modify core settings directly from the menu (model, days, max results, score threshold, report sizes, timer time),
- modify email settings directly from the menu,
- toggle common data sources interactively,
- manage CORE API settings,
- manage target journals,
- inspect logs,
- inspect database status,
- inspect pending pool,
- test email,
- create and restore backups,
- re-run deploy for upgrades,
- uninstall the project.

通过 `esag`，你可以交互式完成：

- 手动运行主程序
- 修改 `.env`
- 修改 `config.yaml`
- 查看日志
- 查看数据库状态
- 查看待展示池
- 测试邮箱
- 重新部署升级
- 卸载项目


If you already deployed the project once and want to update it later, the recommended approach is simple:

如果你已经部署过一次，后续想升级，推荐做法也很简单：

### Recommended upgrade flow / 推荐升级流程

```bash
curl -fsSL https://raw.githubusercontent.com/wannaqueen66-create/essay-agent/main/deploy.sh | sudo bash
```

The deploy script is designed to be reusable. Running it again will:

- pull the latest repository code,
- keep using the same installation directory,
- recreate / refresh service files,
- let you re-enter interactive configuration if needed,
- and optionally run a test execution again.

In `esag`, the dedicated upgrade path now separates this from full reconfiguration:

- **Upgrade program (keep current config)**
  - shows upgrade before/after commit
  - preserves `.env`, `config.yaml`, and `papers.db`
  - records the latest upgrade time on the dashboard
- **Full reconfigure**
  - re-runs the full deploy wizard

这个部署脚本是可重复使用的。再次执行时，它会：

- 拉取最新仓库代码；
- 继续使用同一个安装目录；
- 刷新 service / timer；
- 如有需要重新进入交互式配置；
- 可选再试运行一次。

### If you only want to edit runtime settings / 如果你只想改运行参数

```bash
sudo nano /opt/essay-agent/.env
sudo systemctl restart essay-agent.timer
```

### If you changed only `config.yaml` / 如果你只改了 `config.yaml`

```bash
sudo nano /opt/essay-agent/config.yaml
```

Then the next scheduled run will use the updated config.

---

## 15. Output Files / 输出结果

Each successful run generates files like:

```text
output/essay_daily_YYYY-MM-DD.xlsx
output/essay_daily_YYYY-MM-DD.md
output/essay_daily_YYYY-MM-DD_stats.json
```

### Excel / Excel 文件
Used for:
- sorting
- filtering
- manual review
- later literature synthesis

### Markdown / Markdown 文件
Used for:
- quick reading
- daily briefing
- structured inspection of top papers

### stats.json / stats.json 文件
Used for:
- runtime statistics
- source health checks
- debugging fetch / analysis behavior

When 0 papers are kept, the report still explains:
- how many were fetched,
- how many were filtered,
- which source may have failed,
- and what to check next.

当最终收录为 0 篇时，报告仍会包含：
- 抓取了多少；
- 被哪些环节过滤掉了多少；
- 哪个数据源可能有问题；
- 下一步建议检查什么。

---

## 16. Utility Scripts / 辅助脚本

```bash
python inspect_db.py
python show_pending_pool.py
python reset_reported.py all
python reset_reported.py displayed
python reset_reported.py both
python test_email.py
python send_output_email.py --mark-db
python send_output_email.py --date 2026-03-08 --mark-db
```

### What they are for / 这些脚本是干什么的

- `inspect_db.py` — inspect current DB status  
  查看数据库总体状态
- `show_pending_pool.py` — inspect the pending pool  
  查看待展示池
- `reset_reported.py` — reset display/report tracking flags  
  重置展示 / 上报状态
- `test_email.py` — test SMTP sending only  
  单独测试邮箱发送
- `send_output_email.py` — resend output files without rerunning fetch/analyze  
  不重跑主流程，仅重发输出文件邮件

---

## 17. systemd Timer and Service / systemd 定时服务

The repository includes ready-made systemd files:

- `deploy/essay-agent.service`
- `deploy/essay-agent.timer`

### Default behavior / 默认行为

- timer triggers once per day
- service runs as `oneshot`
- resource limits are included for smaller VPS machines

### Common commands / 常用命令

```bash
systemctl status essay-agent.timer
systemctl status essay-agent.service
journalctl -u essay-agent -n 200 --no-pager
journalctl -u essay-agent -f
```

---

## 18. Suggested Beginner Setup / 新手建议配置

If you are running this for the first time, start small:

```env
OPENAI_MODEL=gpt-4.1-mini
DAYS_BACK=1
MAX_RESULTS_PER_QUERY=10
MIN_RELEVANCE_SCORE=60
FORCE_REFRESH=false
EMAIL_ENABLED=false
```

Why this is recommended:

- lower API cost
- easier debugging
- faster first run
- less noise in results

推荐原因：

- API 成本更低
- 更容易排查问题
- 第一次运行更快
- 结果噪音更少

---

## 19. FAQ / 常见问题

### Q1. `ModuleNotFoundError` when running / 运行时报缺包错误

Install dependencies again:

```bash
pip install -r requirements.txt
```

### Q2. No papers were found / 没抓到论文

Check:

- `DAYS_BACK` too small?
- `MIN_RELEVANCE_SCORE` too high?
- a source temporarily unavailable?
- your query too narrow?

### Q3. Email failed / 邮件发送失败

Check:

- SMTP username/password
- sender address
- receiver address
- whether outbound SMTP is blocked on the VPS

### Q4. I want to deploy with one command and configure interactively / 我想一条命令部署并进入交互式配置

Use:

```bash
curl -fsSL https://raw.githubusercontent.com/wannaqueen66-create/essay-agent/main/deploy.sh | sudo bash
```

That is the intended deployment flow.

---

## 20. Notes and Limitations / 注意事项与当前限制

This project is already useful and complete enough for daily research monitoring, but it is still closer to a **practical research tool** than a fully modular enterprise-grade system.

这个项目已经足够用于日常科研监测，但它更接近一个**实用型科研工具**，而不是完全模块化、企业级工程项目。

Current limitations include:

- main logic still concentrated in one Python file;
- not all dependency versions are fully pinned;
- engineering structure can still be improved;
- best suited for personal or small-team research workflows.

当前限制包括：

- 主逻辑仍主要集中在一个 Python 文件里；
- 依赖版本锁定还可以继续加强；
- 工程结构仍有整理空间；
- 更适合个人或小团队科研工作流。

---

## 21. Chinese Documentation / 中文文档

For a standalone Chinese document, see:

- [README.zh-CN.md](./README.zh-CN.md)

如果你只想看纯中文说明，请直接阅读：

- [README.zh-CN.md](./README.zh-CN.md)

---

## 22. License / 许可证

This repository uses the existing `LICENSE` file.

本仓库沿用现有 `LICENSE` 文件。
