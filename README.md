# 🧩 API Service

**Oracle API Service** — это веб-приложение на базе FastAPI с web-интерфейсом, позволяющее подключаться к различным базам данных (Oracle, PostgreSQL, ClickHouse), создавать API-запросы на SQL и тестировать их прямо из интерфейса. Идеально подходит для быстрой публикации SQL-запросов в виде REST API.

---

## 🚀 Возможности

- Авторизация и управление пользователями
- Поддержка Oracle (oracledb, cx_Oracle), PostgreSQL, ClickHouse
- Создание SQL API с параметрами
- Тестирование SQL-запросов в UI
- Docker-сборка и простой деплой
- Подсветка SQL при редактировании

---

## 🛠️ Требования

- Python 3.12+ (если запускать локально)
- Docker / Docker Compose (если запускать в контейнере)
- Oracle Instant Client (уже встроен в Docker-сборку)

---

## ⚙️ Установка

### Вариант 1: через Docker

git clone git@github.com:Vaadimv/api-service.git
cd api-service
docker compose up --build

Открой в браузере: http://localhost:8000

Логин: admin
Пароль: admin

## Вариант 2: локальный запуск
Клонируем проект
git clone git@github.com:Vaadimv/api-service.git
cd api-service

# Создаём виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Запускаем
uvicorn main:app --reload

📁 Структура проекта
```
.
├── app/                 # Маршруты (API, авторизация, управление)
├── static/              # CSS, иконки, логотип
├── templates/           # HTML-шаблоны (Jinja2)
├── database/api.db      # SQLite-база
├── Dockerfile
├── docker-compose.yml
├── main.py              # Точка входа в FastAPI
├── app_core.py          # Логика подключения и запросов
├── auth_utils.py        # Авторизация, токены
├── dynamic_routes.py    # Автоматическая регистрация API```


🔐 Админ-доступ по умолчанию
После первого запуска доступен админ:
Логин: admin
Пароль: admin
Кодовое слово: admin

🧪 Пример API-запроса
GET /api/clients?user_id=123
Authorization: Bearer <token>

📡 Пример запроса к API (POST)
Предположим, вы создали API-эндпоинт с именем get_clients с параметрами client_id и phone.

🔐 Авторизация:
Сначала получите Bearer Token на странице управления токенами (/manage-api-tokens).

📤 Запрос:
curl -X POST http://localhost:8000/api/get_clients \
     -H "Authorization: Bearer <ВАШ_ТОКЕН>" \
     -H "Content-Type: application/json" \
     -d '{"client_id": 12345, "phone": "+79998887766"}'

📥 Пример ответа:
[
  {
    "client_id": 12345,
    "name": "Иван Иванов",
    "phone": "+79998887766"
  }
]


👨‍💻 Автор
Разработано Vaadimv
Если проект вам помог — поставьте ⭐️
