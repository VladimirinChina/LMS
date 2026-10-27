from drf_spectacular.utils import OpenApiResponse

BAD_REQUEST = OpenApiResponse(description="Ошибка валидации: в теле запроса некорректные данные")
UNAUTHORIZED = OpenApiResponse(description="Не авторизован: токен не передан, просрочен или недействителен")
FORBIDDEN = OpenApiResponse(description="Недостаточно прав для этого действия")
NOT_FOUND = OpenApiResponse(description="Объект не найден")
