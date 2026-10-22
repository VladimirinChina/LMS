from typing import Any

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.serializers import BaseSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from config.api_docs import BAD_REQUEST, FORBIDDEN, NOT_FOUND, UNAUTHORIZED

from .models import Payment, User
from .permissions import IsProfileOwner
from .serializers import (
    PaymentSerializer,
    UserPublicSerializer,
    UserRegisterSerializer,
    UserSerializer,
)

AUTH = ["Авторизация"]
USERS = ["Пользователи"]
PAYMENTS = ["Платежи"]


@extend_schema(
    tags=AUTH,
    summary="Получить пару JWT-токенов",
    description=(
        "Принимает `email` и `password`, возвращает `access` и `refresh`. "
        "При неверных данных возвращается 401."
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
