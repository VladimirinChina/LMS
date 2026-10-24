from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from .models import User

INACTIVITY_PERIOD = timedelta(days=30)


@shared_task
def block_inactive_users() -> int:
    """Блокирует пользователей, которые не заходили более месяца."""
    threshold = timezone.now() - INACTIVITY_PERIOD
    inactive = Q(last_login__lt=threshold) | Q(
        last_login__isnull=True, date_joined__lt=threshold
    )
    return User.objects.filter(inactive, is_active=True, is_superuser=False).update(
        is_active=False
    )
