# LMS (backend)

Бэкенд для LMS-системы, где можно размещать курсы и уроки. Проект реализован на Django и Django REST Framework, клиенту возвращаются JSON-структуры.

## Возможности

- Пользователи с авторизацией по email (кастомная модель на основе `AbstractBaseUser`): телефон, город, аватарка.
- Курсы: название, превью, описание. CRUD через `ViewSet`.
- Уроки: название, описание, превью, ссылка на видео, привязка к курсу. CRUD через Generic-классы.
- Редактирование профиля пользователя (`RetrieveUpdateAPIView`).

На данном этапе авторизация и права доступа не используются: все эндпоинты открыты.

## Технологии

- Python 3.14
- Django, Django REST Framework
- Pillow (работа с изображениями)
- SQLite
- Poetry (управление зависимостями)
- black, flake8, mypy (django-stubs)

## Установка и запуск

1. Клонировать репозиторий и перейти в папку проекта.
2. Установить зависимости:

```bash
   poetry install
```

3. Применить миграции:

```bash
   poetry run python manage.py migrate
```

4. Создать суперпользователя (вход по email):

```bash
   poetry run python manage.py createsuperuser
```

5. Запустить сервер:

```bash
   poetry run python manage.py runserver
```

Сервер будет доступен по адресу http://127.0.0.1:8000/, админка: http://127.0.0.1:8000/admin/.

## Эндпоинты

| Метод | URL | Описание |
|---|---|---|
| GET | `/courses/` | список курсов |
| POST | `/courses/` | создать курс |
| GET | `/courses/<id>/` | получить курс |
| PUT / PATCH | `/courses/<id>/` | изменить курс |
| DELETE | `/courses/<id>/` | удалить курс |
| GET | `/lessons/` | список уроков |
| POST | `/lessons/create/` | создать урок |
| GET | `/lessons/<id>/` | получить урок |
| PUT / PATCH | `/lessons/<id>/update/` | изменить урок |
| DELETE | `/lessons/<id>/delete/` | удалить урок |
| GET | `/users/<id>/` | получить профиль пользователя |
| PUT / PATCH | `/users/<id>/` | изменить профиль пользователя |

Для создания урока обязательно указать id существующего курса в поле `course`.
Для загрузки изображений (`preview`, `avatar`) используется `multipart/form-data`.

## Структура проекта

- `config/` — настройки проекта и корневые маршруты
- `users/` — модель пользователя, сериализатор и контроллер профиля
- `materials/` — модели курса и урока, сериализаторы, контроллеры и маршруты

## Проверка качества кода

```bash
poetry run black .
poetry run flake8
poetry run mypy .
```