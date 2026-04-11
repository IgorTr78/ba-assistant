import base64
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# ─────────────────────────────────────────
# DOCUMENT ANALYST
# ─────────────────────────────────────────

DOCUMENT_PROMPT = """Ты — аналитик документов в команде бизнес-аналитиков.
Извлеки структурированную информацию из загруженного документа.

ТИП ДОКУМЕНТА: {file_type}
ИМЯ ФАЙЛА: {filename}
ПРОЕКТ: {project_name}

ИНСТРУКЦИЯ:

Для нормативных документов (законы, регламенты, стандарты):
1. Определи тип и область применения
2. Выдели ключевые требования, обязательства, ограничения
3. Найди сроки, пороговые значения, условия
4. Отметь, что влияет на разрабатываемую систему
5. Зафикисруй неоднозначные места

Для BPMN-схем (.bpmn, .xml):
1. Опиши процесс своими словами — участники, шаги, развилки
2. Найди точки входа и выхода
3. Выяви узкие места и отсутствующие обработчики ошибок
4. Перечисли все сущности и данные
5. Предложи улучшения

Для технических заданий и требований (DOCX):
1. Извлеки функциональные требования списком
2. Извлеки нефункциональные требования
3. Определи заинтересованные стороны
4. Найди противоречия или пробелы
5. Составь вопросы к заказчику

ФОРМАТ: Markdown, заголовки, списки. В конце — раздел "Вопросы и неясности".
ВАЖНО: Не придумывай то, чего нет в документе."""

IMAGE_PROMPT = """Ты — аналитик бизнес-процессов. Тебе прислали фотографию или скриншот экрана.
Твоя задача — извлечь максимум полезной информации для формирования требований.

ПРОЕКТ: {project_name}
КОЛИЧЕСТВО ИЗОБРАЖЕНИЙ: {image_count}

ИНСТРУКЦИЯ:
1. ОПИШИ, что изображено (интерфейс, схема, таблица, документ, доска, схема на бумаге)
2. ИЗВЛЕКИ всю текстовую информацию, которую можно прочитать
3. ВЫЯВИ элементы процесса:
   - Шаги и этапы (если есть схема или список)
   - Роли и участников
   - Данные и поля (если это форма или таблица)
   - Статусы и состояния
   - Переходы и условия
4. СФОРМУЛИРУЙ предварительные требования на основе увиденного
5. ЗАДАЙ уточняющие вопросы — это AS-IS или TO-BE? Это черновик или утверждённая схема?

СТРУКТУРА ОТВЕТА:

## Что на изображении
[краткое описание]

## Извлечённые данные
[всё, что прочитано/увидено]

## Предварительные требования
FR-XXX: [текст]
OQ-XXX: [вопрос]

## Вопросы для уточнения
[список вопросов]"""


async def run_document_analyst(
    extracted_text: str,
    filename: str,
    file_type: str,
    project_name: str,
) -> str:

    system = DOCUMENT_PROMPT.format(
        file_type=file_type,
        filename=filename,
        project_name=project_name,
    )

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=settings.OPENAI_MAX_TOKENS,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Содержимое документа:\n\n{extracted_text}"},
        ],
    )

    return response.choices[0].message.content


async def run_image_analyst(
    images: list[dict],   # [{"base64": "...", "media_type": "image/jpeg", "filename": "..."}]
    project_name: str,
    additional_context: str = "",
) -> str:
    """
    Анализирует изображения через GPT-4o Vision.
    images — список словарей с base64-данными.
    """
    system = IMAGE_PROMPT.format(
        project_name=project_name,
        image_count=len(images),
    )

    # Строим content с несколькими изображениями
    content = []
    if additional_context:
        content.append({"type": "text", "text": additional_context})

    for img in images:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{img['media_type']};base64,{img['base64']}",
                "detail": "high",   # high detail для чтения текста
            },
        })

    content.append({
        "type": "text",
        "text": "Проанализируй изображение(я) согласно инструкции."
    })

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,   # GPT-4o поддерживает vision
        max_tokens=settings.OPENAI_MAX_TOKENS,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": content},
        ],
    )

    return response.choices[0].message.content


def encode_image_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")
