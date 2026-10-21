#!/usr/bin/env bash
# 启动 Cloudflare 快速隧道：为本地 8001 端口生成一个公网 HTTPS 地址
set -euo pipefail
cd "$(dirname "$0")/.."

BIN="deploy/bin/cloudflared"
TARGET="${TUNNEL_TARGET:-http://127.0.0.1:8001}"

if [ ! -x "$BIN" ]; then
    case "$(uname -m)" in
        arm64|aarch64) ASSET="cloudflared-darwin-arm64.tgz" ;;
        x86_64)        ASSET="cloudflared-darwin-amd64.tgz" ;;
        *) echo "不支持的架构：$(uname -m)" >&2; exit 1 ;;
    esac
    mkdir -p deploy/bin
    echo "下载 cloudflared（$ASSET）..."
    curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/$ASSET" \
        -o /tmp/cloudflared.tgz
    tar -xzf /tmp/cloudflared.tgz -C deploy/bin
    chmod +x "$BIN"
fi

exec "$BIN" tunnel --url "$TARGET" --no-autoupdate
