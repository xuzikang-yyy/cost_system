"""登录审计：解析真实客户端 IP，并通过认证信号记录登录/退出事件。

部署在 Cloudflare 隧道或 Nginx 之后时，真实客户端 IP 位于
CF-Connecting-IP / X-Forwarded-For 头中；直接访问则退回 REMOTE_ADDR。
"""

import threading

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed

from .models import LoginAudit

_local = threading.local()


def get_client_ip(request):
    """按可信度解析客户端 IP。"""
    if request is None:
        return ""
    meta = request.META
    # Cloudflare 写入，客户端无法伪造，优先级最高
    cf = (meta.get("HTTP_CF_CONNECTING_IP") or "").strip()
    if cf:
        return cf.split(",")[0].strip()
    xff = (meta.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return meta.get("REMOTE_ADDR", "")


class AuditMiddleware:
    """把当前请求的 IP 与 User-Agent 存到线程局部变量，供信号处理器读取。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.ip = get_client_ip(request)
        _local.user_agent = request.META.get("HTTP_USER_AGENT", "")
        return self.get_response(request)


def _record(event, *, username="", user=None, request=None):
    LoginAudit.objects.create(
        username=username,
        user=user,
        event=event,
        ip=getattr(_local, "ip", "") or get_client_ip(request),
        user_agent=getattr(_local, "user_agent", "")
        or (request.META.get("HTTP_USER_AGENT", "") if request else ""),
    )


def _on_login(sender, user, request, **kwargs):
    _record("login", username=user.get_username(), user=user, request=request)


def _on_login_failed(sender, credentials, request, **kwargs):
    username = (credentials or {}).get("username", "")
    _record("failed", username=username or "", request=request)


def _on_logout(sender, user, request, **kwargs):
    # 匿名访问退出接口时 user 为 None
    username = user.get_username() if user is not None else ""
    _record("logout", username=username, user=user, request=request)


def connect_signals():
    user_logged_in.connect(_on_login, dispatch_uid="audit.login")
    user_login_failed.connect(_on_login_failed, dispatch_uid="audit.login_failed")
    user_logged_out.connect(_on_logout, dispatch_uid="audit.logout")
