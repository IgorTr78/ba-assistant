# BA Assistant — Backend

FastAPI-бэкенд для ИИ-ассистента бизнес-аналитика.

## Стек

| Компонент | Технология |
|-----------|------------|
| Framework | FastAPI + Uvicorn |
| ИИ (документы, требования, BPMN) | OpenAI GPT-4o |
| ИИ (изображения / скриншоты) | OpenAI GPT-4o Vision |
| ИИ (конкуренты) | Perplexity sonar-pro |
| БД + Storage | Supabase (PostgreSQL + S3) |
| Деплой | Railway |

## Структура проекта

```
backend/
├── app/
│   ├── main.py                  # Точка входа FastAPI
│   ├── core/
│   │   ├── config.py            # Настройки из .env
│   │   └── database.py          # Supabase клиент
│   ├── models/
│   │   └── schemas.py           # Pydantic модели
│   ├── agents/
│   │   ├── orchestrator.py      # Роутинг по агентам
│   │   ├── requirements_agent.py
│   │   ├── document_agent.py    # PDF/DOCX + Vision (фото)
│   │   ├── bpmn_agent.py        # Генерация BPMN XML
│   │   ├── competitor_agent.py  # Perplexity sonar-pro
│   │   └── entity_agent.py      # Сущности и источники
│   ├── api/
│   │   ├── chat.py              # POST /api/chat/message
│   │   ├── projects.py          # CRUD проектов
│   │   ├── sessions.py          # CRUD сессий
│   │   ├── files.py             # Загрузка файлов и фото
│   │   └── export.py            # Скачивание Word/PDF/.bpmn
│   └── services/
│       ├── file_processor.py    # Извлечение текста
│       ├── export_service.py    # Генерация документов
│       └── storage_service.py   # Supabase Storage + DB
├── migrations/
│   └── 001_initial.sql          # Все таблицы + RLS + векторный индекс
├── requirements.txt
├── railway.toml
└── .env.example
```

## Быстрый старт (локально)

### 1. Клонировать и установить зависимости

```bash
git clone https://github.com/your-org/ba-assistant.git
cd ba-assistant/backend

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
# Открыть .env и заполнить ключи
```

Где взять ключи:
- `OPENAI_API_KEY` → platform.openai.com → API keys
- `PERPLEXITY_API_KEY` → perplexity.ai → Settings → API
- `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` → supabase.com → проект → Settings → API

### 3. Применить миграции в Supabase

Открыть Supabase → SQL Editor → вставить содержимое `migrations/001_initial.sql` → Run.

Затем создать бакеты в Storage:
```sql
insert into storage.buckets (id, name, public) values ('project-files', 'project-files', false);
insert into storage.buckets (id, name, public) values ('exports', 'exports', false);
```

### 4. Запустить сервер

```bash
uvicorn app.main:app --reload --port 8000
```

API будет доступен на `http://localhost:8000`.
Swagger UI: `http://localhost:8000/docs`

## Деплой на Railway

### 1. Создать проект на Railway

```bash
# Установить Railway CLI
npm install -g @railway/cli
railway login
railway init
```

### 2. Добавить переменные окружения

В Railway dashboard → Variables → добавить все переменные из `.env.example`.

Или через CLI:
```bash
railway variables set OPENAI_API_KEY=sk-...
railway variables set PERPLEXITY_API_KEY=pplx-...
railway variables set SUPABASE_URL=https://...
railway variables set SUPABASE_SERVICE_KEY=eyJ...
railway variables set SUPABASE_ANON_KEY=eyJ...
railway variables set ALLOWED_ORIGINS='["https://your-frontend.vercel.app"]'
```

### 3. Задеплоить

```bash
railway up
```

Railway автоматически:
- определит Python-проект через `requirements.txt`
- прочитает `railway.toml` для команды запуска
- выдаст публичный URL вида `https://ba-assistant-backend.up.railway.app`

## API Endpoints

### Chat
| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/chat/message` | Отправить сообщение, получить ответ агента |
| GET | `/api/chat/history/{session_id}` | История сообщений сессии |

### Files
| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/files/upload` | Загрузить PDF/DOCX/BPMN/PNG/JPG |
| GET | `/api/files/{file_id}` | Метаданные файла |
| DELETE | `/api/files/{file_id}` | Удалить файл |

### Export
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/export/word/{project_id}` | Скачать BRD в Word |
| GET | `/api/export/pdf/{project_id}` | Скачать BRD в PDF |
| GET | `/api/export/bpmn/{project_id}` | Скачать схему в .bpmn |
| POST | `/api/export/` | Пакетный экспорт + временные ссылки |

### Projects & Sessions
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/projects/` | Список проектов |
| POST | `/api/projects/` | Создать проект |
| PATCH | `/api/projects/{id}` | Обновить проект |
| GET | `/api/projects/{id}/requirements` | Требования проекта |
| GET | `/api/projects/{id}/bpmn` | Последняя BPMN-схема |
| POST | `/api/sessions/` | Создать сессию |
| GET | `/api/sessions/project/{project_id}` | Сессии проекта |

## Пример запроса из фронтенда

### Загрузка фото экрана
```javascript
const form = new FormData();
form.append('file', imageFile);           // File object из input
form.append('project_id', projectId);
form.append('session_id', sessionId);

const res = await fetch('/api/files/upload', {
  method: 'POST',
  body: form,
});
const { id: imageId } = await res.json();
```

### Отправка сообщения с изображением
```javascript
const res = await fetch('/api/chat/message', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    session_id: sessionId,
    project_id: projectId,
    message: 'Проанализируй этот скриншот',
    image_ids: [imageId],   // ID из предыдущего шага
    file_ids: [],
  }),
});
const data = await res.json();
// data.content — ответ агента
// data.agent   — какой агент ответил
// data.bpmn_xml — XML если был запрос на схему
```

### Скачать Word
```javascript
window.open(`/api/export/word/${projectId}`, '_blank');
```

## Агенты и модели

| Агент | Модель | Когда запускается |
|-------|--------|-------------------|
| Оркестратор | GPT-4o | Каждый запрос — определяет маршрут |
| Анализ документов | GPT-4o | При загрузке PDF / DOCX / BPMN |
| Анализ изображений | GPT-4o Vision | При загрузке PNG / JPG / скриншота |
| Требования | GPT-4o | Описание процессов, формализация |
| BPMN | GPT-4o | Запрос на схему |
| Конкуренты | Perplexity sonar-pro | Упоминание конкурентов / рынка |
| Сущности | GPT-4o | Запрос на данные / интеграции |

## Что сделать после тестирования

- [ ] Подключить Supabase Auth (JWT-токены вместо заглушек `uuid4()`)
- [ ] Добавить RAG: векторизация документов через `text-embedding-3-small`
- [ ] Заменить Claude на GPT-4o для анализа больших документов (или оставить оба)
- [ ] Добавить rate limiting (slowapi)
- [ ] Написать тесты для агентов (pytest + httpx)
