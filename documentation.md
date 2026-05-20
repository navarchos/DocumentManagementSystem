# Система электронного документооборота (ЭДО ЛДПР)

Веб-приложение для управления распоряжениями и документами организации. Построено на Flask с поддержкой PostgreSQL/SQLite в качестве базы данных, Yandex Object Storage для хранения файлов и интегрированным RAG-ассистентом на базе YandexGPT.

---

## Содержание

1. [Обзор архитектуры](#1-обзор-архитектуры)
2. [Требования](#2-требования)
3. [Установка и запуск](#3-установка-и-запуск)
4. [Конфигурация (.env)](#4-конфигурация-env)
5. [Роли пользователей](#5-роли-пользователей)
6. [Жизненный цикл распоряжения](#6-жизненный-цикл-распоряжения)
7. [RAG-ассистент](#7-rag-ассистент)
8. [Хранение файлов](#8-хранение-файлов)
9. [CLI-команды](#9-cli-команды)
10. [Структура проекта](#10-структура-проекта)
11. [Модели данных](#11-модели-данных)
12. [Маршруты (API)](#12-маршруты-api)
13. [Тестирование](#13-тестирование)

---

## 1. Обзор архитектуры

```
┌─────────────────────────────────────────────┐
│                  Flask App                   │
│  ┌──────────┐  ┌────────────┐  ┌─────────┐  │
│  │  Routes  │  │  Services  │  │  RAG    │  │
│  │ (views)  │  │ (business  │  │ module  │  │
│  └────┬─────┘  │   logic)   │  └────┬────┘  │
│       │        └─────┬──────┘       │        │
│  ┌────▼──────────────▼──────────────▼────┐  │
│  │              SQLAlchemy ORM            │  │
│  └────────────────────┬──────────────────┘  │
└───────────────────────┼──────────────────────┘
                        │
          ┌─────────────┴────────────┐
          │                          │
   ┌──────▼──────┐          ┌────────▼──────┐
   │  PostgreSQL  │          │    SQLite     │
   │  + pgvector  │          │  (fallback)   │
   └─────────────┘          └───────────────┘
```

Приложение при старте автоматически определяет доступность PostgreSQL. Если подключение успешно — используется PostgreSQL (с поддержкой векторного поиска через `pgvector`). В противном случае приложение переключается на локальную SQLite-базу.

---

## 2. Требования

- Python 3.10+
- PostgreSQL 14+ с расширением `pgvector` (опционально, для полного функционала RAG)
- Аккаунт Yandex Cloud (опционально, для RAG-ассистента и S3-хранилища файлов)

Зависимости Python:

| Пакет | Назначение |
|---|---|
| Flask | Веб-фреймворк |
| Flask-SQLAlchemy | ORM |
| Flask-Migrate | Миграции БД (Alembic) |
| Werkzeug | Хеширование паролей, утилиты |
| python-dotenv | Загрузка `.env` |
| psycopg2-binary | Драйвер PostgreSQL |
| pgvector | Векторные типы для PostgreSQL |
| boto3 | Клиент S3 (Yandex Object Storage) |
| httpx | HTTP-клиент для Yandex API |
| tenacity | Retry-логика для API-запросов |
| pypdf | Извлечение текста из PDF |
| python-docx | Извлечение текста из DOCX |
| pandas + openpyxl | Экспорт распоряжений в Excel |
| gunicorn | WSGI-сервер для продакшна |

---

## 3. Установка и запуск

### 3.1 Локальная разработка (SQLite)

```powershell
# Клонировать репозиторий и перейти в папку проекта
cd DocumentManagementSystem

# Создать и активировать виртуальное окружение
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Установить зависимости
pip install -r requirements.txt

# Запустить приложение
python app.py
```

При первом запуске без `DATABASE_URL` автоматически создаётся `instance/edo_ldpr.db` и наполняется базовыми отделами и пользователями.

### 3.2 С PostgreSQL

```powershell
# Создать .env файл (см. раздел 4)
# Применить миграции
$env:FLASK_APP = "app.py"
flask db upgrade

# Заполнить начальные данные
flask seed-db

# Запустить
python app.py
```

### 3.3 Продакшн (gunicorn)

```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### 3.4 Тестовые учётные записи (seed-данные)

После выполнения `flask seed-db` доступны следующие пользователи:

| Логин | Пароль | Роль |
|---|---|---|
| `admin` | `admin123` | Администратор |
| `secretary` | `sec123` | Секретарь |
| `head_central` | `head123` | Руководитель ЦА |
| `head_department` | `head123` | Начальник отдела |
| `assistant` | `ast123` | Помощник/секретарь |
| `executor` | `exec123` | Исполнитель |

---

## 4. Конфигурация (.env)

Создайте файл `.env` в корне проекта:

```dotenv
# ── Основные настройки ──────────────────────────────────────────────────────
SECRET_KEY=your-random-secret-key-here
FLASK_DEBUG=False
PORT=5000

# ── База данных ──────────────────────────────────────────────────────────────
# Если не указан — используется SQLite (instance/edo_ldpr.db)
DATABASE_URL=postgresql://edo_user:password@localhost:5432/edo_ldpr

# ── Yandex Object Storage (S3) ───────────────────────────────────────────────
# Если не указан — загрузка файлов недоступна
S3_BUCKET_NAME=your-bucket-name
S3_ENDPOINT_URL=https://storage.yandexcloud.net
S3_REGION=ru-central1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key

# ── Yandex AI (для RAG-ассистента) ──────────────────────────────────────────
# Требуется PostgreSQL + pgvector
YANDEX_API_KEY=your-yandex-api-key
YANDEX_FOLDER_ID=your-folder-id

# Опционально: переопределение URI моделей
# YANDEX_EMBED_DOC_URI=emb://<folder_id>/text-search-doc/latest
# YANDEX_EMBED_QUERY_URI=emb://<folder_id>/text-search-query/latest
# YANDEX_LLM_URI=gpt://<folder_id>/yandexgpt-lite/latest
# YANDEX_API_BASE=https://llm.api.cloud.yandex.net/foundationModels/v1

# ── Параметры RAG ────────────────────────────────────────────────────────────
RAG_EMBEDDING_DIM=256         # Размерность векторов эмбеддингов
RAG_TOP_K=6                   # Количество чанков, возвращаемых при поиске
RAG_CHUNK_TOKENS=800          # Размер чанка в токенах
RAG_CHUNK_OVERLAP=100         # Перекрытие чанков в токенах
RAG_MAX_PROMPT_CHARS=20000    # Максимальный размер контекста для LLM
RAG_LLM_TEMPERATURE=0.2       # Температура генерации (0.0–1.0)
RAG_INDEX_CONCURRENCY=2       # Параллельность индексирования
```

---

## 5. Роли пользователей

| Роль | Код | Описание |
|---|---|---|
| Администратор | `admin` | Управление пользователями и отделами. Нет доступа к распоряжениям. |
| Помощник | `assistant` | Создаёт распоряжения и отправляет их на утверждение. |
| Руководитель ЦА | `head_central` | Утверждает или отклоняет распоряжения, закрывает выполненные. |
| Секретарь | `secretary` | Назначает утверждённые распоряжения в отделы. |
| Начальник отдела | `head_department` | Назначает исполнителей, принимает или возвращает выполненную работу. |
| Исполнитель | `executor` | Принимает распоряжение в работу и сдаёт результат. |

---

## 6. Жизненный цикл распоряжения

```
[Помощник]
    │  Создать
    ▼
Черновик ──────────────────────────────────────────────────────────────────┐
    │  Отправить на утверждение                                             │
    ▼                                                                       │
На утверждении ◄── Отозвано (Помощник)                                      │
    │                                                                       │
    ├── [Руководитель ЦА] Утвердить ──────────────────────────────────────┐ │
    └── [Руководитель ЦА] Отклонить → Отклонено                           │ │
                                                                           │ │
                                                                     Утверждено
                                                                           │
                                                             [Секретарь] Назначить отдел
                                                                           │
                                                                       В отделе
                                                                           │
                                                      [Начальник отдела] Назначить исполнителя
                                                                           │
                                                                  Назначен исполнитель
                                                                           │
                                                              [Исполнитель] Взять в работу
                                                                           │
                                                                       В работе
                                                                           │
                                                           [Исполнитель] Сдать результат
                                                                           │
                                                                  Готово к проверке
                                                                           │
                                                      ┌────────────────────┤
                                                      │                    │
                                          [Нач. отдела]          [Нач. отдела]
                                          Подтвердить              Отправить на доработку / Отклонить
                                                      │                    │
                                                 Подтверждено         На доработке ──► В работе
                                                      │
                                         [Рук. ЦА] Закрыть / На доработке
                                                      │
                                                   Закрыто
```

Каждое изменение статуса:
- записывается в историю распоряжения (`OrderHistory`);
- автоматически рассылает уведомления причастным участникам;
- запускает фоновую переиндексацию в RAG (если RAG активен).

---

## 7. RAG-ассистент

RAG-функционал позволяет пользователям задавать вопросы по своим распоряжениям на естественном языке. Ассистент использует YandexGPT и семантический поиск по векторной базе данных.

### Требования для активации RAG

- PostgreSQL с установленным расширением `pgvector`
- Заполненные переменные `YANDEX_API_KEY` и `YANDEX_FOLDER_ID`

Если хотя бы одно условие не выполнено, чат-интерфейс отображается с предупреждением о недоступности ИИ-функций.

### Принцип работы

1. **Индексирование**: при создании/изменении распоряжения или загрузке файла в фоновом потоке запускается индексирование:
   - Текст распоряжения (`order_content`)
   - История изменений (`order_history`)
   - Содержимое прикреплённых файлов PDF и DOCX (`order_file`)
   
   Каждый источник разбивается на чанки (по ~800 токенов с перекрытием ~100), для каждого чанка получается эмбеддинг через Yandex Text Embeddings API и сохраняется в `pgvector`.

2. **Поиск**: при получении вопроса от пользователя:
   - Вопрос преобразуется в вектор (`text-search-query`)
   - Производится косинусный поиск по `rag_chunks`, ограниченный распоряжениями, доступными текущему пользователю
   - Возвращаются топ-K наиболее релевантных чанков

3. **Генерация ответа**: найденные чанки передаются как контекст в YandexGPT вместе с историей диалога (последние 6 пар). Ответ возвращается пользователю с указанием источников.

### Источники данных в индексе

| Тип (`source_type`) | Что индексируется |
|---|---|
| `order_content` | Заголовок, содержание, статус, приоритет, дедлайн |
| `order_history` | История изменений статусов и комментарии |
| `order_file` | Текст из прикреплённых PDF и DOCX файлов |

---

## 8. Хранение файлов

Поддерживается хранение в **Yandex Object Storage** (S3-совместимый). Если переменные `S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID` и `AWS_SECRET_ACCESS_KEY` не заданы, загрузка файлов недоступна.

Разрешённые форматы: `pdf`, `doc`, `docx`, `xls`, `xlsx`, `txt`, `jpg`, `png`, `zip`.

Максимальный размер файла: **16 МБ**.

Путь к файлу в бакете формируется как `orders/<order_id>/<uuid>.<ext>`.

---

## 9. CLI-команды

Все команды запускаются через `flask <command>` при установленном `FLASK_APP=app.py`.

```powershell
# Заполнить базу начальными данными (отделы, пользователи, демо-распоряжения)
flask seed-db

# Принудительно пересоздать демо-распоряжения
flask seed-db --force

# Проиндексировать все распоряжения в векторную БД
flask rag-reindex-all

# Проиндексировать одно распоряжение
flask rag-reindex-order <order_id>

# Проверить подключение к Yandex API
flask rag-test
flask rag-test --text "Ваш тестовый запрос"

# Применить миграции базы данных
flask db upgrade

# Создать новую миграцию (после изменения моделей)
flask db migrate -m "описание изменений"
```

---

## 10. Структура проекта

```
DocumentManagementSystem/
├── app.py                        # Точка входа, конфигурация Flask
├── requirements.txt              # Зависимости Python
├── runtime.txt                   # Версия Python (для деплоя)
├── .env                          # Переменные окружения (не в git)
│
├── application/
│   ├── __init__.py
│   ├── models.py                 # SQLAlchemy-модели
│   ├── database.py               # Начальное наполнение БД (seed)
│   ├── decorators.py             # login_required, role_required
│   ├── services.py               # Бизнес-логика (фильтрация по ролям)
│   ├── file_utils.py             # Работа с S3-хранилищем
│   ├── notifications_utils.py    # Создание уведомлений
│   ├── context.py                # Контекстные процессоры Jinja2
│   ├── seed_demo.py              # Демо-данные для seed-db
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── client.py             # HTTP-клиент Yandex AI API
│   │   ├── chunker.py            # Разбивка текста на чанки
│   │   ├── extractors.py         # Извлечение текста из PDF/DOCX
│   │   ├── indexer.py            # Индексирование в pgvector
│   │   ├── retriever.py          # Семантический поиск
│   │   └── chat.py               # Оркестрация диалога с LLM
│   │
│   └── routes/
│       ├── __init__.py
│       ├── auth.py               # Вход / выход
│       ├── dashboard.py          # Главная страница
│       ├── orders.py             # CRUD распоряжений, файлы
│       ├── departments.py        # Просмотр отделов
│       ├── notifications.py      # Уведомления
│       ├── admin.py              # Управление пользователями
│       └── chat.py               # RAG-чат
│
├── templates/                    # Jinja2-шаблоны
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── orders.html
│   ├── order_details.html
│   ├── department.html
│   ├── notifications.html
│   ├── chat.html
│   ├── admin.html
│   └── admin_departments.html
│
├── static/                       # Статические файлы (изображения)
├── docs/                         # Техническая документация
│   └── postgresql.md
├── seed_data/                    # Файлы для демо-данных
│   └── files/
└── instance/                     # Локальная SQLite-база (в .gitignore)
    └── edo_ldpr.db
```

---

## 11. Модели данных

### Department — Отдел
| Поле | Тип | Описание |
|---|---|---|
| `id` | String (PK) | Идентификатор отдела |
| `name` | String(200) | Название отдела |
| `head_id` | String | ID руководителя отдела (FK → User) |

### User — Пользователь
| Поле | Тип | Описание |
|---|---|---|
| `uid` | String (PK) | Уникальный идентификатор |
| `full_name` | String(200) | Полное имя |
| `email` | String(200) | Email (уникальный) |
| `username` | String(100) | Логин (уникальный) |
| `password` | String(200) | Хеш пароля (Werkzeug) |
| `role` | String(50) | Роль (см. раздел 5) |
| `department_id` | String | ID отдела (FK → Department) |
| `created_at` | DateTime | Дата создания |

### Order — Распоряжение
| Поле | Тип | Описание |
|---|---|---|
| `id` | String (PK) | `ord-` + 8 символов UUID |
| `title` | String(500) | Заголовок |
| `content` | Text | Содержание |
| `priority` | String(50) | Приоритет: Низкий / Нормальный / Высокий / Срочный |
| `status` | String(100) | Текущий статус (см. раздел 6) |
| `created_by` | String | ID автора (FK → User) |
| `creator_name` | String(200) | Имя автора (денормализовано) |
| `assigned_department_id` | String | ID назначенного отдела |
| `assigned_executor_id` | String | ID назначенного исполнителя |
| `deadline` | Date | Срок выполнения |
| `result` | JSON | Список сдач работы (массив объектов) |
| `revision_count` | Integer | Количество доработок |
| `created_at` / `updated_at` | DateTime | Временны́е метки |

### OrderHistory — История распоряжения
| Поле | Тип | Описание |
|---|---|---|
| `id` | Integer (PK) | Автоинкремент |
| `order_id` | String | FK → Order |
| `action` | String(200) | Тип действия |
| `user_name` | String(200) | Имя пользователя |
| `user_role` | String(50) | Роль пользователя |
| `details` | Text | Подробности |
| `created_at` | DateTime | Время события |

### OrderFile — Файл распоряжения
| Поле | Тип | Описание |
|---|---|---|
| `id` | Integer (PK) | Автоинкремент |
| `order_id` | String | FK → Order |
| `filename` | String(200) | UUID-имя файла в хранилище |
| `original_name` | String(200) | Оригинальное имя файла |
| `filepath` | String(500) | Путь в S3 (`orders/<id>/<uuid>.<ext>`) |
| `uploaded_by` | String | ID загрузившего пользователя |
| `created_at` | DateTime | Время загрузки |

### Notification — Уведомление
| Поле | Тип | Описание |
|---|---|---|
| `id` | Integer (PK) | Автоинкремент |
| `user_id` | String | ID адресата |
| `message` | String(500) | Текст уведомления |
| `link` | String(200) | Ссылка (опционально) |
| `is_read` | Boolean | Прочитано ли |
| `created_at` | DateTime | Время создания |

### Comment — Комментарий
| Поле | Тип | Описание |
|---|---|---|
| `id` | Integer (PK) | Автоинкремент |
| `order_id` | String | FK → Order |
| `user_name` | String(200) | Автор комментария |
| `user_role` | String(50) | Роль автора |
| `text` | Text | Текст комментария |
| `created_at` | DateTime | Время создания |

### RagDocument / RagChunk — Векторный индекс
Используются только при активном RAG (PostgreSQL + pgvector).

`RagDocument` — метаданные об индексированном источнике (распоряжение, история, файл).  
`RagChunk` — отдельный фрагмент текста с вектором эмбеддинга (`pgvector`).

### ChatSession / ChatMessage — История чатов
Сессии и сообщения RAG-чата. Источники ответа хранятся в поле `sources` (JSON) у `ChatMessage`.

---

## 12. Маршруты (API)

### Аутентификация

| Метод | URL | Описание | Роли |
|---|---|---|---|
| GET/POST | `/login` | Форма входа | — |
| GET | `/logout` | Выход из системы | Любая |

### Главная страница

| Метод | URL | Описание | Роли |
|---|---|---|---|
| GET | `/` | Дашборд (сводная статистика) | Любая |

### Распоряжения

| Метод | URL | Описание | Роли |
|---|---|---|---|
| GET | `/orders` | Список распоряжений с фильтрами | Любая |
| GET | `/orders/export` | Экспорт в Excel | Любая |
| POST | `/orders/create` | Создать распоряжение | `assistant` |
| GET | `/orders/<id>` | Детали распоряжения | Любая |
| POST | `/orders/<id>/status` | Изменить статус | По роли |
| POST | `/orders/<id>/submit` | Сдать результат | `executor` |
| POST | `/orders/<id>/comment` | Добавить комментарий | Любая |
| POST | `/orders/<id>/upload` | Загрузить файл | Любая |
| POST | `/orders/<id>/delete` | Удалить распоряжение | `head_central` |
| GET | `/orders/file/<id>/download` | Скачать файл | Любая |

### Отделы

| Метод | URL | Описание | Роли |
|---|---|---|---|
| GET | `/departments` | Список отделов | Любая |
| GET | `/departments/<id>` | Детали отдела | Любая |

### Уведомления

| Метод | URL | Описание | Роли |
|---|---|---|---|
| GET | `/notifications` | Список уведомлений | Любая |
| POST | `/notifications/<id>/read` | Пометить прочитанным | Любая |
| POST | `/notifications/read-all` | Пометить все прочитанными | Любая |

### RAG-чат

| Метод | URL | Описание | Роли |
|---|---|---|---|
| GET | `/chat` | Интерфейс чата | Любая |
| POST | `/chat/send` | Отправить сообщение (JSON API) | Любая |
| GET | `/chat/sessions` | Список сессий (JSON) | Любая |
| GET | `/chat/sessions/<id>` | История сессии (JSON) | Любая |
| POST | `/chat/sessions/<id>/delete` | Удалить сессию | Любая |

### Администрирование

| Метод | URL | Описание | Роли |
|---|---|---|---|
| GET | `/admin` | Панель управления | `admin` |
| POST | `/admin/users/create` | Создать пользователя | `admin` |
| POST | `/admin/users/<uid>/edit` | Редактировать пользователя | `admin` |
| POST | `/admin/users/<uid>/delete` | Удалить пользователя | `admin` |
| POST | `/admin/departments/create` | Создать отдел | `admin` |
| POST | `/admin/departments/<id>/edit` | Редактировать отдел | `admin` |
| POST | `/admin/departments/<id>/delete` | Удалить отдел | `admin` |

---

## 13. Тестирование

Проект покрыт автоматическими тестами на базе **pytest**. Тесты расположены в папке `tests/` и не требуют запущенной базы данных PostgreSQL или доступа к внешним сервисам — для изоляции используется SQLite в памяти.

### Зависимости

```bash
pip install pytest pytest-flask
```

### Запуск тестов

```bash
# Запустить все тесты
python -m pytest tests/ -v

# Запустить конкретный файл
python -m pytest tests/test_rag_chunker.py -v

# Запустить конкретный тест
python -m pytest tests/test_auth_routes.py::TestLoginPost::test_valid_credentials_redirect_to_dashboard -v
```

### Структура тестов

```
tests/
├── conftest.py               # Фикстуры: Flask-приложение, SQLite в памяти, тестовый клиент
├── test_models.py            # SQLAlchemy-модели (Department, User, Order, ...)
├── test_file_utils.py        # Утилиты работы с файлами и S3
├── test_decorators.py        # Декораторы login_required, role_required
├── test_services.py          # Бизнес-логика: фильтрация распоряжений, статистика
├── test_rag_chunker.py       # RAG: разбивка текста на чанки
├── test_rag_extractors.py    # RAG: извлечение текста из документов
├── test_notifications.py     # Создание и подсчёт уведомлений
├── test_auth_routes.py       # Маршруты /login, /logout
└── test_database.py          # Начальное заполнение базы (seed)
```

### Описание тестовых модулей

| Файл | Что тестируется | Кол-во тестов |
|---|---|---|
| `test_models.py` | Создание записей, ограничения уникальности, значения по умолчанию | 11 |
| `test_file_utils.py` | `allowed_file()`, `build_storage_path()`, `is_s3_storage_path()`, `is_s3_storage_enabled()` | 14 |
| `test_decorators.py` | Редирект неаутентифицированных пользователей, проверка ролей, сохранение имени функции | 6 |
| `test_services.py` | `get_orders_for_user()` по всем ролям, `get_stats()`, `get_overdue_orders()` | 7 |
| `test_rag_chunker.py` | `chunk_text()`, `_split_paragraphs()`, `_split_sentences()`, перекрытие чанков, русский текст | 22 |
| `test_rag_extractors.py` | `extract_order_content()`, `extract_order_history()`, `_extract_txt()`, работа без S3 | 18 |
| `test_notifications.py` | `create_notification()`, `get_unread_count()`, изоляция прочитанных уведомлений | 6 |
| `test_auth_routes.py` | GET/POST `/login`, `/logout`, все сид-пользователи, управление сессией | 10 |
| `test_database.py` | Корректность начальных данных, хэширование паролей, идемпотентность `seed_initial_data()` | 6 |
| **Итого** | | **105** |

### Принципы изоляции

- **База данных.** Фикстура `app` (scope=`session`) создаёт отдельный движок SQLite в памяти (`sqlite:///:memory:`). Перед каждой тестовой сессией вызываются `db.drop_all()` + `db.create_all()` — это гарантирует актуальность схемы даже при наличии файла `instance/edo_ldpr.db` со старой структурой.
- **Аутентификация.** Фикстура `auth_client` напрямую заполняет Flask-сессию, минуя форму входа, что позволяет тестировать защищённые маршруты без дублирования логики.
- **Внешние сервисы.** S3 (`S3_BUCKET_NAME=None`) и Yandex API не задействуются — соответствующие пути кода возвращают `None` или `RuntimeError`, которые тесты явно проверяют.
- **Чистота данных.** Тесты, изменяющие БД, откатывают транзакцию (`db.session.rollback()`) или удаляют созданные записи в teardown-блоке фикстуры.
