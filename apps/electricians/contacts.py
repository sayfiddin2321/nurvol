"""Validate contact handles once; use the same links on every public surface."""
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError


def normalize_social(value, service):
    value = (value or "").strip()
    if not value:
        return ""
    domains = {"telegram": {"t.me", "telegram.me", "www.t.me"},
               "instagram": {"instagram.com", "www.instagram.com"}}[service]
    if "://" in value or "/" in value:
        parsed = urlsplit(value if "://" in value else "https://" + value)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in domains:
            raise ValidationError("Profil havolasi yoki @foydalanuvchi nomini kiriting.")
        value = parsed.path.strip("/")
    value = value.removeprefix("@")
    pattern = r"[A-Za-z][A-Za-z0-9_]{4,31}" if service == "telegram" else r"[A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?"
    if not re.fullmatch(pattern, value) or ".." in value:
        raise ValidationError("Foydalanuvchi nomi formati noto'g'ri.")
    if service == "instagram" and value.lower() in {"p", "reel", "reels", "stories", "explore", "accounts"}:
        raise ValidationError("Post emas, profil havolasini kiriting.")
    return value


def social_url(value, service):
    try:
        handle = normalize_social(value, service)
    except (ValidationError, ValueError):
        return ""
    domain = "t.me" if service == "telegram" else "instagram.com"
    return f"https://{domain}/{handle}" if handle else ""


def phone_uri(value):
    value = (value or "").strip()
    if not value or not re.fullmatch(r"\+?[\d ()-]+", value):
        return ""
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 15:
        return ""
    return "tel:" + ("+" if value.startswith("+") else "") + digits
