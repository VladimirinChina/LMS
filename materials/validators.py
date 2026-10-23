import re
from urllib.parse import urlparse

from rest_framework.serializers import ValidationError

ALLOWED_DOMAIN = "youtube.com"
URL_PATTERN = re.compile(r"(?:https?://|www\.)[^\s]+", re.IGNORECASE)


def _is_allowed(url: str) -> bool:
    if "://" not in url:
        url = "https://" + url
    host = (urlparse(url).hostname or "").lower()
    return host == ALLOWED_DOMAIN or host.endswith("." + ALLOWED_DOMAIN)


def validate_youtube_link(value: str) -> None:
    """Для поля со ссылкой: допускается только youtube.com."""
    if value and not _is_allowed(value):
        raise ValidationError("Разрешены только ссылки на youtube.com")


def validate_no_external_links(value: str) -> None:
    """Для текстовых полей: в тексте не должно быть ссылок, кроме youtube.com."""
    for url in URL_PATTERN.findall(value or ""):
        if not _is_allowed(url):
            raise ValidationError(
                f"В тексте найдена ссылка на сторонний ресурс ({url}). " "Разрешены только ссылки на youtube.com"
            )
