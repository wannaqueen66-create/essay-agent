# essay-agent 中文说明

## 项目简介

`essay-agent` 是一个面向建筑学、体育空间、VR 环境、空间行为与行为轨迹研究场景的多源文献自动检索与 AI 结构化分析工具。

它可以完成这样一条完整流程：

1. 从多个学术数据源抓取近期论文
2. 调用 OpenAI 或兼容接口进行结构化分析
3. 生成中文摘要与研究字段提取结果
4. 根据相关性阈值进行筛选
5. 将历史结果写入 SQLite 数据库
6. 输出 Markdown / Excel / JSON 日报
7. 可选通过 Brevo SMTP 发送邮件

这个项目适合希望“每天自动收集新论文、快速做初筛、减少手动阅读摘要成本”的研究者。

---

## 已实现功能

### 1. 多源文献抓取

当前支持以下来源：

- arXiv
- OpenAlex
- Crossref
- Semantic Scholar

### 2. AI 结构化分析

程序会基于论文标题和英文摘要，生成适合空间研究场景使用的结构化分析，包括：

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

### 3. 英文摘要保留

系统会同时保留：

- 英文原始摘要
- 中文摘要
- 中文结构化分析

### 4. SQLite 缓存与历史记录

使用 `papers.db` 记录：

- 已抓取论文
- 已分析论文
- 是否达到相关性阈值
- 是否进入待展示池
- 是否已经展示
- 是否已经邮件上报

### 5. 相关性阈值过滤

可通过 `.env` 中的 `MIN_RELEVANCE_SCORE` 控制最低分数要求。

### 6. 待展示池补位

当当天新增的高相关论文数量不足时，会从最近若干天的待展示池中补位，保证日报不至于过空。

### 7. 输出日报

每次运行后默认输出：

- `output/arxiv_daily_YYYY-MM-DD.xlsx`
- `output/arxiv_daily_YYYY-MM-DD.md`
- `output/arxiv_daily_YYYY-MM-DD_stats.json`

### 8. 邮件推送

可通过 Brevo SMTP 发送日报邮件，包括：

- 邮件正文简报
- Markdown 附件
- Excel 附件
- JSON 统计附件

---

## 项目结构

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

运行过程中会额外生成：

```text
papers.db
output/
```

---

## 部署与运行

### 1. 安装系统环境

```bash
apt update && apt install -y python3 python3-pip python3-venv
```

### 2. 克隆仓库

```bash
git clone git@github.com:wannaqueen66-create/essay-agent.git
cd essay-agent
```

### 3. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 创建环境变量文件

```bash
cp .env.example .env
```

### 6. 编辑 `.env`

至少需要填写：

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4.1-mini
DAYS_BACK=2
MAX_RESULTS_PER_QUERY=30
MIN_RELEVANCE_SCORE=70
FORCE_REFRESH=false
```

如果需要启用邮件推送，还需要继续填写：

```env
EMAIL_ENABLED=true
EMAIL_SMTP_HOST=smtp-relay.brevo.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_brevo_smtp_username
EMAIL_PASSWORD=your_brevo_smtp_password
EMAIL_FROM=you@example.com
EMAIL_TO=you@example.com
EMAIL_USE_TLS=true
REPORT_TOP_N=10
EMAIL_TOP_N=5
PENDING_POOL_DAYS=7
EMPTY_REPORT_EMAIL=true
```

### 7. 运行程序

```bash
python arxiv_agent.py
```

---

## 配置说明

### `.env` 里常见参数

- `OPENAI_API_KEY`：OpenAI 或兼容提供商 API Key
- `OPENAI_BASE_URL`：兼容接口 Base URL
- `OPENAI_MODEL`：模型名称
- `DAYS_BACK`：抓取最近几天论文
- `MAX_RESULTS_PER_QUERY`：每个 query 在每个源抓多少条
- `MIN_RELEVANCE_SCORE`：最低相关性阈值
- `FORCE_REFRESH`：是否忽略缓存强制重跑
- `EMAIL_ENABLED`：是否启用邮件推送
- `REPORT_TOP_N`：Markdown 里展示多少条重点论文
- `EMAIL_TOP_N`：邮件正文里展示多少条重点论文
- `PENDING_POOL_DAYS`：待展示池时间窗口
- `EMPTY_REPORT_EMAIL`：日报为空时是否也发邮件

### `config.yaml` 里常见参数

- `queries`：arXiv 专用检索式
- `generic_queries`：OpenAlex / Crossref / Semantic Scholar 使用的自然语言检索式
- `sources`：启用的数据源
- `exclude_keywords`：排噪关键词
- `must_have_keywords`：必须命中的关键词
- `db_path`：数据库路径
- `analysis_retries`：模型分析失败重试次数
- `retry_delay_seconds`：重试间隔秒数

---

## 输出结果说明

### Excel

适合：

- 排序
- 筛选
- 人工复核
- 做后续综述整理

### Markdown

适合：

- 快速阅读
- 汇报展示
- 每日浏览高相关论文

### stats.json

适合：

- 查看运行统计
- 判断抓取是否正常
- 判断缓存命中和分析成功率

---

## 辅助脚本

### 查看数据库总览

```bash
python inspect_db.py
```

### 查看当前待展示池

```bash
python show_pending_pool.py
```

### 重置展示/上报状态

```bash
python reset_reported.py all
python reset_reported.py displayed
python reset_reported.py both
```

### 测试邮箱

```bash
python test_email.py
```

### 只用 output 结果重发邮件

```bash
python send_output_email.py --mark-db
python send_output_email.py --date 2026-03-08 --mark-db
```

---

## 推荐默认配置

建议第一次先用比较保守的参数跑通：

```env
OPENAI_MODEL=gpt-4.1-mini
DAYS_BACK=1
MAX_RESULTS_PER_QUERY=5
MIN_RELEVANCE_SCORE=70
FORCE_REFRESH=false
EMAIL_ENABLED=false
```

这样可以先验证：

- 数据源能否正常返回
- 模型接口能否正常工作
- 输出文件是否能正确生成
- 数据库是否能正常写入

---

## 当前限制

这个项目已经具备“可直接使用”的完整流程，但仍然属于偏实用型原型，主要限制包括：

1. 主逻辑仍然集中在单个 Python 文件中
2. 错误处理偏实用，日志可观测性不够强
3. `requirements.txt` 尚未锁定版本
4. 更适合个人科研使用，不算完全工程化项目

也就是说，它现在是一个：

- **能跑**
- **有闭环**
- **适合自己日常监测**

但如果以后要长期稳定维护、多人协作或公开交付，建议进一步做模块化拆分与工程整理。

---

## 总结

`essay-agent` 不是单纯的抓论文脚本，而是一个已经具备：

- 多源抓取
- AI 结构化分析
- SQLite 缓存
- 阈值过滤
- 待展示池补位
- 日报输出
- 邮件推送

完整闭环的实用型科研工具。

如果你的目标是每天自动监测建筑学 / 体育空间 / VR / 行为轨迹相关的新论文，这个项目是有实际使用价值的。
