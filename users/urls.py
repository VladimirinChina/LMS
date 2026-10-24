from django.urls import path

from .apps import UsersConfig
from .views import (CustomTokenObtainPairView, CustomTokenRefreshView, PaymentCreateAPIView, PaymentListAPIView,
                    PaymentStatusAPIView, UserDestroyAPIView, UserListAPIView, UserRegisterAPIView,
                    UserRetrieveAPIView, UserUpdateAPIView)

app_name = UsersConfig.name

urlpatterns = [
    path("register/", UserRegisterAPIView.as_view(), name="register"),
    path("token/", CustomTokenObtainPairView.as_view(), name="token-obtain"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("payments/", PaymentListAPIView.as_view(), name="payment-list"),
    path("", UserListAPIView.as_view(), name="user-list"),
    path("<int:pk>/", UserRetrieveAPIView.as_view(), name="user-detail"),
    path("<int:pk>/update/", UserUpdateAPIView.as_view(), name="user-update"),
    path("<int:pk>/delete/", UserDestroyAPIView.as_view(), name="user-delete"),
    path("payments/create/", PaymentCreateAPIView.as_view(), name="payment-create"),
    path("payments/<int:pk>/status/", PaymentStatusAPIView.as_view(), name="payment-status"),
]
