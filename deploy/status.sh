#!/usr/bin/env bash
# 查看当前运行状态与公网地址
set -uo pipefail
cd "$(dirname "$0")/.."

echo "--- 服务状态 ---"
./deploy/mysql_local.sh status 2>&1 || true
if lsof -ti:8001 >/dev/null 2>&1; then
    echo "gunicorn：运行中（127.0.0.1:8001）"
else
    echo "gunicorn：未运行"
fi
if pgrep -f "cloudflared tunnel --url http://127.0.0.1:8001" >/dev/null 2>&1; then
    echo "隧道：运行中"
    [ -f logs/current_url.txt ] && echo "公网地址：$(cat logs/current_url.txt)"
else
    echo "隧道：未运行"
fi
