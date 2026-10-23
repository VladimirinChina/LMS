from rest_framework import serializers

from .models import Course, Lesson
from .validators import validate_no_external_links, validate_youtube_link


class LessonSerializer(serializers.ModelSerializer):
    description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[validate_no_external_links],
    )
    video_url = serializers.URLField(
        max_length=200,
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[validate_youtube_link],
    )

    class Meta:
        model = Lesson
        fields = "__all__"
        read_only_fields = ("owner",)


class CourseSerializer(serializers.ModelSerializer):
    description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[validate_no_external_links],
    )
    lessons_count = serializers.SerializerMethodField()
    lessons = LessonSerializer(many=True, read_only=True)

    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = "__all__"
        read_only_fields = ("owner",)

    def get_lessons_count(self, obj: Course) -> int:
        return obj.lessons.count()

    def get_is_subscribed(self, obj: Course) -> bool:
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return obj.subscriptions.filter(user=request.user).exists()
