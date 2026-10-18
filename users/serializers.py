from rest_framework import serializers

from .models import Payment, User


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class UserPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ("id", "paid_at", "course", "lesson", "amount", "method")


class UserSerializer(serializers.ModelSerializer):
    payments = UserPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "city",
            "avatar",
            "payments",
        )
