#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# essay-agent 交互式一键部署脚本
# 支持两种用法：
# 1) 仓库内执行：sudo bash deploy.sh
# 2) 远程一键执行：curl -fsSL <raw-url>/deploy.sh | sudo bash
# ============================================================

REPO_SSH_URL="git@github.com:wannaqueen66-create/essay-agent.git"
REPO_HTTPS_URL="https://github.com/wannaqueen66-create/essay-agent.git"
DEFAULT_BRANCH="main"
INSTALL_DIR="/opt/arxiv-agent"
SERVICE_USER="arxiv-agent"
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

require_tty() {
    if [[ ! -r /dev/tty ]]; then
        error "当前没有可用的交互终端（/dev/tty 不可读），无法进入交互式配置。"
    fi
}

ask() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local input=""
    require_tty
    if [[ -n "$default" ]]; then
        read -r -p "$(echo -e "${BOLD}$prompt${NC} [${default}]: ")" input < /dev/tty || true
        eval "$var_name=\"${input:-$default}\""
    else
        read -r -p "$(echo -e "${BOLD}$prompt${NC}: ")" input < /dev/tty || true
        eval "$var_name=\"${input:-}\""
    fi
}

ask_secret() {
    local prompt="$1"
    local var_name="$2"
    local input=""
    require_tty
    read -r -s -p "$(echo -e "${BOLD}$prompt${NC}: ")" input < /dev/tty || true
    echo "" > /dev/tty
    eval "$var_name=\"${input:-}\""
}

confirm() {
    local prompt="$1"
    local default="${2:-y}"
    local yn=""
    require_tty
    if [[ "$default" == "y" ]]; then
        read -r -p "$(echo -e "${BOLD}$prompt${NC} [Y/n]: ")" yn < /dev/tty || true
        yn="${yn:-y}"
    else
        read -r -p "$(echo -e "${BOLD}$prompt${NC} [y/N]: ")" yn < /dev/tty || true
        yn="${yn:-n}"
    fi
    [[ "$yn" =~ ^[Yy]$ ]]
}

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
echo "  2. 拉取 / 更新项目代码"
echo "  3. 交互式配置 OpenAI 与邮件参数"
echo "  4. 安装 Python 虚拟环境与依赖"
echo "  5. 安装 systemd 服务与定时任务"
echo ""
echo "  交互说明："
echo "  - 看到 [默认值] 的选项时，直接回车 = 使用默认值"
echo "  - y/n 题如果有 [Y/n] 或 [y/N]，直接回车 = 使用括号里的默认选项"
echo "  - 没有默认值的字段，需要你手动输入"
echo ""

if ! confirm "是否继续部署？"; then
    echo "已取消。"
    exit 0
fi

step "1/5 安装系统依赖"
info "更新软件包列表 ..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git ca-certificates >/dev/null
info "系统依赖安装完成"

step "2/5 获取项目代码"
TMP_SRC="$(mktemp -d /tmp/essay-agent-src.XXXXXX)"
trap 'rm -rf "$TMP_SRC"' EXIT

info "尝试通过 HTTPS 拉取仓库 ..."
if git clone --depth=1 --branch "$DEFAULT_BRANCH" "$REPO_HTTPS_URL" "$TMP_SRC" >/dev/null 2>&1; then
    info "仓库拉取成功"
else
    error "无法拉取仓库：$REPO_HTTPS_URL"
fi

if [[ ! -f "$TMP_SRC/arxiv_agent.py" || ! -f "$TMP_SRC/config.yaml" || ! -f "$TMP_SRC/requirements.txt" ]]; then
    error "拉取到的仓库内容不完整，缺少核心文件。"
fi

step "3/5 配置 OpenAI / 邮件 / 运行参数"
echo ""
echo "  essay-agent 需要一个 OpenAI 或兼容接口来分析论文。"
echo "  支持 OpenAI、DeepSeek、Moonshot、本地兼容接口等。"
echo ""

ask "OpenAI API Key" "" OPENAI_API_KEY
while [[ -z "$OPENAI_API_KEY" ]]; do
    warn "API Key 不能为空！"
    ask "OpenAI API Key" "" OPENAI_API_KEY
