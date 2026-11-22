"""Isolated settings for repeatable local browser checks; never use in production."""
from config.settings import *  # noqa: F403

QA_ROOT = BASE_DIR / ".qa"
QA_ROOT.mkdir(exist_ok=True)
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": QA_ROOT / "browser.sqlite3"}}
MEDIA_ROOT = QA_ROOT / "media"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
SECRET_KEY = "isolated-browser-check-only"
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SITE_URL = "http://127.0.0.1:8765"
