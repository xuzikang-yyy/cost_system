# 采购成本核价系统 · 部署说明

## 1. 本机生产模式（gunicorn + WhiteNoise + MySQL）

```bash
# 一键启动（MySQL -> gunicorn -> 隧道）
./deploy/start_all.sh

# 一键停止
./deploy/stop_all.sh
```

也可以分步启动：

```bash
./deploy/mysql_local.sh start   # 本地 MySQL，127.0.0.1:3307
./deploy/run_prod.sh            # gunicorn，127.0.0.1:8001
./deploy/start_tunnel.sh        # 公网 HTTPS 隧道
```

- 监听：`127.0.0.1:8001`
- 关键环境变量见 `deploy/env.production`
- `DJANGO_DEBUG=0`、`DJANGO_SECRET_KEY` 必须显式提供，否则启动即报错
- 静态文件由 WhiteNoise 托管，`collectstatic` 由脚本自动执行
- 重启 Mac 后需要重新执行 `./deploy/start_all.sh`（快速隧道地址会变化）

## 2. 公网临时访问（Cloudflare 快速隧道）

```bash
./deploy/start_tunnel.sh
```

终端会输出形如 `https://xxxx-xxxx.trycloudflare.com` 的地址，
任何电脑用浏览器打开即可，TLS 由 Cloudflare 提供（浏览器信任）。

注意：
- 快速隧道的域名**每次重启都会变化**，且无 SLA，只适合演示；
- 地址公开可访问，当前账号仍是演示密码，务必尽快修改；
- 本机关机 / 睡眠 / 断网，地址立即失效；
- 如需固定地址，需要 Cloudflare 账号 + 自有域名（命名隧道），或改用公网服务器。

## 3. Linux 服务器（Nginx + HTTPS）

```bash
# 服务器上
sudo mkdir -p /opt/cost_system && sudo chown $USER /opt/cost_system
# 上传项目文件后
cd /opt/cost_system
python3 -m pip install --target .vendor -r requirements.txt
cp deploy/env.production.example deploy/env.production
# 编辑 env.production：域名、密钥、数据库路径
./deploy/run_prod.sh
```

- `deploy/cost-system.service` → `/etc/systemd/system/`，`systemctl enable --now cost-system`
- `deploy/nginx-cost-system.conf` → `/etc/nginx/conf.d/`，改域名后 `nginx -t && systemctl reload nginx`
- 证书：`sudo certbot --nginx -d cost.example.com`

## 4. 修改账号密码

```bash
PYTHONPATH=.vendor python3 manage.py changepassword admin
PYTHONPATH=.vendor python3 manage.py changepassword buyer
```

生产环境建议：删除或停用演示账号，至少修改 `admin123` / `buyer123`。

## 5. 数据备份

SQLite 单文件，直接备份 `db.sqlite3`：

```bash
cp db.sqlite3 "backup/db-$(date +%F-%H%M).sqlite3"
```

## 6. MySQL

当前本机使用**当前用户的独立 MySQL 实例**（系统自带的 8.0.30，因无免密 sudo 无法直接接管系统实例）：

- 数据目录：`~/mysql-cost-system/data`
- 地址：`127.0.0.1:3307`，仅监听回环地址
- 数据库：`cost_verification`，账号：`cost`
- 密码：`~/mysql-cost-system/cost_db_password.txt`（同时写入 `deploy/env.production`）
- 管理脚本：[deploy/mysql_local.sh](mysql_local.sh)（`start|stop|status`）
- 配置文件：`~/mysql-cost-system/my.cnf`

Django 固定为 **5.2 LTS**：Django 6.x 要求 MySQL 8.4+，而本机是 8.0.30。

### 备份与恢复

```bash
mysqldump -h127.0.0.1 -P3307 -ucost -p cost_verification > backup/cost-$(date +%F).sql
mysql -h127.0.0.1 -P3307 -ucost -p cost_verification < backup/cost-YYYY-MM-DD.sql
```

### 迁移到其他 MySQL（如云数据库）

修改 `deploy/env.production` 中的 `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD`，
然后执行：

```bash
./deploy/mysql_local.sh stop   # 如不再使用本地实例
./deploy/run_prod.sh
```

已有数据可用 `python3 manage.py dumpdata pricing auth.user -o data.json` 导出，
在新库 `migrate` 后 `loaddata data.json` 导入。
