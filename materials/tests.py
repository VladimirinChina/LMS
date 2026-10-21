from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User
from users.permissions import MODERS_GROUP

from .models import Course, Lesson, Subscription


class BaseTestCase(APITestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(email="owner@example.com", password="pass12345")
        self.other = User.objects.create_user(email="other@example.com", password="pass12345")
        self.moder = User.objects.create_user(email="moder@example.com", password="pass12345")
        group, _ = Group.objects.get_or_create(name=MODERS_GROUP)
        self.moder.groups.add(group)

        self.course = Course.objects.create(title="Курс", description="Описание курса", owner=self.owner)
        self.lesson = Lesson.objects.create(
            course=self.course,
            title="Урок",
            description="Описание урока",
            video_url="https://www.youtube.com/watch?v=abc",
            owner=self.owner,
        )


class LessonTestCase(BaseTestCase):
    def test_create_lesson(self) -> None:
        self.client.force_authenticate(user=self.owner)
        data = {
            "title": "Новый урок",
            "description": "Описание",
            "course": self.course.id,
            "video_url": "https://www.youtube.com/watch?v=xyz",
        }
        response = self.client.post(reverse("materials:lesson-create"), data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["owner"], self.owner.id)
        self.assertEqual(Lesson.objects.count(), 2)

    def test_create_lesson_with_foreign_link(self) -> None:
        self.client.force_authenticate(user=self.owner)
        data = {
            "title": "Новый урок",
            "course": self.course.id,
            "video_url": "https://vimeo.com/123",
        }
        response = self.client.post(reverse("materials:lesson-create"), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("video_url", response.json())
        self.assertEqual(Lesson.objects.count(), 1)

    def test_create_lesson_with_foreign_link_in_description(self) -> None:
        self.client.force_authenticate(user=self.owner)
        data = {
            "title": "Новый урок",
            "description": "Смотри https://stepik.org/course",
            "course": self.course.id,
        }
        response = self.client.post(reverse("materials:lesson-create"), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("description", response.json())

    def test_create_lesson_by_moder_forbidden(self) -> None:
        self.client.force_authenticate(user=self.moder)
        data = {"title": "Урок модера", "course": self.course.id}
        response = self.client.post(reverse("materials:lesson-create"), data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_lesson_unauthenticated(self) -> None:
        data = {"title": "Урок", "course": self.course.id}
        response = self.client.post(reverse("materials:lesson-create"), data)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_lessons_by_role(self) -> None:
        url = reverse("materials:lesson-list")

        self.client.force_authenticate(user=self.owner)
        self.assertEqual(self.client.get(url).json()["count"], 1)

        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(url).json()["count"], 0)

        self.client.force_authenticate(user=self.moder)
        self.assertEqual(self.client.get(url).json()["count"], 1)

    def test_retrieve_lesson(self) -> None:
        url = reverse("materials:lesson-detail", args=[self.lesson.id])

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["title"], "Урок")

        self.client.force_authenticate(user=self.moder)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)

    def test_update_lesson(self) -> None:
        url = reverse("materials:lesson-update", args=[self.lesson.id])

        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(url, {"title": "Новое название"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.title, "Новое название")

        self.client.force_authenticate(user=self.moder)
        response = self.client.patch(url, {"title": "Правка модератора"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.other)
        response = self.client.patch(url, {"title": "Взлом"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_lesson_by_owner(self) -> None:
        self.client.force_authenticate(user=self.owner)
        url = reverse("materials:lesson-delete", args=[self.lesson.id])
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Lesson.objects.filter(id=self.lesson.id).exists())

    def test_delete_lesson_forbidden(self) -> None:
        url = reverse("materials:lesson-delete", args=[self.lesson.id])

        self.client.force_authenticate(user=self.moder)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)

        self.assertTrue(Lesson.objects.filter(id=self.lesson.id).exists())

    def test_delete_lesson_not_found(self) -> None:
        self.client.force_authenticate(user=self.owner)
        url = reverse("materials:lesson-delete", args=[99999])

        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)


class SubscriptionTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = reverse("materials:subscription")

    def test_subscribe_and_unsubscribe(self) -> None:
        self.client.force_authenticate(user=self.other)

        response = self.client.post(self.url, {"course": self.course.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["message"], "Подписка добавлена")
        self.assertTrue(Subscription.objects.filter(user=self.other, course=self.course).exists())

        response = self.client.post(self.url, {"course": self.course.id})
        self.assertEqual(response.json()["message"], "Подписка удалена")
        self.assertFalse(Subscription.objects.filter(user=self.other, course=self.course).exists())

    def test_subscribe_course_not_found(self) -> None:
        self.client.force_authenticate(user=self.other)
        response = self.client.post(self.url, {"course": 99999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_subscribe_without_course_id(self) -> None:
        self.client.force_authenticate(user=self.other)
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_subscribe_unauthenticated(self) -> None:
        response = self.client.post(self.url, {"course": self.course.id})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_subscription_is_unique(self) -> None:
        Subscription.objects.create(user=self.other, course=self.course)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Subscription.objects.create(user=self.other, course=self.course)

    def test_is_subscribed_flag(self) -> None:
        Subscription.objects.create(user=self.owner, course=self.course)
        url = reverse("materials:courses-detail", args=[self.course.id])

        self.client.force_authenticate(user=self.owner)
        self.assertTrue(self.client.get(url).json()["is_subscribed"])

        self.client.force_authenticate(user=self.moder)
        self.assertFalse(self.client.get(url).json()["is_subscribed"])


class CoursePaginationTestCase(BaseTestCase):
    def test_course_list_is_paginated(self) -> None:
        for number in range(6):
            Course.objects.create(title=f"Курс {number}", owner=self.owner)
        self.client.force_authenticate(user=self.owner)
        url = reverse("materials:courses-list")

        response = self.client.get(url)
        self.assertEqual(response.json()["count"], 7)
        self.assertEqual(len(response.json()["results"]), 5)

        response = self.client.get(url, {"page_size": 2})
        self.assertEqual(len(response.json()["results"]), 2)


class CourseTestCase(BaseTestCase):
    def test_create_course(self) -> None:
        self.client.force_authenticate(user=self.owner)
        data = {"title": "Новый курс", "description": "Описание"}
        response = self.client.post(reverse("materials:courses-list"), data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["owner"], self.owner.id)

    def test_create_course_with_foreign_link(self) -> None:
        self.client.force_authenticate(user=self.owner)
        data = {"title": "Новый курс", "description": "Тут https://stepik.org"}
        response = self.client.post(reverse("materials:courses-list"), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("description", response.json())

    def test_create_course_by_moder_forbidden(self) -> None:
        self.client.force_authenticate(user=self.moder)
        response = self.client.post(reverse("materials:courses-list"), {"title": "Курс"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_course_unauthenticated(self) -> None:
        response = self.client.post(reverse("materials:courses-list"), {"title": "Курс"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_courses_by_role(self) -> None:
        url = reverse("materials:courses-list")

        self.client.force_authenticate(user=self.owner)
        self.assertEqual(self.client.get(url).json()["count"], 1)

        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(url).json()["count"], 0)

        self.client.force_authenticate(user=self.moder)
        self.assertEqual(self.client.get(url).json()["count"], 1)

    def test_retrieve_course(self) -> None:
        url = reverse("materials:courses-detail", args=[self.course.id])

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["lessons_count"], 1)
        self.assertEqual(len(response.json()["lessons"]), 1)

        self.client.force_authenticate(user=self.moder)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)

    def test_update_course(self) -> None:
        url = reverse("materials:courses-detail", args=[self.course.id])

        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(url, {"title": "Новое название"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, "Новое название")

        self.client.force_authenticate(user=self.moder)
        response = self.client.patch(url, {"title": "Правка модератора"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.other)
        response = self.client.patch(url, {"title": "Взлом"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_course_forbidden(self) -> None:
        url = reverse("materials:courses-detail", args=[self.course.id])

        self.client.force_authenticate(user=self.moder)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)

        self.assertTrue(Course.objects.filter(id=self.course.id).exists())

    def test_delete_course_by_owner(self) -> None:
        self.client.force_authenticate(user=self.owner)
        url = reverse("materials:courses-detail", args=[self.course.id])
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Course.objects.filter(id=self.course.id).exists())
