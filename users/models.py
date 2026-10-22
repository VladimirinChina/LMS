from typing import ClassVar

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, verbose_name="Email")
    first_name = models.CharField(max_length=150, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=150, blank=True, verbose_name="Фамилия")
    phone = models.CharField(max_length=35, blank=True, null=True, verbose_name="Телефон")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="Город")
    avatar = models.ImageField(upload_to="users/avatars/", blank=True, null=True, verbose_name="Аватар")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_staff = models.BooleanField(default=False, verbose_name="Сотрудник")
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects = UserManager()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        return self.email


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Наличные"
        TRANSFER = "transfer", "Перевод на счёт"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Пользователь",
    )
    paid_at = models.DateTimeField(default=timezone.now, verbose_name="Дата оплаты")
    course = models.ForeignKey(
        "materials.Course",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="payments",
        verbose_name="Оплаченный курс",
    )
    lesson = models.ForeignKey(
        "materials.Lesson",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="payments",
        verbose_name="Оплаченный урок",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма оплаты")
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.TRANSFER,
        verbose_name="Способ оплаты",
    )
    status = models.CharField(
        max_length=30, default="unpaid", verbose_name="Статус оплаты (Stripe)"
    )
    stripe_product_id = models.CharField(
        max_length=255, blank=True, default="", verbose_name="ID продукта Stripe"
    )
    stripe_price_id = models.CharField(
        max_length=255, blank=True, default="", verbose_name="ID цены Stripe"
    )
    stripe_session_id = models.CharField(
        max_length=255, blank=True, default="", verbose_name="ID сессии Stripe"
    )
    payment_url = models.URLField(
        max_length=2000, blank=True, default="", verbose_name="Ссылка на оплату"
    )

    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"

    def __str__(self) -> str:
        return f"{self.user} — {self.amount} ({self.paid_at:%Y-%m-%d})"
