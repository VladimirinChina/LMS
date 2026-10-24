from celery import shared_task
from django.conf import settings
from django.core.mail import send_mass_mail

from .models import Course, Subscription


@shared_task
def send_course_update_email(course_id: int) -> int:
    """Отправляет письмо об обновлении курса его активным подписчикам."""
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        return 0

    emails = Subscription.objects.filter(
        course=course, user__is_active=True
    ).values_list("user__email", flat=True)

    subject = f"Обновление курса «{course.title}»"
    message = (
        f"В курсе «{course.title}» обновились материалы. "
        "Загляните, чтобы посмотреть, что нового."
    )
    messages = [
        (subject, message, settings.DEFAULT_FROM_EMAIL, [email]) for email in emails
    ]
    if not messages:
        return 0
    return send_mass_mail(messages)
