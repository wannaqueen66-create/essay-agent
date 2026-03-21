#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# essay-agent 交互式一键部署脚本
# 适用于 Ubuntu/Debian 系 VPS（1C1G 及以上）
# 用法：sudo bash deploy.sh
# ============================================================

INSTALL_DIR="/opt/arxiv-agent"
SERVICE_USER="arxiv-agent"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$INSTALL_DIR/.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()  { echo -e "\n${CYAN}${BOLD}>>> $*${NC}"; }

# 交互式读取，带默认值
ask() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local input
    if [[ -n "$default" ]]; then
        read -rp "$(echo -e "${BOLD}$prompt${NC} [${default}]: ")" input
        eval "$var_name=\"${input:-$default}\""
    else
        read -rp "$(echo -e "${BOLD}$prompt${NC}: ")" input
        eval "$var_name=\"$input\""
    fi
}

# 交互式读取密码（不回显）
ask_secret() {
    local prompt="$1"
    local var_name="$2"
    local input
    read -srp "$(echo -e "${BOLD}$prompt${NC}: ")" input
    echo ""
    eval "$var_name=\"$input\""
}

# 是/否确认
confirm() {
    local prompt="$1"
    local default="${2:-y}"
    local yn
    if [[ "$default" == "y" ]]; then
        read -rp "$(echo -e "${BOLD}$prompt${NC} [Y/n]: ")" yn
        yn="${yn:-y}"
    else
        read -rp "$(echo -e "${BOLD}$prompt${NC} [y/N]: ")" yn
        yn="${yn:-n}"
    fi
    [[ "$yn" =~ ^[Yy] ]]
}

# --- 检查 root 权限 ---
if [[ $EUID -ne 0 ]]; then
    error "请使用 sudo 运行此脚本：sudo bash deploy.sh"
fi

echo ""
echo -e "${BOLD}=========================================="
echo "  essay-agent 部署向导"
echo -e "==========================================${NC}"
echo ""
echo "  本脚本将引导你完成以下步骤："
echo "  1. 安装系统依赖"
echo "  2. 配置 OpenAI API 参数"
echo "  3. 配置邮件推送（可选）"
echo "  4. 配置运行参数"
echo "  5. 安装 systemd 定时服务"
echo ""

if ! confirm "是否继续部署？"; then
    echo "已取消。"
    exit 0
fi

# ============================================================
# Step 1: 安装系统依赖
# ============================================================
step "1/5 安装系统依赖"
info "更新软件包列表 ..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git rsync > /dev/null
info "系统依赖安装完成"

# ============================================================
# Step 2: 配置 OpenAI API
# ============================================================
step "2/5 配置 OpenAI API"
echo ""
echo "  essay-agent 需要一个 OpenAI 或兼容接口来分析论文。"
echo "  支持 OpenAI、DeepSeek、Moonshot、本地 LLM 等任何兼容接口。"
echo ""

ask "OpenAI API Key" "" OPENAI_API_KEY
while [[ -z "$OPENAI_API_KEY" ]]; do
    warn "API Key 不能为空！"
    ask "OpenAI API Key" "" OPENAI_API_KEY
done

ask "API Base URL（直接回车表示使用 OpenAI 官方）" "" OPENAI_BASE_URL
ask "模型名称" "gpt-4.1-mini" OPENAI_MODEL

# ============================================================
# Step 3: 配置邮件（可选）
# ============================================================
step "3/5 配置邮件推送（可选）"
echo ""
echo "  配置后每天会自动发送日报邮件到你的邮箱。"
echo "  支持 Brevo（原 Sendinblue）SMTP 服务（免费注册即可使用）。"
echo ""

EMAIL_ENABLED="false"
EMAIL_SMTP_HOST="smtp-relay.brevo.com"
EMAIL_SMTP_PORT="587"
EMAIL_USERNAME=""
EMAIL_PASSWORD=""
EMAIL_FROM=""
EMAIL_TO=""
EMAIL_USE_TLS="true"

