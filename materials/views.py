from typing import Any, cast

from django.db.models import QuerySet
from rest_framework import generics, status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from users.models import User
from users.permissions import IsModer, IsOwner, is_moder

from .models import Course, Lesson, Subscription
from .paginators import CoursePagination, LessonPagination
from .serializers import CourseSerializer, LessonSerializer


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all().order_by("id")
    serializer_class = CourseSerializer
    pagination_class = CoursePagination

    def get_queryset(self) -> QuerySet[Course]:
        queryset = super().get_queryset()
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


class LessonListAPIView(generics.ListAPIView):
    queryset = Lesson.objects.all().order_by("id")
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LessonPagination

    def get_queryset(self) -> QuerySet[Lesson]:
        queryset = super().get_queryset()
        if not is_moder(self.request.user):
            return queryset.filter(owner=self.request.user)
        return queryset


class LessonCreateAPIView(generics.CreateAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, ~IsModer]

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        serializer.save(owner=self.request.user)


class LessonRetrieveAPIView(generics.RetrieveAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, IsModer | IsOwner]


class LessonUpdateAPIView(generics.UpdateAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, IsModer | IsOwner]


class LessonDestroyAPIView(generics.DestroyAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, ~IsModer, IsOwner]


class SubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

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
