# essay-agent 中文说明

## 项目简介

`essay-agent` 是一个面向建筑学、体育空间、VR 环境、空间行为与行为轨迹研究场景的多源文献自动检索与 AI 结构化分析工具。

它可以完成这样一条完整流程：

1. 从 6 个学术数据源 + 目标顶刊抓取近期论文
2. 调用 OpenAI 或兼容接口进行结构化分析（中文摘要 + 14 个结构化字段）
3. 根据相关性阈值进行筛选
4. 将历史结果写入 SQLite 数据库（带缓存和去重）
5. 输出 Markdown / Excel / JSON 日报
6. 可选通过 Brevo SMTP 发送邮件（含 0 篇诊断信息）

---

## 功能特性

- **6 个数据源** — arXiv、OpenAlex、Crossref、Semantic Scholar、Europe PMC、CORE
- **顶刊直接监控** — 通过 ISSN 过滤直接追踪 16+ 本领域核心期刊
- **AI 结构化分析** — 中文摘要 + 研究主题、自变量/因变量、方法、结论、相关性分数等
- **SQLite 优化** — WAL 模式、索引、批量提交，适配低配 VPS
- **结构化日志** — 带时间戳和级别，异常完整记录
- **诊断报告** — 0 篇时邮件/Markdown 显示完整诊断链（各源状态、各阶段过滤数、可能原因）
- **速率限制** — API 调用间自动延时，防止 429 错误
- **待展示池补位** — 当日不足时自动从近期高分论文补充
- **一键部署** — `deploy.sh` 支持 Ubuntu/Debian VPS 一键安装
- **systemd 定时** — 每天 07:00 自动运行，带内存/CPU 限制保护
- **1C1G 适配** — 内存限制 768M，CPU 限制 80%

---

## 支持的数据源

| 数据源 | 类型 | 需要认证 | 说明 |
|--------|------|----------|------|
| **arXiv** | 预印本 | 否 | 支持分类检索（cs.HC、physics.soc-ph 等） |
| **OpenAlex** | 聚合器 | 否 | 覆盖面广，倒排索引摘要重建 |
| **Crossref** | 元数据 | 否 | 基于 DOI，期刊文章 |
| **Semantic Scholar** | 聚合器 | 否 | AI/NLP 方向强，限速 1 req/sec |
| **Europe PMC** | 生物医学 | 否 | VR + EEG/眼动方向特别有价值 |
| **CORE** | 开放获取 | 免费 API key | 3 亿+ 文档，灰色文献和会议论文 |

在 `config.yaml` → `sources` 中配置启用的数据源。

---

## 目标期刊监控

除了关键词检索外，essay-agent 还能通过 OpenAlex ISSN 过滤直接监控指定期刊的最新论文。这样即使论文标题/摘要不包含你的检索关键词，只要发表在目标期刊上就会被抓取到。

已预置的期刊（在 `config.yaml` → `target_journals` 中配置）：

**建筑环境与空间行为：**
- Building and Environment (0360-1323)
- Environment and Behavior (0013-9165)
- Journal of Environmental Psychology (0272-4944)
- Architectural Science Review (0003-8628)
- Indoor Air (1600-0668)

**体育科学与运动空间：**
- Journal of Sports Sciences (0264-0414)
- International Review for the Sociology of Sport (1012-6902)
- European Sport Management Quarterly (1618-4742)

**VR / 人机交互 / 感知：**
- Virtual Reality (1359-4338)
- Computers in Human Behavior (0747-5632)
- International Journal of Human-Computer Studies (1071-5819)
- Presence: Teleoperators and Virtual Environments (1054-7460)

**行为轨迹 / 时空行为 / 城市空间：**
- Transportation Research Part C (0968-090X)
- Journal of Transport Geography (0966-6923)
- Computers, Environment and Urban Systems (0198-9715)
- Applied Geography (0143-6228)

