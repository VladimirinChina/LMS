# LMS (backend)

Бэкенд для LMS-системы, где можно размещать курсы и уроки. Проект реализован на Django и Django REST Framework, клиенту возвращаются JSON-структуры.

## Возможности

- Пользователи с авторизацией по email (кастомная модель на основе `AbstractBaseUser`): телефон, город, аватарка.
- Регистрация пользователей и JWT-авторизация (access/refresh токены).
- Курсы и уроки с привязкой к владельцу. CRUD курсов через `ViewSet`, CRUD уроков через Generic-классы.
- Количество уроков и список уроков в сериализаторе курса.
- Платежи (наличные или перевод), фильтрация и сортировка списка платежей, история платежей в профиле.
- Группа модераторов и разграничение прав доступа.
- Валидация ссылок: в уроках и курсах допускаются только ссылки на youtube.com.
- Подписка на обновления курса, признак подписки `is_subscribed` в данных курса.
- Пагинация списков курсов и уроков.

На данном этапе авторизация и права доступа не используются: все эндпоинты открыты.

## Технологии

- Python 3.14
- Django, Django REST Framework
- Pillow (работа с изображениями)
- PostgreSQL
- Docker и Docker Compose
- Poetry (управление зависимостями)
- black, flake8, mypy (django-stubs)
- djangorestframework-simplejwt (JWT-авторизация)
- django-filter (фильтрация)
- drf-spectacular (документация API, Swagger/ReDoc)
- Stripe (приём платежей, тестовый режим)
- Celery и celery-beat (фоновые и периодические задачи)
- Redis (брокер сообщений для Celery)

## Установка и запуск

## Запуск через Docker Compose (рекомендуется)

Одной командой поднимаются все части проекта: приложение, база данных PostgreSQL, Redis, воркер Celery и планировщик celery-beat.

### Требования

- Docker Desktop (или Docker Engine с плагином Compose), он должен быть запущен.

### Первый запуск

1. Склонировать репозиторий и перейти в папку проекта.
2. Создать файл `.env` из примера и заполнить его своими значениями:

   ```bash
   cp .env.example .env
   ```

   Переменные:

   - `SECRET_KEY` — секретный ключ Django (в одинарных кавычках). Сгенерировать: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`;
   - `DEBUG` — `True` или `False`;
   - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — имя базы, пользователь и пароль PostgreSQL (придумайте свои, база создаётся с ними при первом запуске);
   - `POSTGRES_HOST`, `POSTGRES_PORT` — адрес базы при запуске без Docker (`localhost`, `5432`); внутри Compose хост подменяется на `db` автоматически;
   - `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` — адреса Redis (внутри Compose подменяются на `redis`);
   - `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL` — настройки почты (по умолчанию письма печатаются в логах воркера; для реальной отправки укажите SMTP-бэкенд и `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`);
   - `STRIPE_API_KEY` — тестовый секретный ключ Stripe (`sk_test_...`), `STRIPE_CURRENCY` — валюта платежей.

3. Собрать образ и запустить все сервисы:

   ```bash
   docker compose up --build
   ```

   (флаг `-d` запускает контейнеры в фоне: `docker compose up -d --build`). Миграции и загрузка группы модераторов выполняются автоматически при старте приложения.

4. Создать суперпользователя (в другом окне терминала):

   ```bash
   docker compose exec app python manage.py createsuperuser
   ```

### Сервисы

| Сервис | Назначение | Доступ |
|---|---|---|
| `app` | Django-приложение (API) | http://127.0.0.1:8000 |
| `db` | PostgreSQL 17 | `localhost:5432` (только с вашего компьютера, например для pgAdmin) |
| `redis` | брокер сообщений Celery | только внутри сети Compose (`expose`) |
| `celery_worker` | выполнение фоновых задач | — |
| `celery_beat` | периодические задачи | — |

Адреса приложения:

- API и админка: http://127.0.0.1:8000/admin/
- Swagger UI: http://127.0.0.1:8000/api/docs/swagger/
- ReDoc: http://127.0.0.1:8000/api/docs/redoc/

### Сохранность данных

Данные хранятся в именованных томах Docker: `postgres_data` (база), `redis_data` (Redis), `media_data` (загруженные файлы). Они сохраняются при остановке и пересоздании контейнеров.

### Полезные команды

```bash
docker compose ps                        # состояние сервисов
docker compose logs -f app               # логи приложения (аналогично celery_worker, celery_beat, db)
docker compose exec app python manage.py test   # запуск тестов в контейнере
docker compose down                      # остановить и удалить контейнеры (данные сохраняются)
docker compose down -v                   # то же, но вместе с данными (чистая база)
```

Если после смены `POSTGRES_PASSWORD` в `.env` приложение не подключается к базе, выполните `docker compose down -v` и запустите заново (пароль применяется только при создании базы).

### Подключение к базе через pgAdmin

В pgAdmin: Servers → Register → Server. На вкладке Connection: Host `localhost`, Port `5432`, Maintenance database, Username и Password из `.env` (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`). Порт 5432 на компьютере не должен быть занят другой установленной PostgreSQL.

## Запуск без Docker

