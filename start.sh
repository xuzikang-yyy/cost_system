#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if ! PYTHONPATH=.vendor python3 -c "import django" >/dev/null 2>&1; then
    python3 -m pip install --quiet --target .vendor -r requirements.txt
fi

export PYTHONPATH="$PWD/.vendor${PYTHONPATH:+:$PYTHONPATH}"
exec python3 manage.py runserver 0.0.0.0:8000 --noreload