done
ask "API Base URL（回车表示使用官方 OpenAI）" "" OPENAI_BASE_URL

DEFAULT_MODEL="gpt-4.1-mini"
OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
OPENAI_BASE_URL="${OPENAI_BASE_URL%/}"
OPENAI_MODEL="$DEFAULT_MODEL"

info "尝试根据你填写的 API 参数拉取模型列表 ..."
MODEL_FETCH_OUTPUT="$(DEPLOY_OPENAI_API_KEY="$OPENAI_API_KEY" DEPLOY_OPENAI_BASEURL="$OPENAI_BASE_URL" python3 - <<'PY'
import json, os, urllib.request
api_key = os.environ.get('DEPLOY_OPENAI_API_KEY', '').strip()
base_url = os.environ.get('DEPLOY_OPENAI_BASEURL', '').strip().rstrip('/')
if not api_key or not base_url:
    print(json.dumps({"ok": False, "error": "missing api_key or base_url"}))
    raise SystemExit(0)
url = base_url + '/models'
req = urllib.request.Request(url, headers={
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json',
    'User-Agent': 'essay-agent-deploy/1.0',
})
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode('utf-8', errors='ignore'))
    models = []
    for item in data.get('data', []):
        mid = item.get('id')
        if isinstance(mid, str) and mid.strip():
            models.append(mid.strip())
    print(json.dumps({"ok": True, "models": models[:50]}))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
PY
)"

if [[ -n "$MODEL_FETCH_OUTPUT" ]]; then
    MODEL_STATUS="$(MODEL_FETCH_OUTPUT_RAW="$MODEL_FETCH_OUTPUT" python3 - <<'PY'
import json, os
raw = os.environ.get('MODEL_FETCH_OUTPUT_RAW', '')
try:
    data = json.loads(raw)
except Exception:
    data = {"ok": False, "error": "invalid json"}
print('OK' if data.get('ok') and data.get('models') else 'FAIL')
PY
)"
    if [[ "$MODEL_STATUS" == "OK" ]]; then
        echo ""
        echo "  检测到以下模型（前 15 个）："
        MODEL_LINES="$(MODEL_FETCH_OUTPUT_RAW="$MODEL_FETCH_OUTPUT" python3 - <<'PY'
import json, os
raw = os.environ.get('MODEL_FETCH_OUTPUT_RAW', '')
data = json.loads(raw)
for i, m in enumerate(data['models'][:15], start=1):
    print(f'{i}. {m}')
PY
)"
        echo "$MODEL_LINES"
        FIRST_MODEL="$(MODEL_FETCH_OUTPUT_RAW="$MODEL_FETCH_OUTPUT" python3 - <<'PY'
import json, os
raw = os.environ.get('MODEL_FETCH_OUTPUT_RAW', '')
data = json.loads(raw)
print(data['models'][0])
PY
)"
        ask "模型名称（可直接粘贴，也可回车使用默认/首个模型）" "$FIRST_MODEL" OPENAI_MODEL
    else
        MODEL_ERROR="$(MODEL_FETCH_OUTPUT_RAW="$MODEL_FETCH_OUTPUT" python3 - <<'PY'
import json, os
raw = os.environ.get('MODEL_FETCH_OUTPUT_RAW', '')
try:
    data = json.loads(raw)
    print(data.get('error', 'unknown error'))
except Exception:
    print('unknown error')
PY
)"
        warn "自动获取模型列表失败：$MODEL_ERROR"
        ask "模型名称" "$DEFAULT_MODEL" OPENAI_MODEL
    fi
else
    warn "模型列表获取结果为空，改为手动输入模型名称。"
    ask "模型名称" "$DEFAULT_MODEL" OPENAI_MODEL
fi

echo ""
echo "  邮件推送是可选的；如果现在不配，后面也可以手动修改 .env。"
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
fi

