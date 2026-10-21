"""Django settings for the procurement cost verification system."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_list(name, default=""):
    """读取逗号分隔的环境变量，用于域名、Origin 列表等。"""
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG:
        # 仅限本地开发；生产环境必须通过 DJANGO_SECRET_KEY 注入随机密钥
        SECRET_KEY = "django-insecure-xb-w191w-ih()au$bouzu-rb*tlzi47$8_51&i6g#!+#!qu((7"
    else:
        raise ImproperlyConfigured("生产模式必须设置环境变量 DJANGO_SECRET_KEY")

# 生产环境建议显式填写域名；使用隧道时可用 * 并配合 CSRF_TRUSTED_ORIGINS
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "*") or ["*"]

# 反向代理 / 隧道域名，例如 https://abc.trycloudflare.com
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "pricing",
]

MIDDLEWARE = [
    "config.middleware.PreviewCookieMiddleware",
    "pricing.audit.AuditMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# 预览代理终止 TLS 后通过该请求头告知 Django 原始协议
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "pricing.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# 默认使用 SQLite 便于直接运行演示；设置 DB_ENGINE=mysql 即切换到 MySQL。
if os.environ.get("DB_ENGINE") == "mysql":
    import pymysql

    pymysql.install_as_MySQLdb()
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "cost_verification"),
            "USER": os.environ.get("DB_USER", "root"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# 生产环境由 WhiteNoise 直接托管静态文件，无需 Nginx
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "pricing:login"
LOGIN_REDIRECT_URL = "pricing:dashboard"
LOGOUT_REDIRECT_URL = "pricing:login"

# 系统统一的增值税税率，用于含税/不含税口径换算
TAX_RATE = 0.13
USD_RATE = 7.10

SESSION_COOKIE_AGE = 60 * 60 * 12

# ---------------------------------------------------------------- 安全设置
# 生产模式默认启用安全 Cookie；本地 DEBUG 时关闭以便直接访问 HTTP。
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# 隧道 / 反向代理负责 HTTPS 时保持关闭，避免本地健康检查被重定向
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "0") == "1"
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