if confirm "是否启用邮件推送？" "n"; then
    EMAIL_ENABLED="true"
    ask "SMTP 主机" "smtp-relay.brevo.com" EMAIL_SMTP_HOST
    ask "SMTP 端口" "587" EMAIL_SMTP_PORT
    ask "SMTP 用户名" "" EMAIL_USERNAME
    ask_secret "SMTP 密码" EMAIL_PASSWORD
    ask "发件人邮箱" "" EMAIL_FROM
    ask "收件人邮箱（多个用英文逗号分隔）" "" EMAIL_TO
    info "邮件配置完成"
else
    info "跳过邮件配置，后续可编辑 $ENV_FILE 启用"
fi

# ============================================================
# Step 4: 运行参数
# ============================================================
step "4/5 配置运行参数"
echo ""
echo "  这些参数控制抓取范围和过滤强度。"
echo "  首次部署建议使用默认值，验证通过后再调整。"
echo ""

ask "抓取最近几天的论文（DAYS_BACK）" "2" DAYS_BACK
ask "每个 query 每个源最大抓取数（MAX_RESULTS_PER_QUERY）" "30" MAX_RESULTS_PER_QUERY
ask "最低相关性阈值 0-100（MIN_RELEVANCE_SCORE）" "70" MIN_RELEVANCE_SCORE
ask "Markdown 报告展示前 N 条（REPORT_TOP_N）" "10" REPORT_TOP_N
ask "邮件正文展示前 N 条（EMAIL_TOP_N）" "5" EMAIL_TOP_N

CORE_API_KEY=""
echo ""
echo "  CORE 是一个开放获取聚合器（3 亿+ 文档），需要免费 API key。"
echo "  申请地址：https://core.ac.uk/services/api"
if confirm "是否配置 CORE API Key？" "n"; then
    ask "CORE API Key" "" CORE_API_KEY
fi

# ============================================================
# Step 4.5: 配置定时运行时间
# ============================================================
echo ""
ask "每天自动运行时间（24 小时制，如 07:00）" "07:00" RUN_TIME

# ============================================================
# Step 5: 执行部署
# ============================================================
step "5/5 执行部署"

# 确认配置
echo ""
echo -e "${BOLD}部署配置确认：${NC}"
echo "  安装目录：$INSTALL_DIR"
echo "  模型：$OPENAI_MODEL"
echo "  API Base URL：${OPENAI_BASE_URL:-（OpenAI 官方）}"
echo "  邮件推送：$EMAIL_ENABLED"
if [[ "$EMAIL_ENABLED" == "true" ]]; then
    echo "  收件人：$EMAIL_TO"
fi
echo "  抓取天数：$DAYS_BACK"
echo "  相关性阈值：$MIN_RELEVANCE_SCORE"
echo "  定时运行：每天 $RUN_TIME"
echo ""

if ! confirm "确认以上配置，开始安装？"; then
    echo "已取消。"
    exit 0
fi

# --- 创建服务用户 ---
if ! id "$SERVICE_USER" &>/dev/null; then
    info "创建服务用户 $SERVICE_USER ..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# --- 部署应用文件 ---
info "部署应用到 $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
rsync -a --exclude='.git' --exclude='.venv' --exclude='papers.db' --exclude='output' \
    "$REPO_DIR/" "$INSTALL_DIR/"

# --- 创建虚拟环境 ---
info "创建 Python 虚拟环境 ..."
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
    python3 -m venv "$INSTALL_DIR/.venv"
fi
info "安装 Python 依赖 ..."
"$INSTALL_DIR/.venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"

# --- 写入 .env ---
info "写入配置文件 ..."
cat > "$ENV_FILE" <<ENVEOF
# OpenAI / OpenAI-compatible provider
OPENAI_API_KEY=$OPENAI_API_KEY
OPENAI_BASE_URL=$OPENAI_BASE_URL
OPENAI_MODEL=$OPENAI_MODEL

