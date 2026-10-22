from typing import Any, cast

from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from config.api_docs import BAD_REQUEST, FORBIDDEN, NOT_FOUND, UNAUTHORIZED
from users.models import User
from users.permissions import IsModer, IsOwner, is_moder

from .models import Course, Lesson, Subscription
from .paginators import CoursePagination, LessonPagination
from .serializers import (
    CourseSerializer,
    LessonSerializer,
    SubscriptionRequestSerializer,
    SubscriptionResponseSerializer,
)

COURSES = ["Курсы"]
LESSONS = ["Уроки"]
OWNER_NOTE = "Доступно модератору и владельцу объекта."


@extend_schema_view(
    list=extend_schema(
        tags=COURSES,
        summary="Список курсов",
        description="Обычный пользователь видит только свои курсы, модератор все. Ответ постраничный.",
        responses={200: CourseSerializer(many=True), 401: UNAUTHORIZED},
    ),
    create=extend_schema(
        tags=COURSES,
        summary="Создать курс",
        description="Недоступно модераторам. Владелец проставляется автоматически.",
        responses={201: CourseSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 403: FORBIDDEN},
    ),
    retrieve=extend_schema(
        tags=COURSES,
        summary="Получить курс",
        description=f"Включает количество уроков, список уроков и признак подписки. {OWNER_NOTE}",
        responses={200: CourseSerializer, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    ),
    update=extend_schema(
        tags=COURSES,
        summary="Изменить курс (полностью)",
        description=OWNER_NOTE,
        responses={200: CourseSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    ),
    partial_update=extend_schema(
        tags=COURSES,
        summary="Изменить курс (частично)",
        description=OWNER_NOTE,
        responses={200: CourseSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    ),
    destroy=extend_schema(
        tags=COURSES,
        summary="Удалить курс",
        description="Доступно только владельцу, модераторам удаление недоступно.",
        responses={204: None, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    ),
)
class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all().order_by("id")
    serializer_class = CourseSerializer
    pagination_class = CoursePagination

    def get_queryset(self) -> QuerySet[Course]:
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        if self.action == "list" and not is_moder(self.request.user):
            return queryset.filter(owner=self.request.user)
        return queryset

    def get_permissions(self) -> list[BasePermission]:
        permission_classes: list[Any]
        if self.action == "create":
            permission_classes = [IsAuthenticated, ~IsModer]
        elif self.action in ("retrieve", "update", "partial_update"):
            permission_classes = [IsAuthenticated, IsModer | IsOwner]
        elif self.action == "destroy":
            permission_classes = [IsAuthenticated, ~IsModer, IsOwner]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        serializer.save(owner=self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=LESSONS,
        summary="Список уроков",
        description="Обычный пользователь видит только свои уроки, модератор все. Ответ постраничный.",
        responses={200: LessonSerializer(many=True), 401: UNAUTHORIZED},
    )
)
class LessonListAPIView(generics.ListAPIView):
    queryset = Lesson.objects.all().order_by("id")
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LessonPagination

    def get_queryset(self) -> QuerySet[Lesson]:
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        if not is_moder(self.request.user):
            return queryset.filter(owner=self.request.user)
        return queryset


@extend_schema_view(
    post=extend_schema(
        tags=LESSONS,
        summary="Создать урок",
        description=(
            "Недоступно модераторам. Владелец проставляется автоматически. "
            "Ссылка в `video_url` и ссылки в описании могут вести только на youtube.com."
        ),
        responses={201: LessonSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 403: FORBIDDEN},
    )
)
class LessonCreateAPIView(generics.CreateAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, ~IsModer]

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        serializer.save(owner=self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=LESSONS,
        summary="Получить урок",
        description=OWNER_NOTE,
        responses={200: LessonSerializer, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    )
)
class LessonRetrieveAPIView(generics.RetrieveAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, IsModer | IsOwner]


@extend_schema_view(
    put=extend_schema(
        tags=LESSONS,
        summary="Изменить урок (полностью)",
        description=OWNER_NOTE,
        responses={200: LessonSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    ),
    patch=extend_schema(
        tags=LESSONS,
        summary="Изменить урок (частично)",
        description=OWNER_NOTE,
        responses={200: LessonSerializer, 400: BAD_REQUEST, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    ),
)
class LessonUpdateAPIView(generics.UpdateAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, IsModer | IsOwner]


@extend_schema_view(
    delete=extend_schema(
        tags=LESSONS,
        summary="Удалить урок",
        description="Доступно только владельцу, модераторам удаление недоступно.",
        responses={204: None, 401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
    )
)
class LessonDestroyAPIView(generics.DestroyAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, ~IsModer, IsOwner]


class SubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Подписки"],
        summary="Подписаться на курс или отписаться",
        description=(
            "Если подписки пользователя на курс нет, она создаётся, "
            "если есть, удаляется. Результат описан в поле `message`."
        ),
        request=SubscriptionRequestSerializer,
        responses={
            200: SubscriptionResponseSerializer,
            400: OpenApiResponse(description="Не указан id курса (поле `course`)"),
            401: UNAUTHORIZED,
            404: OpenApiResponse(description="Курс не найден"),
        },
    )
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        data = request.data
        course_id = data.get("course") if isinstance(data, dict) else None
        if course_id is None:
            return Response(
                {"error": "Не указан id курса (поле course)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course = get_object_or_404(Course, pk=course_id)
        subscription = Subscription.objects.filter(user=user, course=course)

        if subscription.exists():
            subscription.delete()
            message = "Подписка удалена"
        else:
            Subscription.objects.create(user=user, course=course)
            message = "Подписка добавлена"

        return Response({"message": message})
