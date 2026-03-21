#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# essay-agent 一键部署脚本
# 适用于 Ubuntu/Debian 系 VPS（1C1G 及以上）
# 用法：sudo bash deploy.sh
# ============================================================

INSTALL_DIR="/opt/arxiv-agent"
SERVICE_USER="arxiv-agent"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# --- 检查 root 权限 ---
if [[ $EUID -ne 0 ]]; then
    error "请使用 sudo 运行此脚本：sudo bash deploy.sh"
fi

info "开始部署 arxiv-agent ..."

# --- 1. 安装系统依赖 ---
info "安装系统依赖 ..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git > /dev/null

# --- 2. 创建服务用户（如不存在） ---
if ! id "$SERVICE_USER" &>/dev/null; then
    info "创建服务用户 $SERVICE_USER ..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# --- 3. 部署应用文件 ---
info "部署应用到 $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
rsync -a --exclude='.git' --exclude='.venv' --exclude='papers.db' --exclude='output' \
    "$REPO_DIR/" "$INSTALL_DIR/"

# --- 4. 创建虚拟环境并安装依赖 ---
info "创建 Python 虚拟环境 ..."
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
    python3 -m venv "$INSTALL_DIR/.venv"
fi
info "安装 Python 依赖 ..."
"$INSTALL_DIR/.venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"

# --- 5. 配置 .env ---
if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    warn ".env 文件已从模板创建，请编辑 $INSTALL_DIR/.env 填入 API key 等配置"
else
    info ".env 文件已存在，跳过覆盖"
fi

# --- 6. 创建输出目录 ---
mkdir -p "$INSTALL_DIR/output"

# --- 7. 设置文件权限 ---
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.env"

# --- 8. 安装 systemd 服务 ---
info "安装 systemd 服务和定时器 ..."
cp "$INSTALL_DIR/deploy/arxiv-agent.service" /etc/systemd/system/
cp "$INSTALL_DIR/deploy/arxiv-agent.timer" /etc/systemd/system/

# 补充 User 字段到 service
if ! grep -q "^User=" /etc/systemd/system/arxiv-agent.service; then
    sed -i "/^\[Service\]/a User=$SERVICE_USER" /etc/systemd/system/arxiv-agent.service
fi

systemctl daemon-reload
systemctl enable arxiv-agent.timer
systemctl start arxiv-agent.timer

# --- 9. 验证 ---
info "验证部署 ..."
TIMER_STATUS=$(systemctl is-active arxiv-agent.timer 2>/dev/null || true)
if [[ "$TIMER_STATUS" == "active" ]]; then
    info "定时器已激活"
else
    warn "定时器状态异常：$TIMER_STATUS"
fi

echo ""
info "=========================================="
info "  部署完成！"
info "=========================================="
echo ""
echo "  安装目录：$INSTALL_DIR"
echo "  配置文件：$INSTALL_DIR/.env"
echo "  定时任务：每天 07:00 自动运行"
echo ""
echo "  常用命令："
echo "    手动运行：  sudo -u $SERVICE_USER $INSTALL_DIR/.venv/bin/python $INSTALL_DIR/arxiv_agent.py"
echo "    查看日志：  journalctl -u arxiv-agent -f"
echo "    定时器状态：systemctl status arxiv-agent.timer"
echo "    上次运行：  systemctl status arxiv-agent.service"
echo ""
if [[ ! -s "$INSTALL_DIR/.env" ]] || grep -q "your_openai_api_key_here" "$INSTALL_DIR/.env" 2>/dev/null; then
    warn "请先编辑 $INSTALL_DIR/.env 配置 API key 等参数！"
fi