# Runtime fetch controls
DAYS_BACK=$DAYS_BACK
MAX_RESULTS_PER_QUERY=$MAX_RESULTS_PER_QUERY
MIN_RELEVANCE_SCORE=$MIN_RELEVANCE_SCORE
FORCE_REFRESH=false

# CORE API (optional)
CORE_API_KEY=$CORE_API_KEY

# Brevo email push
EMAIL_ENABLED=$EMAIL_ENABLED
EMAIL_SMTP_HOST=$EMAIL_SMTP_HOST
EMAIL_SMTP_PORT=$EMAIL_SMTP_PORT
EMAIL_USERNAME=$EMAIL_USERNAME
EMAIL_PASSWORD=$EMAIL_PASSWORD
EMAIL_FROM=$EMAIL_FROM
EMAIL_TO=$EMAIL_TO
EMAIL_USE_TLS=$EMAIL_USE_TLS
REPORT_TOP_N=$REPORT_TOP_N
EMAIL_TOP_N=$EMAIL_TOP_N
PENDING_POOL_DAYS=7
EMPTY_REPORT_EMAIL=true
ENVEOF

# --- 创建输出目录 ---
mkdir -p "$INSTALL_DIR/output"

# --- 设置权限 ---
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"
chmod 600 "$ENV_FILE"

# --- 安装 systemd 服务 ---
info "安装 systemd 服务 ..."
cp "$INSTALL_DIR/deploy/arxiv-agent.service" /etc/systemd/system/
cp "$INSTALL_DIR/deploy/arxiv-agent.timer" /etc/systemd/system/

# 补充 User 字段
if ! grep -q "^User=" /etc/systemd/system/arxiv-agent.service; then
    sed -i "/^\[Service\]/a User=$SERVICE_USER" /etc/systemd/system/arxiv-agent.service
fi

# 更新定时器时间
sed -i "s|OnCalendar=.*|OnCalendar=*-*-* ${RUN_TIME}:00|" /etc/systemd/system/arxiv-agent.timer

systemctl daemon-reload
systemctl enable arxiv-agent.timer
systemctl start arxiv-agent.timer

# --- 验证 ---
info "验证部署 ..."
TIMER_STATUS=$(systemctl is-active arxiv-agent.timer 2>/dev/null || true)
if [[ "$TIMER_STATUS" == "active" ]]; then
    info "定时器已激活"
else
    warn "定时器状态异常：$TIMER_STATUS"
fi

# --- 询问是否立即试运行 ---
echo ""
if confirm "部署完成！是否立即试运行一次？（大约 2-5 分钟）" "y"; then
    info "开始试运行 ..."
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/arxiv_agent.py" && {
        info "试运行成功！"
        echo ""
        echo "  检查输出文件："
        ls -la "$INSTALL_DIR/output/" 2>/dev/null || echo "  （无输出文件）"
    } || {
        warn "试运行出错，请检查日志：journalctl -u arxiv-agent"
    }
fi

echo ""
echo -e "${GREEN}${BOLD}=========================================="
echo "  部署完成！"
echo -e "==========================================${NC}"
echo ""
echo "  安装目录：$INSTALL_DIR"
echo "  配置文件：$INSTALL_DIR/.env"
echo "  定时任务：每天 $RUN_TIME 自动运行"
echo ""
echo "  常用命令："
echo "    手动运行：  sudo -u $SERVICE_USER $INSTALL_DIR/.venv/bin/python $INSTALL_DIR/arxiv_agent.py"
echo "    查看日志：  journalctl -u arxiv-agent -f"
echo "    修改配置：  sudo nano $INSTALL_DIR/.env"
echo "    修改期刊：  sudo nano $INSTALL_DIR/config.yaml"
echo "    定时器状态：systemctl status arxiv-agent.timer"
echo "    上次运行：  systemctl status arxiv-agent.service"
echo ""
