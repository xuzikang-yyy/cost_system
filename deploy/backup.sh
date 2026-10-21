#!/usr/bin/env bash
# 备份当前数据库：MySQL 全量 dump + SQLite 副本
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE="${ENV_FILE:-deploy/env.production}"
[ -f "$ENV_FILE" ] || { echo "缺少 $ENV_FILE" >&2; exit 1; }
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p backup

if [ "${DB_ENGINE:-}" = "mysql" ]; then
    MYSQL_PWD="$DB_PASSWORD" /usr/local/mysql/bin/mysqldump \
        -h"${DB_HOST:-127.0.0.1}" -P"${DB_PORT:-3306}" -u"${DB_USER:-root}" \
        --single-transaction --no-tablespaces --routines --triggers \
        --default-character-set=utf8mb4 "${DB_NAME}" \
        > "backup/mysql-${DB_NAME}-$STAMP.sql"
    echo "MySQL 备份：backup/mysql-${DB_NAME}-$STAMP.sql"
fi

if [ -f db.sqlite3 ]; then
    cp db.sqlite3 "backup/db-$STAMP.sqlite3"
    echo "SQLite 备份：backup/db-$STAMP.sqlite3"
fi

ls -lh backup | tail -3
