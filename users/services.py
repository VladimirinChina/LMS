from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

import stripe
from django.conf import settings


class PaymentServiceError(Exception):
    """Ошибка при обращении к платёжному сервису."""


@contextmanager
def _stripe_errors() -> Iterator[None]:
    if not settings.STRIPE_API_KEY:
        raise PaymentServiceError("Не задан STRIPE_API_KEY в настройках проекта")
    stripe.api_key = settings.STRIPE_API_KEY
    try:
        yield
    except stripe.StripeError as error:
        raise PaymentServiceError(error.user_message or str(error)) from error


def create_stripe_product(name: str) -> Any:
    with _stripe_errors():
        product = stripe.Product.create(name=name)
    return product


def create_stripe_price(product_id: str, amount: Decimal) -> Any:
    unit_amount = int(amount * 100)  # Stripe принимает сумму в копейках
    with _stripe_errors():
        price = stripe.Price.create(
            currency=settings.STRIPE_CURRENCY,
            unit_amount=unit_amount,
            product=product_id,
        )
    return price


def create_stripe_session(price_id: str) -> Any:
    with _stripe_errors():
        session = stripe.checkout.Session.create(
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
            line_items=[{"price": price_id, "quantity": 1}],
            mode="payment",
        )
    return session


def retrieve_stripe_session(session_id: str) -> Any:
    with _stripe_errors():
        session = stripe.checkout.Session.retrieve(session_id)
    return session
