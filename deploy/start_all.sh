#!/usr/bin/env bash
# 一键启动：MySQL -> gunicorn -> Cloudflare 隧道
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p logs
TARGET="http://127.0.0.1:8001"

echo "[1/3] MySQL"
./deploy/mysql_local.sh start

echo "[2/3] gunicorn"
if lsof -ti:8001 >/dev/null 2>&1; then
    echo "8001 已在监听，跳过启动"
else
    [ -f logs/gunicorn.log ] && cp logs/gunicorn.log "logs/gunicorn-$(date +%Y%m%d-%H%M%S).log"
    nohup ./deploy/run_prod.sh > logs/gunicorn.log 2>&1 &
    echo $! > logs/gunicorn.pid
    ready=0
    for _ in $(seq 1 40); do
        if curl -s -o /dev/null --max-time 2 http://127.0.0.1:8001/login/; then
            echo "gunicorn 已启动（PID $(cat logs/gunicorn.pid)）"
            ready=1
            break
        fi
        sleep 1
    done
    if [ "$ready" -eq 0 ]; then
        echo "gunicorn 启动失败，最近日志：" >&2
        tail -20 logs/gunicorn.log >&2
        exit 1
    fi
fi

echo "[3/3] Cloudflare 隧道"
if pgrep -f "cloudflared tunnel --url $TARGET" >/dev/null 2>&1; then
    URL=$(cat logs/current_url.txt 2>/dev/null || grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' logs/cloudflared.log 2>/dev/null | head -1 || true)
    echo "隧道已在运行"
    [ -n "$URL" ] && echo "公网地址：$URL"
else
    [ -f logs/cloudflared.log ] && cp logs/cloudflared.log "logs/cloudflared-$(date +%Y%m%d-%H%M%S).log"
    : > logs/cloudflared.log
    nohup ./deploy/start_tunnel.sh > logs/cloudflared.log 2>&1 &
    echo $! > logs/cloudflared.pid
    URL=""
    for _ in $(seq 1 45); do
        URL=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' logs/cloudflared.log | head -1 || true)
        [ -n "$URL" ] && break
        sleep 1
    done
    if [ -n "$URL" ]; then
        echo "$URL" > logs/current_url.txt
        echo "公网地址：$URL"
    else
        echo "隧道地址未生成，最近日志：" >&2
        tail -20 logs/cloudflared.log >&2
        exit 1
    fi
fi

echo "启动完成。日志目录：logs/"
