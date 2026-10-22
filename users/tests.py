from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from materials.models import Course, Lesson

from .models import Payment, User


class UserTestCase(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="user@example.com",
            password="pass12345",
            first_name="Иван",
            last_name="Иванов",
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="pass12345",
            first_name="Пётр",
            last_name="Петров",
        )

    def test_register(self) -> None:
        data = {"email": "new@example.com", "password": "StrongPass123"}
        response = self.client.post(reverse("users:register"), data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.json())
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_register_duplicate_email(self) -> None:
        data = {"email": "USER@example.com", "password": "StrongPass123"}
        response = self.client.post(reverse("users:register"), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.json())

    def test_register_weak_password(self) -> None:
        data = {"email": "new@example.com", "password": "12345678"}
        response = self.client.post(reverse("users:register"), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.json())

    def test_obtain_token(self) -> None:
        data = {"email": "user@example.com", "password": "pass12345"}
        response = self.client.post(reverse("users:token-obtain"), data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())

    def test_obtain_token_wrong_password(self) -> None:
        data = {"email": "user@example.com", "password": "wrong"}
        response = self.client.post(reverse("users:token-obtain"), data)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self) -> None:
        data = {"email": "user@example.com", "password": "pass12345"}
        tokens = self.client.post(reverse("users:token-obtain"), data).json()

        response = self.client.post(reverse("users:token-refresh"), {"refresh": tokens["refresh"]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())

    def test_user_list(self) -> None:
        url = reverse("users:user-list")
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 2)
        self.assertNotIn("last_name", response.json()[0])

    def test_own_profile_is_full(self) -> None:
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("users:user-detail", args=[self.user.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["last_name"], "Иванов")
        self.assertIn("payments", response.json())

    def test_foreign_profile_is_public(self) -> None:
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("users:user-detail", args=[self.other.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["first_name"], "Пётр")
        self.assertNotIn("last_name", response.json())
        self.assertNotIn("payments", response.json())

    def test_update_own_profile(self) -> None:
        self.client.force_authenticate(user=self.user)
        url = reverse("users:user-update", args=[self.user.id])
        response = self.client.patch(url, {"city": "Москва"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.city, "Москва")

    def test_update_foreign_profile_forbidden(self) -> None:
        self.client.force_authenticate(user=self.user)
        url = reverse("users:user-update", args=[self.other.id])
        response = self.client.patch(url, {"city": "Москва"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_profile(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(reverse("users:user-delete", args=[self.other.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.delete(reverse("users:user-delete", args=[self.user.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())


class PaymentTestCase(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="user@example.com", password="pass12345")
        self.course = Course.objects.create(title="Курс", owner=self.user)
        self.lesson = Lesson.objects.create(course=self.course, title="Урок", owner=self.user)
        now = timezone.now()
        self.old_payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            amount=Decimal("5000.00"),
            method=Payment.Method.TRANSFER,
            paid_at=now - timedelta(days=5),
        )
        self.new_payment = Payment.objects.create(
            user=self.user,
            lesson=self.lesson,
            amount=Decimal("700.00"),
            method=Payment.Method.CASH,
            paid_at=now - timedelta(days=1),
        )
        self.url = reverse("users:payment-list")

    def _ids(self, params: dict[str, object] | None = None) -> list[int]:
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [item["id"] for item in response.json()]

    def test_payments_unauthenticated(self) -> None:
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_default_ordering_newest_first(self) -> None:
        self.client.force_authenticate(user=self.user)

        self.assertEqual(self._ids(), [self.new_payment.id, self.old_payment.id])

    def test_ordering_asc_and_desc(self) -> None:
        self.client.force_authenticate(user=self.user)

        self.assertEqual(self._ids({"ordering": "paid_at"}), [self.old_payment.id, self.new_payment.id])
        self.assertEqual(self._ids({"ordering": "-paid_at"}), [self.new_payment.id, self.old_payment.id])

    def test_filter_by_course(self) -> None:
        self.client.force_authenticate(user=self.user)

        self.assertEqual(self._ids({"course": self.course.id}), [self.old_payment.id])

    def test_filter_by_lesson(self) -> None:
        self.client.force_authenticate(user=self.user)

        self.assertEqual(self._ids({"lesson": self.lesson.id}), [self.new_payment.id])

    def test_filter_by_method(self) -> None:
        self.client.force_authenticate(user=self.user)

        self.assertEqual(self._ids({"method": "cash"}), [self.new_payment.id])
        self.assertEqual(self._ids({"method": "transfer"}), [self.old_payment.id])

    def test_combined_filters(self) -> None:
        self.client.force_authenticate(user=self.user)

        self.assertEqual(
            self._ids({"course": self.course.id, "method": "transfer"}),
            [self.old_payment.id],
        )
        self.assertEqual(self._ids({"course": self.course.id, "method": "cash"}), [])

    def test_payment_history_in_profile(self) -> None:
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("users:user-detail", args=[self.user.id]))

        payments = response.json()["payments"]
        self.assertEqual(len(payments), 2)
        self.assertIn("amount", payments[0])


class FillPaymentsCommandTestCase(TestCase):
    def test_command_creates_payments_without_duplicates(self) -> None:
        call_command("fill_payments", stdout=StringIO())
        self.assertEqual(Payment.objects.count(), 4)

        call_command("fill_payments", stdout=StringIO())
        self.assertEqual(Payment.objects.count(), 4)


class DocsTestCase(APITestCase):
    def test_schema_and_docs_available(self) -> None:
        for name in ("schema", "swagger-ui", "redoc"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
