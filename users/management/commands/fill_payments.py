from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from materials.models import Course, Lesson
from users.models import Payment, User


class Command(BaseCommand):
    help = "Заполняет таблицу платежей тестовыми данными"

    def handle(self, *args: Any, **options: Any) -> None:
        now = timezone.now()

        course, _ = Course.objects.get_or_create(
            title="Python для начинающих",
            defaults={"description": "Основы языка"},
        )
        lesson, _ = Lesson.objects.get_or_create(
            course=course,
            title="Введение",
            defaults={"description": "Первый урок"},
        )

        users = []
        for email in ("student1@example.com", "student2@example.com"):
            user = User.objects.filter(email=email).first() or User.objects.create_user(email=email)
            users.append(user)

        payments = [
            (users[0], course, None, "5000.00", Payment.Method.TRANSFER, 10),
            (users[0], None, lesson, "700.00", Payment.Method.CASH, 5),
            (users[1], course, None, "5000.00", Payment.Method.CASH, 3),
            (users[1], None, lesson, "700.00", Payment.Method.TRANSFER, 1),
        ]

        created = 0
        for user, pay_course, pay_lesson, amount, method, days_ago in payments:
            _, is_created = Payment.objects.get_or_create(
                user=user,
                course=pay_course,
                lesson=pay_lesson,
                amount=Decimal(amount),
                method=method,
                defaults={"paid_at": now - timedelta(days=days_ago)},
            )
            created += is_created

        self.stdout.write(self.style.SUCCESS(f"Создано платежей: {created}"))