echo ""
echo "  以下参数控制抓取范围和过滤强度。"
echo "  首次部署建议先用默认值，确认跑通后再放大。"
echo ""
ask "抓取最近几天论文（DAYS_BACK）" "1" DAYS_BACK
ask "每个 query 每个源最大抓取数（MAX_RESULTS_PER_QUERY）" "10" MAX_RESULTS_PER_QUERY
ask "最低相关性阈值 0-100（MIN_RELEVANCE_SCORE）" "60" MIN_RELEVANCE_SCORE
ask "Markdown 报告展示前 N 条（REPORT_TOP_N）" "10" REPORT_TOP_N
ask "邮件正文展示前 N 条（EMAIL_TOP_N）" "5" EMAIL_TOP_N
ask "待展示池窗口天数（PENDING_POOL_DAYS）" "7" PENDING_POOL_DAYS

CORE_API_KEY=""
if confirm "是否配置 CORE API Key？" "n"; then
    ask "CORE API Key" "" CORE_API_KEY
fi

ask "每天自动运行时间（24 小时制，如 07:00）" "07:00" RUN_TIME

step "4/5 安装应用"
echo ""
echo -e "${BOLD}部署配置确认：${NC}"
echo "  安装目录：$INSTALL_DIR"
echo "  仓库：$REPO_HTTPS_URL"
echo "  分支：$DEFAULT_BRANCH"
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

if ! id "$SERVICE_USER" &>/dev/null; then
    info "创建服务用户 $SERVICE_USER ..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

info "部署应用到 $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 ! -name '.env' -exec rm -rf {} +
cp -a "$TMP_SRC"/. "$INSTALL_DIR"/

info "创建 Python 虚拟环境 ..."
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
    python3 -m venv "$INSTALL_DIR/.venv"
fi
info "安装 Python 依赖 ..."
"$INSTALL_DIR/.venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"

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
PENDING_POOL_DAYS=$PENDING_POOL_DAYS
EMPTY_REPORT_EMAIL=true
ENVEOF

mkdir -p "$INSTALL_DIR/output"
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"
chmod 600 "$ENV_FILE"
chmod 644 "$INSTALL_DIR/config.yaml" "$INSTALL_DIR/arxiv_agent.py" "$INSTALL_DIR/requirements.txt" "$INSTALL_DIR/README.md" "$INSTALL_DIR/README.zh-CN.md" 2>/dev/null || true
chmod 755 "$INSTALL_DIR" "$INSTALL_DIR/output" 2>/dev/null || true

info "安装 systemd 服务 ..."
cp "$INSTALL_DIR/deploy/arxiv-agent.service" /etc/systemd/system/
cp "$INSTALL_DIR/deploy/arxiv-agent.timer" /etc/systemd/system/

if ! grep -q '^User=' /etc/systemd/system/arxiv-agent.service; then
    sed -i "/^\[Service\]/a User=$SERVICE_USER" /etc/systemd/system/arxiv-agent.service
fi
sed -i "s|OnCalendar=.*|OnCalendar=*-*-* ${RUN_TIME}:00|" /etc/systemd/system/arxiv-agent.timer

systemctl daemon-reload
systemctl enable arxiv-agent.timer >/dev/null
systemctl restart arxiv-agent.timer

step "5/5 验证与试运行"
TIMER_STATUS="$(systemctl is-active arxiv-agent.timer 2>/dev/null || true)"
if [[ "$TIMER_STATUS" == "active" ]]; then
    info "定时器已激活"
else
    warn "定时器状态异常：$TIMER_STATUS"
fi

echo ""
if confirm "部署完成！是否立即试运行一次？（约 2-5 分钟）" "y"; then
    info "开始试运行 ..."
    if sudo -u "$SERVICE_USER" test -r "$INSTALL_DIR/config.yaml"; then
        info "配置文件可读性检查通过"
    else
        warn "配置文件当前对服务用户不可读：$INSTALL_DIR/config.yaml"
    fi
    if sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && '$INSTALL_DIR/.venv/bin/python' arxiv_agent.py"; then
        info "试运行成功！"
        echo ""
        echo "  输出文件："
        ls -la "$INSTALL_DIR/output/" 2>/dev/null || true
    else
        warn "试运行出错，请检查日志：journalctl -u arxiv-agent -n 200 --no-pager"
    fi
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
echo "    修改检索：  sudo nano $INSTALL_DIR/config.yaml"
echo "    定时器状态：systemctl status arxiv-agent.timer"
echo "    上次运行：  systemctl status arxiv-agent.service"
echo ""
