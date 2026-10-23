from typing import Any, cast

from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from config.api_docs import BAD_REQUEST, FORBIDDEN, NOT_FOUND, UNAUTHORIZED

from .models import Payment, User
from .permissions import IsProfileOwner
from .serializers import (
    PaymentCreateSerializer,
    PaymentSerializer,
    UserPublicSerializer,
    UserRegisterSerializer,
    UserSerializer,
)
from .services import (
    PaymentServiceError,
    create_stripe_price,
    create_stripe_product,
    create_stripe_session,
    retrieve_stripe_session,
)

AUTH = ["Авторизация"]
USERS = ["Пользователи"]
PAYMENTS = ["Платежи"]


@extend_schema(
    tags=AUTH,
    summary="Получить пару JWT-токенов",
    description=(
        "Принимает `email` и `password`, возвращает `access` и `refresh`. " "При неверных данных возвращается 401."
    ),
)
class CustomTokenObtainPairView(TokenObtainPairView):
    pass


@extend_schema(
    tags=AUTH,
    summary="Обновить access-токен",
    description="Принимает `refresh`, возвращает новый `access`. Если refresh недействителен, возвращается 401.",
)
class CustomTokenRefreshView(TokenRefreshView):
    pass


@extend_schema_view(
    post=extend_schema(
        tags=AUTH,
        summary="Регистрация пользователя",
        description=(
            "Email должен быть уникальным (без учёта регистра), "
            "пароль проходит стандартные валидаторы Django (минимум 8 символов)."
        ),
        responses={201: UserRegisterSerializer, 400: BAD_REQUEST},
    )
)
class UserRegisterAPIView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]


@extend_schema_view(
    get=extend_schema(
        tags=USERS,
        summary="Список пользователей",
        description="Возвращает только общую информацию (без фамилии и истории платежей).",
        responses={200: UserPublicSerializer(many=True), 401: UNAUTHORIZED},
    )
)
class UserListAPIView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserPublicSerializer


@extend_schema_view(
    get=extend_schema(
        tags=USERS,
        summary="Профиль пользователя",
        description=(
            "Свой профиль возвращается полностью (с историей платежей), "
            "чужой только с общей информацией (без фамилии и платежей)."
        ),
        responses={200: UserSerializer, 401: UNAUTHORIZED, 404: NOT_FOUND},
    )
)
class UserRetrieveAPIView(generics.RetrieveAPIView):
    queryset = User.objects.all()

    def get_serializer_class(self) -> type[BaseSerializer[Any]]:
        if self.kwargs.get("pk") == self.request.user.pk:
            return UserSerializer
        return UserPublicSerializer


@extend_schema_view(
    put=extend_schema(
        tags=USERS,
        summary="Изменить свой профиль (полностью)",
        description="Редактировать можно только свой профиль.",
        responses={200: UserSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    ),
    patch=extend_schema(
        tags=USERS,
        summary="Изменить свой профиль (частично)",
        description="Редактировать можно только свой профиль.",
        responses={200: UserSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    ),
)
class UserUpdateAPIView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsProfileOwner]


@extend_schema_view(
    delete=extend_schema(
        tags=USERS,
        summary="Удалить свой профиль",
        description="Удалить можно только свой профиль.",
        responses={204: None, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    )
)
class UserDestroyAPIView(generics.DestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsProfileOwner]


@extend_schema_view(
    get=extend_schema(
        tags=PAYMENTS,
        summary="Список платежей",
        description=(
            "Поддерживает фильтрацию по курсу (`course`), уроку (`lesson`) "
            "и способу оплаты (`method`), а также сортировку по дате оплаты."
        ),
        parameters=[
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                enum=["paid_at", "-paid_at"],
                description=(
                    "Сортировка по дате оплаты: `paid_at` по возрастанию, "
                    "`-paid_at` по убыванию. По умолчанию новые платежи сверху."
                ),
            )
        ],
        responses={200: PaymentSerializer(many=True), 401: UNAUTHORIZED},
    )
)
class PaymentListAPIView(generics.ListAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ("course", "lesson", "method")
    ordering_fields = ("paid_at",)
    ordering = ("-paid_at",)


@extend_schema_view(
    post=extend_schema(
        tags=PAYMENTS,
        summary="Оплатить курс через Stripe",
        description=(
            "Создаёт в Stripe продукт, цену (в копейках) и сессию оплаты, "
            "сохраняет платёж и возвращает данные платежа со ссылкой на оплату "
            "в поле `payment_url`. Цена берётся из поля `price` курса."
        ),
        request=PaymentCreateSerializer,
        responses={
            201: PaymentSerializer,
            400: OpenApiResponse(description="Курс не найден или для курса не задана цена"),
            401: UNAUTHORIZED,
            502: OpenApiResponse(description="Платёжный сервис вернул ошибку или недоступен"),
        },
    )
)
class PaymentCreateAPIView(generics.CreateAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentCreateSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = serializer.validated_data["course"]

        if course.price <= 0:
            return Response(
                {"error": "Для курса не задана цена"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = create_stripe_product(course.title)
            price = create_stripe_price(product["id"], course.price)
            session = create_stripe_session(price["id"])
        except PaymentServiceError as error:
            return Response({"error": str(error)}, status=status.HTTP_502_BAD_GATEWAY)

        payment = Payment.objects.create(
            user=cast(User, request.user),
            course=course,
            amount=course.price,
            method=Payment.Method.TRANSFER,
            status=session.get("payment_status", "unpaid"),
            stripe_product_id=product["id"],
            stripe_price_id=price["id"],
            stripe_session_id=session["id"],
            payment_url=session["url"],
        )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=PAYMENTS,
        summary="Проверить статус платежа",
        description=(
            "Запрашивает у Stripe данные сессии оплаты, обновляет поле `status` платежа "
            "(`unpaid`, `paid`, `no_payment_required`) и возвращает платёж. "
            "Доступно только владельцу платежа."
        ),
        responses={
            200: PaymentSerializer,
            400: OpenApiResponse(description="У платежа нет сессии Stripe"),
            401: UNAUTHORIZED,
            404: NOT_FOUND,
            502: OpenApiResponse(description="Платёжный сервис вернул ошибку или недоступен"),
        },
    )
)
class PaymentStatusAPIView(generics.RetrieveAPIView):
    serializer_class = PaymentSerializer

    def get_queryset(self) -> QuerySet[Payment]:
        if getattr(self, "swagger_fake_view", False):
            return Payment.objects.none()
        return Payment.objects.filter(user=cast(User, self.request.user))

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        payment = self.get_object()
        if not payment.stripe_session_id:
            return Response(
                {"error": "Для этого платежа нет сессии Stripe"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = retrieve_stripe_session(payment.stripe_session_id)
        except PaymentServiceError as error:
            return Response({"error": str(error)}, status=status.HTTP_502_BAD_GATEWAY)

        payment.status = session["payment_status"]
        payment.save(update_fields=["status"])
        return Response(self.get_serializer(payment).data)