添加更多期刊：在 `target_journals` 列表中加入 `name` 和 `issn` 即可。ISSN 可在 [OpenAlex Sources](https://openalex.org/sources) 或期刊官网查到。

---

## 项目结构

```text
essay-agent/
├── arxiv_agent.py          # 主程序
├── config.yaml             # 配置（检索式、数据源、期刊列表）
├── requirements.txt        # Python 依赖（已锁定版本范围）
├── .env.example            # 环境变量模板
├── deploy.sh               # 一键部署脚本
├── deploy/
│   ├── arxiv-agent.service # systemd 服务单元
│   └── arxiv-agent.timer   # systemd 定时器
├── inspect_db.py           # 数据库检查
├── reset_reported.py       # 重置展示/上报状态
├── send_output_email.py    # 重发已有报告
├── show_pending_pool.py    # 查看待展示池
├── test_email.py           # 测试邮箱配置
├── README.md
├── README.zh-CN.md
└── LICENSE
```

运行时生成：

```text
papers.db                   # SQLite 数据库（WAL 模式）
output/                     # 日报输出目录
```

---

## 部署与运行

### 手动部署

```bash
# 1. 安装系统依赖
apt update && apt install -y python3 python3-pip python3-venv

# 2. 克隆仓库
git clone git@github.com:wannaqueen66-create/essay-agent.git
cd essay-agent

# 3. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 创建并编辑环境变量
cp .env.example .env
# 编辑 .env：填写 OPENAI_API_KEY 等

# 6. 运行
python arxiv_agent.py
```

### 一键部署（推荐）

适用于 Ubuntu/Debian VPS（1C1G 及以上）：

```bash
sudo bash deploy.sh
```

部署脚本会自动完成：
1. 安装系统依赖
2. 创建服务用户 `arxiv-agent`
3. 部署应用到 `/opt/arxiv-agent`
4. 创建虚拟环境并安装依赖
5. 从模板创建 `.env`（需手动编辑）
6. 安装 systemd 服务和定时器（每天 07:00）
7. 设置权限（`.env` 为 600）

部署后：

```bash
# 编辑配置
sudo nano /opt/arxiv-agent/.env

# 手动运行一次
sudo -u arxiv-agent /opt/arxiv-agent/.venv/bin/python /opt/arxiv-agent/arxiv_agent.py

# 查看日志
journalctl -u arxiv-agent -f

# 定时器状态
systemctl status arxiv-agent.timer
```

---

## 环境变量说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | *（必填）* | OpenAI 或兼容接口 API Key |
| `OPENAI_BASE_URL` | *（空）* | 兼容接口 Base URL |
| `OPENAI_MODEL` | `gpt-4.1-mini` | 模型名称 |
| `DAYS_BACK` | `2` | 抓取最近几天的论文 |
| `MAX_RESULTS_PER_QUERY` | `30` | 每个 query 每个源最大抓取数 |
| `MIN_RELEVANCE_SCORE` | `70` | 最低相关性阈值（0-100） |
| `FORCE_REFRESH` | `false` | 忽略缓存强制重跑 |
| `CORE_API_KEY` | *（空）* | CORE 免费 API key |
| `EMAIL_ENABLED` | `false` | 启用邮件推送 |
| `EMAIL_SMTP_HOST` | `smtp-relay.brevo.com` | SMTP 主机 |
| `EMAIL_SMTP_PORT` | `587` | SMTP 端口 |
| `EMAIL_USERNAME` | | SMTP 用户名 |
| `EMAIL_PASSWORD` | | SMTP 密码 |
| `EMAIL_FROM` | | 发件人 |
| `EMAIL_TO` | | 收件人（多个用英文逗号分隔） |
| `EMAIL_USE_TLS` | `true` | 启用 TLS |
| `REPORT_TOP_N` | `10` | Markdown 展示前 N 条 |
| `EMAIL_TOP_N` | `5` | 邮件正文展示前 N 条 |
| `PENDING_POOL_DAYS` | `7` | 待展示池时间窗口 |
| `EMPTY_REPORT_EMAIL` | `true` | 0 篇时也发邮件（含诊断信息） |

---

## 配置说明

### config.yaml 主要配置项

| 配置项 | 说明 |
|--------|------|
| `queries` | arXiv 专用检索式（含 `cat:` 分类语法） |
| `generic_queries` | 通用文献源检索式（OpenAlex/Crossref/Semantic Scholar/Europe PMC） |
| `target_journals` | 目标期刊 ISSN 列表（通过 OpenAlex 过滤） |
| `sources` | 启用的数据源列表 |
| `exclude_keywords` | 排噪关键词 |
| `must_have_keywords` | 必须命中的关键词 |
| `db_path` | 数据库路径 |
| `analysis_retries` | AI 分析重试次数 |
| `retry_delay_seconds` | 重试间隔（指数退避） |

---

## 输出结果

每次运行后生成：

```text
output/arxiv_daily_YYYY-MM-DD.xlsx       # 可排序筛选的表格
output/arxiv_daily_YYYY-MM-DD.md         # 可阅读的报告（含 TOP N）
output/arxiv_daily_YYYY-MM-DD_stats.json # 运行统计（含各源状态）
```

当收录 0 篇时，Markdown 和邮件报告会自动包含完整诊断信息：
- 各阶段过滤数量（总抓取、日期过旧、重复、排除关键词、阈值不达标等）
- 各数据源独立状态（抓取数 / 错误信息）
- 可能原因建议

---

## 辅助脚本

```bash
python inspect_db.py                          # 数据库总览
python show_pending_pool.py                   # 查看待展示池
python reset_reported.py all|displayed|both   # 重置状态
python test_email.py                          # 测试邮箱
python send_output_email.py --mark-db         # 重发今日报告
python send_output_email.py --date 2026-03-08 # 重发历史报告
```

---

## 推荐默认配置

第一次运行建议用保守参数：

```env
OPENAI_MODEL=gpt-4.1-mini
DAYS_BACK=1
MAX_RESULTS_PER_QUERY=5
MIN_RELEVANCE_SCORE=70
FORCE_REFRESH=false
EMAIL_ENABLED=false
```

验证通过后再逐步放大 `DAYS_BACK` 和 `MAX_RESULTS_PER_QUERY`。

---

## systemd 定时服务

项目在 `deploy/` 目录下提供了现成的 systemd 文件：

- `arxiv-agent.service` — oneshot 服务，含内存/CPU 限制
  - `MemoryMax=768M`（保护 1G VPS 不被 OOM kill）
  - `CPUQuota=80%`（防止独占单核）
  - `TimeoutStartSec=600`（10 分钟超时保护）
- `arxiv-agent.timer` — 每天 07:00 触发，`Persistent=true`（错过时间开机补跑）

手动安装：

```bash
sudo cp deploy/arxiv-agent.service deploy/arxiv-agent.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now arxiv-agent.timer
```

或直接使用 `sudo bash deploy.sh` 自动安装。

---

## 许可证

本仓库使用已有的 `LICENSE` 文件。
