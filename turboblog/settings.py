import os
from pathlib import Path


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

SQLITE_FILE = os.environ.get("SQLITE_FILE") or str(BASE_DIR / "backend" / "data" / "turbo-blog-django.sqlite")

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
UPLOAD_DIR = BASE_DIR / "assets" / "uploads"
