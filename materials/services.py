from datetime import datetime, timedelta

from django.utils import timezone

UPDATE_NOTIFICATION_INTERVAL = timedelta(hours=4)


def should_notify(previous_update: datetime) -> bool:
    """Уведомлять подписчиков, только если курс не обновлялся дольше 4 часов."""
    return timezone.now() - previous_update > UPDATE_NOTIFICATION_INTERVAL