Нужны Python 3.14, Poetry, запущенные локально PostgreSQL и Redis.

1. `poetry install`
2. Создать `.env` из `.env.example` (`POSTGRES_HOST=localhost`, адреса Redis с `localhost`).
3. Применить миграции и загрузить группу модераторов:

   ```bash
   poetry run python manage.py migrate
   poetry run python manage.py loaddata groups
   ```

4. Создать суперпользователя и запустить сервер:

   ```bash
   poetry run python manage.py createsuperuser
   poetry run python manage.py runserver
   ```

5. В отдельных терминалах запустить воркер и планировщик:

   ```bash
   poetry run celery -A config worker -l info -P solo
   poetry run celery -A config beat -l info
   ```

## Авторизация

Все эндпоинты, кроме регистрации и получения токенов, требуют JWT-токен. Передавайте его в заголовке:

```
Authorization: Bearer <access-токен>
```

1. Зарегистрироваться: `POST /users/register/` с телом `{"email": "...", "password": "..."}`.
2. Получить токены: `POST /users/token/` с теми же данными, в ответе `access` и `refresh`.
3. Обновить access-токен: `POST /users/token/refresh/` с телом `{"refresh": "<refresh-токен>"}`.

Время жизни access-токена — 30 минут, refresh — 1 день.

## Эндпоинты

| Метод | URL | Описание | Доступ |
|---|---|---|---|
| POST | `/users/register/` | регистрация | все |
| POST | `/users/token/` | получить пару токенов | все |
| POST | `/users/token/refresh/` | обновить access-токен | все |
| GET | `/users/` | список пользователей (общая информация) | авторизованные |
| GET | `/users/<id>/` | профиль (свой — полный, чужой — общая информация) | авторизованные |
| PUT / PATCH | `/users/<id>/update/` | изменить профиль | только свой |
| DELETE | `/users/<id>/delete/` | удалить профиль | только свой |
| GET | `/users/payments/` | список платежей | авторизованные |
| GET | `/courses/` | список курсов | авторизованные |
| POST | `/courses/` | создать курс | не модераторы |
| GET | `/courses/<id>/` | получить курс | модератор или владелец |
| PUT / PATCH | `/courses/<id>/` | изменить курс | модератор или владелец |
| DELETE | `/courses/<id>/` | удалить курс | владелец, не модератор |
| GET | `/lessons/` | список уроков | авторизованные |
| POST | `/lessons/create/` | создать урок | не модераторы |
| GET | `/lessons/<id>/` | получить урок | модератор или владелец |
| PUT / PATCH | `/lessons/<id>/update/` | изменить урок | модератор или владелец |
| DELETE | `/lessons/<id>/delete/` | удалить урок | владелец, не модератор |
| POST | `/subscriptions/` | подписаться на курс или отписаться (тело: `{"course": <id>}`) | авторизованные |
| POST | `/users/payments/create/` | создать платёж и получить ссылку на оплату Stripe | авторизованные |
| GET | `/users/payments/<id>/status/` | проверить статус платежа в Stripe | владелец платежа |
| GET | `/api/docs/swagger/` | документация Swagger UI | все |
| GET | `/api/docs/redoc/` | документация ReDoc | все |

Список платежей поддерживает параметры: `?ordering=paid_at` или `?ordering=-paid_at`, `?course=<id>`, `?lesson=<id>`, `?method=cash|transfer`.

## Права доступа

Модераторы входят в группу `moders` (назначается через админку).

| Действие | Обычный пользователь | Модератор |
|---|---|---|
| Список курсов и уроков | только свои | все |
| Просмотр и изменение | только свои | любые |
| Создание | да (владельцем становится он) | нет |
| Удаление | только свои | нет |

В чужом профиле доступна только общая информация (без фамилии, пароля и истории платежей), редактировать можно только свой профиль.

## Валидация ссылок

В поле `video_url` урока допускаются только ссылки на `youtube.com`, а в описаниях курсов и уроков не должно быть ссылок на другие сайты. При нарушении API возвращает ошибку 400 с понятным текстом.

## Подписка на курс

`POST /subscriptions/` с телом `{"course": <id курса>}`: если подписки нет, она создаётся (`"Подписка добавлена"`), если есть, удаляется (`"Подписка удалена"`). В данных курса поле `is_subscribed` показывает, подписан ли текущий пользователь.

Пример запроса:

```http
POST /subscriptions/
Authorization: Bearer <access-токен>
Content-Type: application/json

{"course": 1}
```

Ответ, если подписки не было (она создана):

```json
{"message": "Подписка добавлена"}
```

Тот же запрос повторно (подписка удалена):

```json
{"message": "Подписка удалена"}
```

Ошибки: `400`, если не указано поле `course` (`{"error": "Не указан id курса (поле course)"}`), `404`, если курса с таким id нет, `401`, если токен не передан или недействителен.

## Пагинация

Списки курсов (`/courses/`) и уроков (`/lessons/`) выдаются постранично: по умолчанию 5 курсов и 10 уроков на странице. Параметры: `?page=<номер>` и `?page_size=<размер>` (максимум 50 для курсов и 100 для уроков). Формат ответа: `count`, `next`, `previous`, `results`.

