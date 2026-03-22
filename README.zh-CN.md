# essay-agent 纯中文说明文档

## 目录

- [1. 项目简介](#1-项目简介)
- [2. 这个项目解决什么问题](#2-这个项目解决什么问题)
- [3. 核心功能](#3-核心功能)
- [4. 支持的数据源](#4-支持的数据源)
- [5. 目标期刊监控](#5-目标期刊监控)
- [6. 项目结构](#6-项目结构)
- [7. 一条命令部署到 VPS](#7-一条命令部署到-vps)
- [8. 手动安装方式](#8-手动安装方式)
- [9. 交互式 env 配置说明](#9-交互式-env-配置说明)
- [10. 配置文件说明](#10-配置文件说明)
- [11. 如何运行](#11-如何运行)
- [12. 输出结果说明](#12-输出结果说明)
- [13. 辅助脚本说明](#13-辅助脚本说明)
- [14. systemd 定时运行](#14-systemd-定时运行)
- [15. 新手推荐默认配置](#15-新手推荐默认配置)
- [16. 常见问题](#16-常见问题)
- [17. 注意事项与当前限制](#17-注意事项与当前限制)
- [18. 许可证](#18-许可证)

---

## 1. 项目简介

`essay-agent` 是一个面向建筑学、体育空间、VR 环境、空间行为与行为轨迹研究场景的多源文献自动检索与 AI 结构化分析工具。

它不是一个只会“抓论文标题”的小脚本，而是一条完整工作流：

1. 从多个学术数据源抓取近期论文；
2. 使用 OpenAI 或兼容接口对论文标题与摘要做结构化分析；
3. 输出中文摘要、研究主题、研究方法、变量、行为指标、相关性评分等字段；
4. 把历史结果存入 SQLite，避免重复分析；
5. 根据相关性阈值筛选结果；
6. 生成 Markdown、Excel 和 JSON 日报；
7. 可选通过邮件自动推送结果。

它特别适合以下方向的日常文献监测：

- 建筑学
- 体育空间 / 体育设施
- VR 环境
- 空间行为
- 行为轨迹
- 环境感知
- VR + EEG / 眼动等交叉研究

---

## 2. 这个项目解决什么问题

做跨学科研究时，文献监测通常会遇到几个现实问题：

1. 论文分散在多个来源，不好统一追踪；
2. 单纯靠关键词搜索，噪音会非常大；
3. 即使找到论文，也还要逐篇读摘要，耗时很多；
4. 想做日报、周报或邮件推送时，经常还得手工整理；
5. 重复抓取、重复分析会浪费大量时间和 token 成本。

这个项目的目标，就是把“每天找文献、筛文献、总结文献”的过程自动化。

简单说，它帮你把文献监测变成一条稳定流程：

- 自动抓取
- 自动去重
- 自动分析
- 自动评分
- 自动生成报告
- 自动邮件发送

---

## 3. 核心功能

### 3.1 多源文献抓取

当前支持从多个来源抓取近期论文：

- arXiv
- OpenAlex
- Crossref
- Semantic Scholar
- Europe PMC
- CORE

### 3.2 AI 结构化分析

对每篇论文，程序会根据标题和英文摘要生成结构化结果，主要包括：

- 中文摘要
- 研究主题
- 空间/场景类型
- 研究场景
- 自变量
- 因变量
- 行为指标
- 生理/感知指标
- 研究方法
- 数据/样本
- 主要结论
- 与建筑/体育空间研究相关性
- 相关性分数
- 可借鉴启发

### 3.3 保留英文原始摘要

除了中文分析结果，系统还会同时保留英文原始摘要，方便后续人工复核。

### 3.4 SQLite 缓存与历史数据库

程序使用 `papers.db` 记录历史结果，主要用于：

- 避免重复抓取后的重复分析；
- 保留历史论文记录；
- 标记论文是否已展示；
- 标记论文是否已上报；
- 作为待展示池补位的数据基础。

### 3.5 相关性阈值过滤

你可以设置最小相关性分数，例如：

```env
MIN_RELEVANCE_SCORE=70
```

只有达到阈值的论文才会进入正式结果。

### 3.6 待展示池补位

如果当天新抓到的高相关论文不够多，系统会自动从最近几天的待展示池里补位，避免日报太空。

### 3.7 报告输出

程序会输出：

- Excel 报告
- Markdown 报告
- JSON 统计文件

### 3.8 邮件推送

如果配置了 SMTP，就可以自动发送日报邮件，正文带摘要，附件带完整报告文件。

### 3.9 一键部署 + 交互式配置

支持一条 bash 命令部署到 VPS，并在部署过程中进入交互式配置界面，让你填写 `.env` 所需参数，而不是自己先写配置文件。

---

## 4. 支持的数据源

| 数据源 | 类型 | 是否需要认证 | 说明 |
|---|---|---|---|
| arXiv | 预印本 | 否 | 支持分类检索，适合 CS/HCI/社科交叉方向 |
| OpenAlex | 聚合器 | 否 | 覆盖广，适合通用学术监测 |
| Crossref | 元数据 | 否 | DOI 与期刊元数据丰富 |
| Semantic Scholar | 聚合器 | 否 | AI / CS 方向较强 |
| Europe PMC | 生物医学 | 否 | VR、EEG、感知方向常有价值结果 |
| CORE | 开放获取聚合器 | 可选免费 API Key | 覆盖开放获取文献较广 |

你可以在 `config.yaml` 的 `sources` 中决定启用哪些来源。

---

## 5. 目标期刊监控

除了关键词检索外，这个项目还支持通过 ISSN 直接监控指定期刊。

这很重要，因为有些论文虽然标题没有完整命中关键词，但如果它发表在你真正关心的期刊上，你仍然会希望它被抓到。

项目里已经预置了一批示例期刊，覆盖：

- 建筑环境与空间行为
- 体育科学与运动空间
- VR / HCI / 感知
- 行为轨迹 / 时空行为 / 城市空间

如果你要增加更多期刊，可以在 `config.yaml` 的 `target_journals` 中继续加：

```yaml
target_journals:
  - name: Example Journal
    issn: 1234-5678
```

---

## 6. 项目结构

```text
essay-agent/
├── arxiv_agent.py              # 主程序
├── config.yaml                 # 检索式、数据源、目标期刊等配置
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
├── deploy.sh                   # 交互式一键部署脚本
├── deploy/
│   ├── arxiv-agent.service     # systemd 服务单元
│   └── arxiv-agent.timer       # systemd 定时器
├── inspect_db.py               # 数据库总览
├── reset_reported.py           # 重置展示/上报状态
├── send_output_email.py        # 重发已有 output 报告
├── show_pending_pool.py        # 查看待展示池
├── test_email.py               # 测试 SMTP 配置
├── README.md                   # 中英双语说明
├── README.zh-CN.md             # 本文档（纯中文）
└── LICENSE
```

运行后会额外生成：

```text
papers.db
output/
```

---

## 7. 一条命令部署到 VPS

如果你的 VPS 已经有 `curl` 和 `sudo`，推荐直接使用下面这条命令：

```bash
curl -fsSL https://raw.githubusercontent.com/wannaqueen66-create/essay-agent/main/deploy.sh | sudo bash
```

### 这条命令符合什么预期

你的预期是：

> 一条 bash 命令复制到 VPS 执行，然后它自动完成安装，并进入交互式配置 env 的界面。

现在这个脚本的设计就是按这个预期来的。

### 脚本会自动做什么

执行后，它会：

1. 安装系统依赖；
2. 拉取项目代码；
3. 进入交互式配置流程；
4. 询问 OpenAI API 配置；
5. 询问是否启用邮件推送；
6. 询问 SMTP 参数（如果启用邮件）；
7. 询问抓取天数、相关性阈值等运行参数；
8. 自动生成 `.env`；
9. 创建 Python 虚拟环境；
10. 安装依赖；
11. 安装 systemd 定时服务；
12. 可选立即试运行一次。

也就是说，你不需要先手动写 `.env`，部署脚本会在过程中一步步问你。

---

## 8. 手动安装方式

如果你不想用一键脚本，也可以手动安装。

### 8.1 安装系统依赖

```bash
apt update && apt install -y python3 python3-pip python3-venv git
```

### 8.2 克隆仓库

```bash
git clone git@github.com:wannaqueen66-create/essay-agent.git
cd essay-agent
```

### 8.3 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 8.4 安装依赖

```bash
pip install -r requirements.txt
```

### 8.5 创建并编辑 `.env`

```bash
cp .env.example .env
nano .env
```

### 8.6 运行程序

```bash
python arxiv_agent.py
```

---

## 9. 交互式 env 配置说明

如果你使用一键部署脚本，它会交互式询问你以下参数：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- 是否启用邮件
- SMTP 主机、端口、用户名、密码、发件人、收件人
- `DAYS_BACK`
- `MAX_RESULTS_PER_QUERY`
- `MIN_RELEVANCE_SCORE`
- `REPORT_TOP_N`
- `EMAIL_TOP_N`
- `PENDING_POOL_DAYS`
- `CORE_API_KEY`（可选）
- 每日自动运行时间

这些参数会自动写入 `.env`，所以部署时你不需要手工先建文件。

---

## 10. 配置文件说明

### 10.1 `.env` 运行时配置

| 变量 | 说明 |
|---|---|
| `OPENAI_API_KEY` | OpenAI 或兼容接口 API Key |
| `OPENAI_BASE_URL` | 兼容接口 Base URL |
| `OPENAI_MODEL` | 模型名称 |
| `DAYS_BACK` | 抓取最近多少天论文 |
| `MAX_RESULTS_PER_QUERY` | 每个 query 每个源最大抓取数 |
| `MIN_RELEVANCE_SCORE` | 最低相关性阈值 |
| `FORCE_REFRESH` | 是否强制忽略缓存重跑 |
| `CORE_API_KEY` | CORE 可选 API Key |
| `EMAIL_ENABLED` | 是否启用邮件推送 |
| `EMAIL_SMTP_HOST` | SMTP 主机 |
| `EMAIL_SMTP_PORT` | SMTP 端口 |
| `EMAIL_USERNAME` | SMTP 用户名 |
| `EMAIL_PASSWORD` | SMTP 密码 |
| `EMAIL_FROM` | 发件人邮箱 |
| `EMAIL_TO` | 收件人列表 |
| `EMAIL_USE_TLS` | 是否启用 TLS |
| `REPORT_TOP_N` | Markdown 展示前 N 条 |
| `EMAIL_TOP_N` | 邮件正文展示前 N 条 |
| `PENDING_POOL_DAYS` | 待展示池天数 |
| `EMPTY_REPORT_EMAIL` | 日报为空时是否仍发邮件 |

### 10.2 `config.yaml` 项目配置

| 配置项 | 说明 |
|---|---|
| `queries` | arXiv 专用检索式 |
| `generic_queries` | 其他文献源通用检索式 |
| `target_journals` | 基于 ISSN 的期刊监控列表 |
| `sources` | 启用的数据源 |
| `exclude_keywords` | 排噪关键词 |
| `must_have_keywords` | 必须命中的关键词 |
| `db_path` | SQLite 数据库路径 |
| `analysis_retries` | 分析失败重试次数 |
| `retry_delay_seconds` | 重试间隔 |

---

## 11. 如何运行

### 手动运行一次

```bash
python arxiv_agent.py
```

### 如果是通过部署脚本安装到 `/opt/arxiv-agent`

```bash
sudo -u arxiv-agent /opt/arxiv-agent/.venv/bin/python /opt/arxiv-agent/arxiv_agent.py
```

### 查看日志

```bash
journalctl -u arxiv-agent -f
```

---

## 12. 输出结果说明

每次运行后，会在 `output/` 下生成：

```text
output/arxiv_daily_YYYY-MM-DD.xlsx
output/arxiv_daily_YYYY-MM-DD.md
output/arxiv_daily_YYYY-MM-DD_stats.json
```

### Excel 文件

适合：

- 排序
- 筛选
- 人工复核
- 后续综述整理

### Markdown 文件

适合：

- 快速阅读
- 日报汇报
- 浏览 TOP 论文

### stats.json 文件

适合：

- 查看运行统计
- 判断抓取是否正常
- 判断数据源是否有问题
- 判断缓存是否生效

如果最终收录为 0 篇，报告中仍会保留完整诊断信息，而不是只给一句“今天没有论文”。

---

## 13. 辅助脚本说明

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

### 各脚本作用

- `inspect_db.py`：查看数据库总览
- `show_pending_pool.py`：查看待展示池
- `reset_reported.py`：重置展示 / 上报状态
- `test_email.py`：只测试 SMTP 邮件发送
- `send_output_email.py`：不重跑主流程，只用现有 output 文件补发邮件

---

## 14. systemd 定时运行

项目自带：

- `deploy/arxiv-agent.service`
- `deploy/arxiv-agent.timer`

### 常用命令

```bash
systemctl status arxiv-agent.timer
systemctl status arxiv-agent.service
journalctl -u arxiv-agent -n 200 --no-pager
journalctl -u arxiv-agent -f
```

如果你使用一键部署脚本，这些会自动安装好。

---

## 15. 新手推荐默认配置

第一次运行建议先保守一点：

```env
OPENAI_MODEL=gpt-4.1-mini
DAYS_BACK=1
MAX_RESULTS_PER_QUERY=5
MIN_RELEVANCE_SCORE=70
FORCE_REFRESH=false
EMAIL_ENABLED=false
```

这样做的好处是：

- 成本更低
- 更容易排错
- 首次运行更快
- 结果噪音更少

---

## 16. 常见问题

### 16.1 缺少 Python 包

```bash
pip install -r requirements.txt
```

### 16.2 没抓到论文

优先检查：

- `DAYS_BACK` 是否太小
- `MIN_RELEVANCE_SCORE` 是否太高
- 某个数据源是否暂时不可用
- 检索式是否过窄

### 16.3 邮件发送失败

检查：

- SMTP 用户名 / 密码
- 发件人地址
- 收件人地址
- VPS 是否屏蔽出站 SMTP

### 16.4 想一条命令部署并交互式配置

直接用：

```bash
curl -fsSL https://raw.githubusercontent.com/wannaqueen66-create/essay-agent/main/deploy.sh | sudo bash
```

这就是当前推荐的部署方式。

---

## 17. 注意事项与当前限制

这个项目已经具备完整闭环，适合日常科研监测，但它更偏向：

- **实用型科研工具**

而不是：

- **高度模块化的企业级工程系统**

当前限制主要包括：

1. 主逻辑仍主要集中在单个 Python 文件中；
2. 依赖版本锁定还可以继续加强；
3. 工程结构还有进一步拆分空间；
4. 更适合个人或小团队研究使用。

但就“每日文献监测 + AI 分析 + 日报输出 + 邮件推送”这个目标来说，它已经是一个能真正上手使用的项目，而不是只有概念的 demo。

---

## 18. 许可证

本仓库沿用现有 `LICENSE` 文件。
