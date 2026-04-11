import json
from openai import AsyncOpenAI
from app.core.config import settings
from app.models.schemas import OrchestratorResult, AgentName

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

ORCHESTRATOR_PROMPT = """Ты — оркестратор ИИ-ассистента для команды бизнес-аналитиков.
Твоя единственная задача — определить тип запроса и вернуть JSON с маршрутом.

КОНТЕКСТ ПРОЕКТА:
{project_name} — {project_description}

ДОСТУПНЫЕ АГЕНТЫ:
- "document_analyst"   — анализ загруженных PDF, DOCX, BPMN файлов
- "image_analyst"      — анализ загруженных фото и скриншотов (PNG, JPG)
- "requirements_agent" — формализация требований из чата, BRD, User Story
- "competitor_analyst" — поиск и анализ практик конкурентов из открытых источников
- "bpmn_agent"         — генерация или редактирование BPMN-схемы
- "entity_agent"       — выявление сущностей, параметров, источников данных
- "export_agent"       — генерация Word, PDF, .bpmn файлов для скачивания
- "clarification"      — запрос неясен, нужно уточнение

ПРАВИЛА:
- Загружен документ (file_ids не пуст) → "document_analyst"
- Загружено изображение (image_ids не пуст) → "image_analyst"
- Оба типа → оба агента, image_analyst первым
- Слова «конкурент», «рынок», «практика», «аналог» → "competitor_analyst"
- Слова «схема», «процесс», «нарисуй», «bpmn» → "bpmn_agent"
- Слова «скачай», «экспорт», «сохрани», «выгрузи» → "export_agent"
- Слова «сущность», «данные», «источник», «система» → "entity_agent"
- Описание процесса, задачи, хаотичный текст → "requirements_agent"

ФОРМАТ ОТВЕТА — строго валидный JSON, без пояснений и markdown:
{{
  "agents": ["agent_name"],
  "intent": "одно предложение о задаче",
  "priority_agent": "agent_name",
  "needs_clarification": false,
  "clarification_question": null
}}"""


async def run_orchestrator(
    message: str,
    project_name: str,
    project_description: str,
    has_files: bool = False,
    has_images: bool = False,
) -> OrchestratorResult:

    # Быстрый путь — если есть файлы/картинки, сразу маршрутизируем
    if has_images and has_files:
        return OrchestratorResult(
            agents=[AgentName.image_analyst, AgentName.document_analyst],
            intent="Анализ загруженных изображений и документов",
            priority_agent=AgentName.image_analyst,
        )
    if has_images:
        return OrchestratorResult(
            agents=[AgentName.image_analyst],
            intent="Анализ загруженного изображения",
            priority_agent=AgentName.image_analyst,
        )
    if has_files:
        return OrchestratorResult(
            agents=[AgentName.document_analyst],
            intent="Анализ загруженного документа",
            priority_agent=AgentName.document_analyst,
        )

    system = ORCHESTRATOR_PROMPT.format(
        project_name=project_name,
        project_description=project_description or "Описание не указано",
    )

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=300,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    return OrchestratorResult(
        agents=[AgentName(a) for a in data.get("agents", ["requirements_agent"])],
        intent=data.get("intent", ""),
        priority_agent=AgentName(data.get("priority_agent", "requirements_agent")),
        needs_clarification=data.get("needs_clarification", False),
        clarification_question=data.get("clarification_question"),
    )