Пример запроса: `GET /courses/?page=1&page_size=2`

```json
{
  "count": 7,
  "next": "http://127.0.0.1:8000/courses/?page=2&page_size=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "description": "Основы языка",
      "lessons_count": 1,
      "lessons": [
        {
          "id": 1,
          "description": "Введение",
          "video_url": "https://www.youtube.com/watch?v=abc",
          "title": "Первый урок",
          "preview": null,
          "course": 1,
          "owner": 2
        }
      ],
      "is_subscribed": false,
      "title": "Python для начинающих",
      "preview": null,
      "owner": 2
    }
  ]
}
```

Поля `count` (всего объектов), `next` и `previous` (ссылки на соседние страницы, `null`, если страницы нет) и `results` (объекты текущей страницы) одинаковы для курсов и уроков.

## Документация API

После запуска сервера документация доступна по адресам:

- Swagger UI: http://127.0.0.1:8000/api/docs/swagger/
- ReDoc: http://127.0.0.1:8000/api/docs/redoc/
- Схема OpenAPI: http://127.0.0.1:8000/api/schema/

В Swagger UI можно авторизоваться кнопкой **Authorize** (вставить `access`-токен) и отправлять запросы прямо из браузера. Для каждого эндпоинта описаны параметры, тело запроса, ответы и возможные ошибки.

## Оплата курсов через Stripe

У курса есть поле `price` (цена, задаётся владельцем курса или в админке). Оплата работает в тестовом режиме Stripe.

1. `POST /users/payments/create/` (нужен токен), тело запроса:

```json
   {"course": 1}
```

   Сервер создаёт в Stripe продукт, цену (сумма передаётся в копейках) и сессию оплаты, сохраняет платёж и возвращает данные платежа со ссылкой на оплату:

```json
   {
     "id": 5,
     "paid_at": "2026-10-22T10:15:00Z",
     "amount": "5000.00",
     "method": "transfer",
     "status": "unpaid",
     "stripe_product_id": "prod_...",
     "stripe_price_id": "price_...",
     "stripe_session_id": "cs_test_...",
     "payment_url": "https://checkout.stripe.com/c/pay/cs_test_...",
     "user": 2,
     "course": 1,
     "lesson": null
   }
```

2. Откройте `payment_url` в браузере и оплатите тестовой картой `4242 4242 4242 4242` (любая будущая дата, любой CVC).
3. `GET /users/payments/<id>/status/` запрашивает у Stripe статус сессии и обновляет поле `status` платежа (`unpaid` или `paid`).

Ошибки: `400`, если курс не найден или у курса не задана цена, `401`, если токен не передан, `404`, если платёж чужой или не существует, `502`, если Stripe вернул ошибку (текст ошибки в поле `error`).

## Фоновые задачи (Celery)

Celery настроен в `config/celery.py`, брокер и хранилище результатов Redis, настройки берутся из `.env`. Часовой пояс Celery (`CELERY_TIMEZONE`) совпадает с `TIME_ZONE` проекта.

### Рассылка об обновлении курса

Задача `materials.tasks.send_course_update_email` отправляет письмо каждому активному подписчику курса. Она вызывается из контроллеров после успешного обновления:

- при обновлении курса (`PUT`/`PATCH /courses/<id>/`);
- при обновлении любого урока курса (`PUT`/`PATCH /lessons/<id>/update/`), урок считается частью курса.

Уведомление отправляется только если курс не обновлялся более 4 часов (проверяется по полю `updated_at` курса), поэтому частые правки не засыпают подписчиков письмами.

По умолчанию используется консольный почтовый бэкенд: текст письма выводится в терминале воркера.

### Блокировка неактивных пользователей

Периодическая задача `users.tasks.block_inactive_users` запускается каждый день в 03:00 (расписание в `CELERY_BEAT_SCHEDULE` в `config/settings.py`). Она одним запросом блокирует (`is_active=False`) пользователей, которые не заходили более 30 дней по полю `last_login`, а также тех, кто зарегистрировался более 30 дней назад и ни разу не входил. Суперпользователи не блокируются. Поле `last_login` обновляется при получении JWT-токена.

Запустить задачу вручную:

```bash
poetry run python manage.py shell -c "from users.tasks import block_inactive_users; print(block_inactive_users.delay().get(timeout=10))"
```

## Тесты и покрытие

```bash
poetry run python manage.py test
poetry run coverage run manage.py test
poetry run coverage report
```

Тестам не нужен запущенный Redis: вызовы задач подменяются, письма проверяются через mail.outbox.
Результат проверки покрытия сохранён в файле `coverage.txt`.

## Структура проекта

- `config/` — настройки проекта и корневые маршруты
- `users/` — модель пользователя, сериализатор и контроллер профиля
- `materials/` — модели курса и урока, сериализаторы, контроллеры и маршруты
- `users/services.py` — сервисные функции для работы со Stripe
- `config/celery.py` — приложение Celery
- `materials/tasks.py`, `users/tasks.py` — Celery-задачи

## Проверка качества кода

```bash
poetry run black .
poetry run flake8
poetry run mypy .
```