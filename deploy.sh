#!/usr/bin/env bash
# Install once; subsequent invocations use the transactional updater.
set -euo pipefail
INSTALL_DIR="/opt/essay-agent"
if [[ $EUID -ne 0 ]]; then echo "请使用 sudo bash deploy.sh" >&2; exit 1; fi
if [[ ! -r /dev/tty ]]; then echo "需要交互终端 /dev/tty" >&2; exit 1; fi
read -r -p "安装 / 升级 essay-agent（保留现有配置与数据）？[Y/n]: " answer < /dev/tty
case "$answer" in n|N|no|NO) exit 0 ;; esac
apt-get update -qq
apt-get install -y -qq python3 python3-venv git ca-certificates curl nano util-linux
TMP_SRC="$(mktemp -d /tmp/essay-agent-src.XXXXXX)"
trap 'rm -rf "$TMP_SRC"' EXIT
git clone --depth=30 --branch main https://github.com/wannaqueen66-create/essay-agent.git "$TMP_SRC"
for file in essay_agent.py config.yaml requirements.txt esag esag_console.py agent_config.py agent_update.py; do
  test -f "$TMP_SRC/$file" || { echo "下载内容不完整" >&2; exit 1; }
done
if [[ -x "$INSTALL_DIR/.venv/bin/python" && -f "$INSTALL_DIR/essay_agent.py" ]]; then
  # Run downloaded updater from staging, never overwrite old files to bootstrap it.
  cd "$TMP_SRC"
  "$INSTALL_DIR/.venv/bin/python" - "$INSTALL_DIR" "$TMP_SRC" <<'PY'
import hashlib, sys
from pathlib import Path
from agent_config import operation_lock
from agent_update import install_update, run, tracked
root, source = map(Path, sys.argv[1:])
files = tracked(source)
sha = run(['git', 'rev-parse', 'HEAD'], source, True).stdout.strip()
info = {'source': source, 'sha': sha, 'files': files,
        'hashes': {n: hashlib.sha256((source / n).read_bytes()).hexdigest() for n in files}}
with operation_lock(root, 'console'):
    install_update(root, info, 'all')
PY
  cd "$INSTALL_DIR"
  exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/esag_console.py" < /dev/tty
fi
# A partial installation must never be mistaken for disposable data.
if [[ -d "$INSTALL_DIR" ]] && [[ -n "$(ls -A "$INSTALL_DIR")" ]]; then
  echo "检测到不完整安装，已保留全部文件。请检查 .venv，修复后再运行部署脚本。" >&2
  exit 1
fi
id essay-agent >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin essay-agent
mkdir -p "$INSTALL_DIR"
cp -a "$TMP_SRC"/. "$INSTALL_DIR"/
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install -r "$INSTALL_DIR/requirements.txt"
"$INSTALL_DIR/.venv/bin/python" -m pip check
cd "$INSTALL_DIR"
"$INSTALL_DIR/.venv/bin/python" - <<'PY'
from pathlib import Path
from agent_config import write_env
write_env(Path('.env'), {'DAYS_BACK': 1, 'MAX_RESULTS_PER_QUERY': 10,
          'MIN_RELEVANCE_SCORE': 60, 'REPORT_TOP_N': 10, 'EMAIL_TOP_N': 5,
          'PENDING_POOL_DAYS': 7, 'EMAIL_ENABLED': 'false', 'EMPTY_REPORT_EMAIL': 'false',
          'FORCE_REFRESH': 'false', 'OUTPUT_RETENTION_DAYS': 30})
PY
mkdir -p output
chown -R essay-agent:essay-agent "$INSTALL_DIR"
chmod 600 .env
# Install entry now: a cancelled API wizard can be resumed with sudo esag.
install -m 755 esag /usr/local/bin/esag
install -m 644 deploy/essay-agent.service /etc/systemd/system/essay-agent.service
install -m 644 deploy/essay-agent.timer /etc/systemd/system/essay-agent.timer
systemctl daemon-reload
if "$INSTALL_DIR/.venv/bin/python" esag_console.py --configure < /dev/tty; then
  systemctl enable --now essay-agent.timer
  echo "安装成功，默认每天 07:00（服务器时区）运行；可在抓取与报告设置中修改。"
else
  echo "AI 配置尚未完成，定时器未启用。用 sudo esag 完成配置后，在抓取设置中启用定时任务。"
fi
exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/esag_console.py" < /dev/tty
