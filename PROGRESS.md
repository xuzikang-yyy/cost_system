# 采购成本核价系统 · 工作进度快照

> 快照时间：2026-10-21 17:26（Asia/Shanghai）
> 项目路径：`/Users/Zhuanz/Downloads/cost_system`
> 当前阶段：生产模式运行中，公网可访问

---

## 一、当前运行状态

| 项目 | 状态 |
|---|---|
| 公网地址 | https://organ-enhancement-restored-mail.trycloudflare.com |
| MySQL | 运行中，`127.0.0.1:3307`，数据库 `cost_verification` |
| gunicorn | 运行中，`127.0.0.1:8001`，3 worker × 2 threads |
| Cloudflare 隧道 | 运行中（快速隧道，地址临时） |
| 访问方式 | 浏览器打开公网地址，账号登录 |

> 快速隧道地址每次重启都会变化，最新地址见 `logs/current_url.txt`。

## 二、技术栈

- Python 3.14.8 / Django **5.2.18 LTS**（固定 5.2，因 Django 6.x 要求 MySQL 8.4+）
- MySQL 8.0.30（当前用户独立实例，非系统 launchd 服务）
- gunicorn 26.2.0 + WhiteNoise（静态文件）
- Bootstrap 5 + ECharts（前端）
- openpyxl（Excel 导出）

## 三、已完成的改造（2026-10-21）

### 1. 生产化运行
- 关闭 DEBUG（`DJANGO_DEBUG=0`），错误页不再暴露堆栈
- 随机 `SECRET_KEY`，通过 `deploy/env.production` 注入
- 安全 Cookie、`X-Frame-Options: DENY`、`nosniff`、`Referrer-Policy`
- WhiteNoise 托管静态文件，无需 Nginx
- gunicorn 只监听回环地址，公网入口由 Cloudflare 隧道终止 TLS

### 2. SQLite → MySQL
- 本地 MySQL 独立实例：`~/mysql-cost-system`，端口 3307，仅回环
- 数据库 `cost_verification`，账号 `cost`（密码见 `~/mysql-cost-system/cost_db_password.txt`）
- 原 SQLite 数据 211 条已全量导入：3 用户、4 材料、52 价格、7 零件、4 规则、8 供应商、20 报价、16 核价单、96 明细
- SQLite 备份：`backup/db-20261021-162141.sqlite3`

### 3. 登录 IP 审计
- 新增 `LoginAudit` 模型（迁移 `pricing/0002_loginaudit.py`）
- 记录登录成功 / 失败 / 退出，含账号、真实客户端 IP、User-Agent、时间
- IP 解析优先级：`CF-Connecting-IP` → `X-Forwarded-For` → `REMOTE_ADDR`
- 管理页：左侧「系统 → 登录审计」（`/system/audit/`，仅管理员）
- 实测公网登录可正确记录真实 IP

### 4. 登录页
- 删除页面上展示的演示账号与密码
- 生产模式模板有缓存，修改后需重启 gunicorn

### 5. 部署脚本
- `deploy/start_all.sh`：MySQL → gunicorn → 隧道，幂等、失败时打印日志
- `deploy/stop_all.sh`：按 PID + 进程特征兜底停止
- `deploy/status.sh`：查看三个服务状态与当前公网地址
- `deploy/mysql_local.sh`：MySQL 启停/状态，自动清理重启后的残留 socket/pid
- `deploy/run_prod.sh`：加载环境变量、迁移、collectstatic、启动 gunicorn
- `deploy/start_tunnel.sh`：下载并启动 cloudflared
- `deploy/backup.sh`：一键备份 MySQL + SQLite 到 `backup/`
- `deploy/nginx-cost-system.conf`、`deploy/cost-system.service`：服务器部署参考

## 四、关键文件

| 文件 | 说明 |
|---|---|
| `config/settings.py` | 环境变量驱动、安全设置、WhiteNoise、审计中间件 |
| `pricing/models.py` | 8 张业务表 + `LoginAudit` + `SystemSetting` |
| `pricing/services.py` | 成本计算、报价统一口径、偏差判定 |
| `pricing/audit.py` | 登录审计中间件与信号 |
| `pricing/views.py` | 全部业务视图（含审计列表） |
| `pricing/exports.py` | Excel 导出 |
| `templates/system/audit_log.html` | 登录审计页面 |
| `deploy/env.production` | 生产环境变量（含密钥，**不入库、不外发**） |
| `deploy/README.md` | 部署与运维说明 |

## 五、数据库快照

本次已备份：

- MySQL：`backup/mysql-cost_verification-20261021-172629.sql`（59 KB，20 张表）
- SQLite：`backup/db-20261021-172629.sqlite3`（248 KB）

恢复 MySQL：

```bash
mysql -h127.0.0.1 -P3307 -ucost -p cost_verification < backup/mysql-cost_verification-20261021-172629.sql
```

当前数据量：3 用户、4 材料、52 价格、7 零件、4 规则、8 供应商、20 报价、17 核价单、102 明细、10 条登录审计。

## 六、常用命令

```bash
./deploy/start_all.sh   # 启动（Mac 重启后也用这个）
./deploy/status.sh      # 查看状态与公网地址
./deploy/stop_all.sh    # 停止全部服务
```

手动启动（分步）：

```bash
./deploy/mysql_local.sh start
./deploy/run_prod.sh
./deploy/start_tunnel.sh
```

## 七、已知问题 / 待办

1. **密码仍是演示密码**：`admin/admin123`、`buyer/buyer123`、`buyer2/buyer123`，公网可访问下风险较高，建议尽快改随机强密码。
2. **隧道地址临时**：快速隧道无 SLA、每次重启换域名；长期使用需命名隧道 + 自有域名，或部署到云服务器。
3. **未配置开机自启**：Mac 重启后需手动执行 `start_all.sh`（可加 launchd）。
4. **Excel 导出元信息错位**：`pricing/exports.py` 的 `build_calc_workbook` 第 46–62 行，标签/值合并导致列错位（历史问题，未修）。
5. **N+1 查询**：`dashboard_stats`、`supplier_performance`、`analysis` 逐条查核价单，数据量大时变慢。
6. **系统设置部分字段未接线**：`usd_rate`、`default_deviation_*` 只存不用；`ensure_roles()` 未调用。
7. **SQLite 回退**：`db.sqlite3` 保留作演示备份，生产已使用 MySQL；已加入 `.gitignore`。

## 八、变更记录

| 时间 | 内容 |
|---|---|
| 10-21 15:52 | 阅读项目，确认 Django 单体结构与业务模型 |
| 10-21 16:12 | 安装依赖，开发服务器跑通 |
| 10-21 16:16 | 生产化：gunicorn + WhiteNoise + 环境变量 + Cloudflare 隧道 |
| 10-21 16:21 | 切换 MySQL，迁移全部数据，Django 固定 5.2 LTS |
| 10-21 16:22 | 补齐启动/停止/状态脚本与部署文档 |
| 10-21 16:49 | 删除登录页演示账号展示 |
| 10-21 17:00 | 新增登录 IP 审计（模型/中间件/页面） |
| 10-21 17:26 | 数据库备份 + 进度快照 + Git 初始化提交 |
