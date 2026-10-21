#!/usr/bin/env bash
# 停止隧道、gunicorn 与本地 MySQL
set -uo pipefail
cd "$(dirname "$0")/.."

for name in cloudflared gunicorn; do
    pidfile="logs/$name.pid"
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && echo "$name 已停止（PID $pid）"
        fi
        rm -f "$pidfile"
    fi
done

# 兜底：按进程特征清理，避免 PID 文件丢失或过期
pgrep -f "cloudflared tunnel --url http://127.0.0.1:8001" 2>/dev/null | xargs -r kill 2>/dev/null || true
pgrep -f "gunicorn config.wsgi:application" 2>/dev/null | xargs -r kill 2>/dev/null || true
lsof -ti:8001 2>/dev/null | xargs -r kill 2>/dev/null || true

./deploy/mysql_local.sh stop || true
rm -f logs/current_url.txt
echo "全部停止"
