#!/usr/bin/env bash
# 本地 MySQL 实例管理（当前用户，端口 3307，仅监听回环地址）
set -euo pipefail

BASE="${MYSQL_BASE:-/usr/local/mysql}"
ROOT="${MYSQL_ROOT:-$HOME/mysql-cost-system}"
SOCK="$ROOT/mysql.sock"
ACTION="${1:-start}"

case "$ACTION" in
    start)
        mkdir -p "$ROOT"
        if [ -S "$SOCK" ] && "$BASE/bin/mysqladmin" --socket="$SOCK" -uroot ping >/dev/null 2>&1; then
            echo "MySQL 已在运行：$SOCK"
            exit 0
        fi
        # 重启/异常退出后可能残留 socket 或 pid 文件，确认实例无响应后清理
        rm -f "$SOCK" "$ROOT/mysqld.pid"
        if [ ! -d "$ROOT/data/mysql" ]; then
            echo "数据目录未初始化，正在初始化..."
            mkdir -p "$ROOT/data"
            "$BASE/bin/mysqld" --initialize-insecure --basedir="$BASE" \
                --datadir="$ROOT/data" --log-error="$ROOT/init.err"
        fi
        "$BASE/bin/mysqld" --defaults-file="$ROOT/my.cnf" --daemonize
        for _ in $(seq 1 30); do
            if "$BASE/bin/mysqladmin" --socket="$SOCK" -uroot ping >/dev/null 2>&1; then
                echo "MySQL 已启动：127.0.0.1:3307"
                exit 0
            fi
            sleep 1
        done
        echo "MySQL 启动失败，查看 $ROOT/mysqld.err" >&2
        exit 1
        ;;
    stop)
        "$BASE/bin/mysqladmin" --socket="$SOCK" -uroot shutdown
        echo "MySQL 已停止"
        ;;
    status)
        if "$BASE/bin/mysqladmin" --socket="$SOCK" -uroot ping >/dev/null 2>&1; then
            echo "MySQL 运行中：127.0.0.1:3307"
        else
            echo "MySQL 未运行"
            exit 1
        fi
        ;;
    *)
        echo "用法：$0 {start|stop|status}" >&2
        exit 2
        ;;
esac
