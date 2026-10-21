#!/usr/bin/env bash
# 以生产模式启动：加载环境变量 -> 迁移 -> 收集静态文件 -> gunicorn
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .vendor ]; then
    python3 -m pip install --quiet --target .vendor -r requirements.txt
fi

export PYTHONPATH="$PWD/.vendor${PYTHONPATH:+:$PYTHONPATH}"

ENV_FILE="${ENV_FILE:-deploy/env.production}"
if [ ! -f "$ENV_FILE" ]; then
    echo "缺少环境变量文件：$ENV_FILE（可从 deploy/env.production.example 复制）" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

mkdir -p logs

python3 manage.py migrate --noinput
python3 manage.py collectstatic --noinput >/dev/null

echo "启动 gunicorn：http://127.0.0.1:8001（DEBUG=$DJANGO_DEBUG）"
exec python3 -m gunicorn config.wsgi:application -c deploy/gunicorn.conf.py
