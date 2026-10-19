from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

MODERS_GROUP = "moders"


def is_moder(user: Any) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.groups.filter(name=MODERS_GROUP).exists()
    )


class IsModer(BasePermission):
    """Пользователь входит в группу модераторов."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return is_moder(request.user)

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        return is_moder(request.user)


class IsOwner(BasePermission):
    """Пользователь является владельцем объекта."""

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        return bool(obj.owner == request.user)


class IsProfileOwner(BasePermission):
    """Пользователь работает со своим профилем."""

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        return bool(obj == request.user)
