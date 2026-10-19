from django.urls import path

from .apps import UsersConfig
from .views import UserRetrieveUpdateAPIView

app_name = UsersConfig.name

urlpatterns = [
    path("<int:pk>/", UserRetrieveUpdateAPIView.as_view(), name="user-detail"),
]
