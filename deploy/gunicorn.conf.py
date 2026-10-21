"""gunicorn 生产配置：仅监听回环地址，由隧道或 Nginx 转发。"""

bind = "127.0.0.1:8001"
workers = 3
threads = 2
worker_class = "gthread"
timeout = 60
graceful_timeout = 30
keepalive = 5

# 访问日志与错误日志交给 systemd / nohup 收集
accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True

# 只信任本机反向代理写入的 X-Forwarded-* 头
forwarded_allow_ips = "127.0.0.1"
proxy_allow_ips = "127.0.0.1"
