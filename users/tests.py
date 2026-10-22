from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch, MagicMock

import stripe
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from materials.models import Course, Lesson

from .models import Payment, User
from .services import PaymentServiceError, create_stripe_price, create_stripe_product


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


class StripePaymentTestCase(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="user@example.com", password="pass12345")
        self.other = User.objects.create_user(email="other@example.com", password="pass12345")
        self.course = Course.objects.create(title="Курс", price=Decimal("5000.00"), owner=self.user)
        self.url = reverse("users:payment-create")
        self.session = {
            "id": "cs_test_1",
            "url": "https://checkout.stripe.com/c/pay/cs_test_1",
            "payment_status": "unpaid",
        }

    @patch("users.views.create_stripe_session")
    @patch("users.views.create_stripe_price")
    @patch("users.views.create_stripe_product")
    def test_create_payment(self, mock_product: MagicMock, mock_price: MagicMock, mock_session: MagicMock) -> None:
        mock_product.return_value = {"id": "prod_1"}
        mock_price.return_value = {"id": "price_1"}
        mock_session.return_value = self.session
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, {"course": self.course.id})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["payment_url"], self.session["url"])
        payment = Payment.objects.get(stripe_session_id="cs_test_1")
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.course, self.course)
        self.assertEqual(payment.amount, Decimal("5000.00"))
        self.assertEqual(payment.stripe_product_id, "prod_1")
        self.assertEqual(payment.stripe_price_id, "price_1")
        mock_product.assert_called_once_with("Курс")
        mock_price.assert_called_once_with("prod_1", Decimal("5000.00"))
        mock_session.assert_called_once_with("price_1")

    @patch("users.views.create_stripe_product")
    def test_create_payment_stripe_error(self, mock_product: MagicMock) -> None:
        mock_product.side_effect = PaymentServiceError("Ошибка Stripe")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, {"course": self.course.id})

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("error", response.json())
        self.assertEqual(Payment.objects.count(), 0)

    def test_create_payment_course_without_price(self) -> None:
        free_course = Course.objects.create(title="Бесплатный", owner=self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, {"course": free_course.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_invalid_course(self) -> None:
        self.client.force_authenticate(user=self.user)

        self.assertEqual(
            self.client.post(self.url, {"course": 99999}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(self.client.post(self.url, {}).status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_unauthenticated(self) -> None:
        response = self.client.post(self.url, {"course": self.course.id})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("users.views.retrieve_stripe_session")
    def test_payment_status_is_synced(self, mock_retrieve: MagicMock) -> None:
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            amount=Decimal("5000.00"),
            stripe_session_id="cs_test_1",
        )
        mock_retrieve.return_value = {"payment_status": "paid"}
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("users:payment-status", args=[payment.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "paid")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "paid")
        mock_retrieve.assert_called_once_with("cs_test_1")

    def test_payment_status_of_foreign_payment(self) -> None:
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            amount=Decimal("5000.00"),
            stripe_session_id="cs_test_1",
        )
        self.client.force_authenticate(user=self.other)

        response = self.client.get(reverse("users:payment-status", args=[payment.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_payment_status_without_session(self) -> None:
        payment = Payment.objects.create(user=self.user, course=self.course, amount=Decimal("5000.00"))
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("users:payment-status", args=[payment.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("users.views.retrieve_stripe_session")
    def test_payment_status_stripe_error(self, mock_retrieve: MagicMock) -> None:
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            amount=Decimal("5000.00"),
            stripe_session_id="cs_test_1",
        )
        mock_retrieve.side_effect = PaymentServiceError("Ошибка Stripe")
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("users:payment-status", args=[payment.id]))

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)


class StripeServiceTestCase(TestCase):
    @override_settings(STRIPE_API_KEY="sk_test_x")
    @patch("users.services.stripe.Price.create")
    def test_price_is_in_kopecks(self, mock_create: MagicMock) -> None:
        create_stripe_price("prod_1", Decimal("5000.00"))

        mock_create.assert_called_once_with(
            currency=settings.STRIPE_CURRENCY,
            unit_amount=500000,
            product="prod_1",
        )

    @override_settings(STRIPE_API_KEY="")
    def test_missing_api_key(self) -> None:
        with self.assertRaises(PaymentServiceError):
            create_stripe_product("Курс")

    @override_settings(STRIPE_API_KEY="sk_test_x")
    @patch("users.services.stripe.Product.create")
    def test_stripe_error_is_wrapped(self, mock_create: MagicMock) -> None:
        mock_create.side_effect = stripe.StripeError("boom")

        with self.assertRaises(PaymentServiceError):
            create_stripe_product("Курс")
