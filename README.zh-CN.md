# essay-agent 纯中文说明文档

## 目录

- [1. 项目简介](#1-项目简介)
- [2. 适合谁用](#2-适合谁用)
- [3. 这个项目解决什么问题](#3-这个项目解决什么问题)
- [4. 为什么它有用](#4-为什么它有用)
- [5. 核心功能](#5-核心功能)
- [6. 支持的数据源](#6-支持的数据源)
- [7. 目标期刊监控](#7-目标期刊监控)
- [8. 项目结构](#8-项目结构)
- [9. 一条命令部署到 VPS](#9-一条命令部署到-vps)
- [10. 手动安装方式](#10-手动安装方式)
- [11. 交互式 env 配置说明](#11-交互式-env-配置说明)
- [12. 配置文件说明](#12-配置文件说明)
- [13. 如何运行](#13-如何运行)
- [14. 更新与升级](#14-更新与升级)
- [15. 输出结果说明](#15-输出结果说明)
- [16. 辅助脚本说明](#16-辅助脚本说明)
- [17. systemd 定时运行](#17-systemd-定时运行)
- [18. 新手推荐默认配置](#18-新手推荐默认配置)
- [19. 常见问题](#19-常见问题)
- [20. 注意事项与当前限制](#20-注意事项与当前限制)
- [21. 许可证](#21-许可证)

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

## 2. 适合谁用

这个项目尤其适合：

- 需要每天监测新论文的研究者；
- 希望先看中文摘要，而不是逐篇手动读英文摘要的人；
- 建筑学 / 体育空间 / 空间行为 / VR 方向的研究者；
- 想把任务稳定跑在 VPS 上的人；
- 喜欢“复制一条命令就部署”的使用方式的人。

如果你的需求是：

- 定期盯文献；
- 自动做初筛；
- 减少机械重复劳动；
- 形成结构化日报；

那么这个项目就是为这种工作流准备的。

---

## 3. 这个项目解决什么问题

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

## 4. 为什么它有用

这个项目真正有价值的地方，不是“它会抓论文”，而是：

它把下面这些事情串成了一个闭环：

- 检索
- 分析
- 过滤
- 存储
- 汇报
- 推送

所以它不是停留在“抓到标题就结束”的小工具，而是已经接近一个能长期服务日常研究工作的实用系统。

在实际使用里，这意味着：

- 少手工读摘要；
- 少重复做检索；
- 更容易形成稳定的日报习惯；
- 更容易积累自己的领域文献数据库；
- 更适合放在 VPS 上长期运行。

---

## 5. 核心功能

### 5.1 多源文献抓取

当前支持从多个来源抓取近期论文：

- arXiv
- OpenAlex
- Crossref
- Semantic Scholar
- Europe PMC
- CORE

### 5.2 AI 结构化分析

对每篇论文，程序会根据标题和摘要生成结构化结果，主要包括：

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

### 5.3 保留英文原始摘要

除了中文分析结果，系统还会同时保留英文原始摘要，方便后续人工复核。

### 5.4 SQLite 缓存与历史数据库

程序使用 `papers.db` 记录历史结果，主要用于：

- 避免重复抓取后的重复分析；
- 保留历史论文记录；
- 标记论文是否已展示；
- 标记论文是否已上报；
- 作为待展示池补位的数据基础。

### 5.5 相关性阈值过滤

你可以设置最小相关性分数，例如：

```env
MIN_RELEVANCE_SCORE=60
```

只有达到阈值的论文才会进入正式结果。

### 5.6 待展示池补位

如果当天新抓到的高相关论文不够多，系统会自动从最近几天的待展示池里补位，避免日报太空。

### 5.7 报告输出

程序会输出：

- Excel 报告
- Markdown 报告
- JSON 统计文件

### 5.8 邮件推送

如果配置了 SMTP，就可以自动发送日报邮件，正文带摘要，附件带完整报告文件。

### 5.9 一键部署 + 交互式配置

支持一条 bash 命令部署到 VPS，并在部署过程中进入交互式配置界面，让你填写 `.env` 所需参数，而不是自己先写配置文件。

---

## 6. 支持的数据源

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

## 7. 目标期刊监控

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

## 8. 项目结构

```text
essay-agent/
├── arxiv_agent.py              # 主程序
├── config.yaml                 # 检索式、数据源、目标期刊等配置
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
├── deploy.sh                   # 首次安装 / 部署脚本
├── esag                        # 交互式运维管理脚本
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

## 9. 一条命令部署到 VPS

如果你的 VPS 已经有 `curl` 和 `sudo`，推荐直接使用下面这条命令。

这条命令用于：

- **首次安装**
- **首次部署**
- **首次交互式配置**

```bash
curl -fsSL https://raw.githubusercontent.com/wannaqueen66-create/essay-agent/main/deploy.sh | sudo bash
```

### 这条命令符合什么预期

你的预期是：

> 一条 bash 命令复制到 VPS 执行，然后它自动完成安装，并进入交互式配置 env 的界面。

现在这个脚本的设计就是按这个预期来的。

### 关于 `curl ... | sudo bash` 的说明

这个安装脚本已经专门适配了下面这种执行方式：

```bash
curl -fsSL https://raw.githubusercontent.com/wannaqueen66-create/essay-agent/main/deploy.sh | sudo bash
```

即使脚本是通过管道喂给 `bash` 的，它也会从 `/dev/tty` 读取你的交互输入，所以你仍然可以正常在终端里输入 API Key、邮件参数和运行配置。

### 交互输入里的默认值说明

脚本运行过程中，凡是你看到：

- `[默认值]`
- `[Y/n]`
- `[y/N]`

都表示这个问题支持直接回车使用默认项。

也就是说：

- 如果看到 `[默认值]`，直接回车 = 使用该默认值；
- 如果看到 `[Y/n]` 或 `[y/N]`，直接回车 = 使用括号里给出的默认选择；
- 邮件推送默认关闭，直接回车即可跳过；
- CORE API 默认不配置，直接回车即可跳过；
- 只有没有默认值的字段，才需要你明确手动输入。

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

## 10. 手动安装方式

如果你不想用一键脚本，也可以手动安装。

### 10.1 安装系统依赖

```bash
apt update && apt install -y python3 python3-pip python3-venv git
```

### 10.2 克隆仓库

```bash
git clone git@github.com:wannaqueen66-create/essay-agent.git
cd essay-agent
```

### 10.3 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 10.4 安装依赖

```bash
pip install -r requirements.txt
```

### 10.5 创建并编辑 `.env`

```bash
cp .env.example .env
nano .env
```

### 10.6 运行程序

```bash
python arxiv_agent.py
```

---

## 11. 交互式 env 配置说明

如果你使用一键部署脚本，它会交互式询问你以下参数：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- 当你填完 API key 和 base URL 后，脚本会自动尝试拉取可用模型列表，并展示候选模型，方便你选择
- 如果成功拉到模型列表，你既可以输入编号（如 `1`、`2`、`3`），也可以直接输入完整模型名
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

## 12. 配置文件说明

### CORE API 注册流程

如果你想启用 CORE 数据源，需要先申请一个 CORE API Key。

申请入口：

- <https://core.ac.uk/services/api>

一般流程是：

1. 打开 CORE API 页面；
2. 注册或登录；
3. 创建一个 API key；
4. 把 key 填进 `.env` 里的 `CORE_API_KEY`。

如果你暂时没有 CORE key，也没关系，项目仍然可以依赖其他数据源继续运行。

### 12.1 `.env` 运行时配置

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

### 12.2 `config.yaml` 项目配置

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

## 13. 如何运行

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

## 14. 更新与升级

首次安装完成后，推荐的日常运维入口是：

```bash
sudo esag
```

现在的 `esag` 已经更接近一个菜单式终端控制台了，它提供：

- 状态首页
- 核心配置子菜单
- 邮件配置子菜单
- 数据源 / CORE 子菜单
- 日志与诊断子菜单
- 维护操作子菜单

通过 `esag`，你可以交互式完成：

- 查看状态总览
- 手动运行主程序
- 直接在菜单里修改核心配置（模型、抓取天数、抓取上限、相关性阈值、报告展示数量、定时运行时间）
- 直接在菜单里修改邮件配置
- 管理 CORE API Key
- 查看日志
- 查看数据库状态
- 查看待展示池
- 测试邮箱
- 重新执行部署脚本做升级/重配
- 卸载项目


如果你已经部署过一次，后续想升级，推荐做法也很简单：

```bash
curl -fsSL https://raw.githubusercontent.com/wannaqueen66-create/essay-agent/main/deploy.sh | sudo bash
```

这个部署脚本是可重复使用的。再次执行时，它会：

- 拉取最新仓库代码；
- 继续使用同一个安装目录；
- 刷新 service / timer；
- 如有需要重新进入交互式配置；
- 可选再试运行一次。

### 如果你只想改运行参数

```bash
sudo nano /opt/arxiv-agent/.env
sudo systemctl restart arxiv-agent.timer
```

### 如果你只改了 `config.yaml`

```bash
sudo nano /opt/arxiv-agent/config.yaml
```

下次运行时就会自动使用新的配置。

---

## 15. 输出结果说明

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

## 16. 辅助脚本说明

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

## 17. systemd 定时运行

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

## 18. 新手推荐默认配置

第一次运行建议先保守一点：

```env
OPENAI_MODEL=gpt-4.1-mini
DAYS_BACK=1
MAX_RESULTS_PER_QUERY=10
MIN_RELEVANCE_SCORE=60
FORCE_REFRESH=false
EMAIL_ENABLED=false
```

这样做的好处是：

- 成本更低
- 更容易排错
- 首次运行更快
- 结果噪音更少

---

## 19. 常见问题

### 19.1 缺少 Python 包

```bash
pip install -r requirements.txt
```

### 19.2 没抓到论文

优先检查：

- `DAYS_BACK` 是否太小
- `MIN_RELEVANCE_SCORE` 是否太高
- 某个数据源是否暂时不可用
- 检索式是否过窄

### 19.3 邮件发送失败

检查：

- SMTP 用户名 / 密码
- 发件人地址
- 收件人地址
- VPS 是否屏蔽出站 SMTP

### 19.4 想一条命令部署并交互式配置

直接用：

```bash
curl -fsSL https://raw.githubusercontent.com/wannaqueen66-create/essay-agent/main/deploy.sh | sudo bash
```

这就是当前推荐的部署方式。

---

## 20. 注意事项与当前限制

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

## 21. 许可证

本仓库沿用现有 `LICENSE` 文件。
