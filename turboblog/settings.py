import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "turbo-blog-local-dev-secret")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") != "0"
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("ALLOWED_HOSTS", "*").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "blog",
]

MIDDLEWARE = [
    "blog.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "turboblog.urls"
WSGI_APPLICATION = "turboblog.wsgi.application"
ASGI_APPLICATION = "turboblog.asgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
REQUIRE_DATABASE_URL = os.environ.get("REQUIRE_DATABASE_URL", "0") == "1"
if REQUIRE_DATABASE_URL and not DATABASE_URL:
    raise ImproperlyConfigured("REQUIRE_DATABASE_URL=1 requires DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    SQLITE_FILE = os.environ.get("SQLITE_FILE") or str(
        BASE_DIR / "backend" / "data" / "turbo-blog-django.sqlite"
    )
    Path(SQLITE_FILE).expanduser().parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": SQLITE_FILE,
        }
    }

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

JSON_BODY_LIMIT = int(os.environ.get("JSON_BODY_LIMIT", 8 * 1024 * 1024))
IMAGE_UPLOAD_LIMIT = int(os.environ.get("IMAGE_UPLOAD_LIMIT", 5 * 1024 * 1024))
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "dev-token")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", ADMIN_TOKEN)
COMMENT_RATE_LIMIT_WINDOW_MS = int(os.environ.get("COMMENT_RATE_LIMIT_WINDOW_MS", 60_000))
COMMENT_RATE_LIMIT_MAX = int(os.environ.get("COMMENT_RATE_LIMIT_MAX", 6))
CAPTCHA_FAILURE_LIMIT = int(os.environ.get("CAPTCHA_FAILURE_LIMIT", 5))
SENSITIVE_WORDS = [
    word.strip().lower()
    for word in os.environ.get("SENSITIVE_WORDS", "spam,广告,博彩,辱骂").split(",")
    if word.strip()
]

AI_PROVIDER = os.environ.get("AI_PROVIDER", "local").strip().lower()
AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()
AI_API_BASE = os.environ.get("AI_API_BASE", "").strip().rstrip("/")
AI_API_URL = os.environ.get("AI_API_URL", "").strip()
if not AI_API_BASE and AI_PROVIDER == "deepseek":
    AI_API_BASE = "https://api.deepseek.com"
elif not AI_API_BASE and AI_PROVIDER == "openai":
    AI_API_BASE = "https://api.openai.com/v1"
if not AI_API_URL and AI_API_BASE:
    AI_API_URL = f"{AI_API_BASE}/chat/completions"
AI_MODEL = os.environ.get("AI_MODEL", "").strip()
if not AI_MODEL and AI_PROVIDER == "deepseek":
    AI_MODEL = "deepseek-chat"
elif not AI_MODEL and AI_PROVIDER == "openai":
    AI_MODEL = "gpt-4o-mini"
AI_TIMEOUT_SECONDS = int(os.environ.get("AI_TIMEOUT_SECONDS", 20))
AI_MAX_CONTEXT_CHARS = int(os.environ.get("AI_MAX_CONTEXT_CHARS", 5000))

STATIC_ROOT_DIR = BASE_DIR
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR") or BASE_DIR / "assets" / "uploads")

OBJECT_STORAGE_ENABLED = os.environ.get(
    "OBJECT_STORAGE_ENABLED", os.environ.get("R2_STORAGE_ENABLED", "0")
) == "1"
OBJECT_STORAGE_ENDPOINT_URL = os.environ.get(
    "OBJECT_STORAGE_ENDPOINT_URL",
    os.environ.get("AWS_ENDPOINT_URL", os.environ.get("R2_ENDPOINT_URL", "")),
).strip().rstrip("/")
OBJECT_STORAGE_ACCESS_KEY_ID = os.environ.get(
    "OBJECT_STORAGE_ACCESS_KEY_ID",
    os.environ.get("AWS_ACCESS_KEY_ID", os.environ.get("R2_ACCESS_KEY_ID", "")),
).strip()
OBJECT_STORAGE_SECRET_ACCESS_KEY = os.environ.get(
    "OBJECT_STORAGE_SECRET_ACCESS_KEY",
    os.environ.get("AWS_SECRET_ACCESS_KEY", os.environ.get("R2_SECRET_ACCESS_KEY", "")),
).strip()
OBJECT_STORAGE_BUCKET_NAME = os.environ.get(
    "OBJECT_STORAGE_BUCKET_NAME",
    os.environ.get("AWS_S3_BUCKET_NAME", os.environ.get("R2_BUCKET_NAME", "")),
).strip()
OBJECT_STORAGE_REGION = os.environ.get(
    "OBJECT_STORAGE_REGION", os.environ.get("AWS_DEFAULT_REGION", "auto")
).strip()
OBJECT_STORAGE_PUBLIC_BASE_URL = os.environ.get(
    "OBJECT_STORAGE_PUBLIC_BASE_URL", os.environ.get("R2_PUBLIC_BASE_URL", "")
).strip().rstrip("/")

# Backward-compatible aliases for existing R2 deployments.
R2_STORAGE_ENABLED = OBJECT_STORAGE_ENABLED
R2_ENDPOINT_URL = OBJECT_STORAGE_ENDPOINT_URL
R2_ACCESS_KEY_ID = OBJECT_STORAGE_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY = OBJECT_STORAGE_SECRET_ACCESS_KEY
R2_BUCKET_NAME = OBJECT_STORAGE_BUCKET_NAME
R2_PUBLIC_BASE_URL = OBJECT_STORAGE_PUBLIC_BASE_URL

if OBJECT_STORAGE_ENABLED:
    required_object_storage_settings = {
        "OBJECT_STORAGE_ENDPOINT_URL": OBJECT_STORAGE_ENDPOINT_URL,
        "OBJECT_STORAGE_ACCESS_KEY_ID": OBJECT_STORAGE_ACCESS_KEY_ID,
        "OBJECT_STORAGE_SECRET_ACCESS_KEY": OBJECT_STORAGE_SECRET_ACCESS_KEY,
        "OBJECT_STORAGE_BUCKET_NAME": OBJECT_STORAGE_BUCKET_NAME,
    }
    missing_object_storage_settings = [
        name for name, value in required_object_storage_settings.items() if not value
    ]
    if missing_object_storage_settings:
        raise ImproperlyConfigured(
            "OBJECT_STORAGE_ENABLED=1 requires: "
            + ", ".join(missing_object_storage_settings)
        )
