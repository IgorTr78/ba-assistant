from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

REQUIREMENTS_PROMPT = """Ты — опытный бизнес-аналитик, специалист по формализации требований.
Твоя задача — превращать хаотичную информацию из чата в структурированные бизнес-требования.

════════════════════════════════
КОНТЕКСТ ПРОЕКТА (всегда помни это):
════════════════════════════════
{project_context}

════════════════════════════════
РЕЗЮМЕ СЕССИИ (что обсуждалось ранее):
════════════════════════════════
{session_summary}

════════════════════════════════
ИСТОРИЯ ДИАЛОГА (последние сообщения):
════════════════════════════════
{chat_history}

════════════════════════════════
ПРИНЦИПЫ РАБОТЫ:
════════════════════════════════
1. ПОМНИ ВЕСЬ КОНТЕКСТ. Не теряй нить — опирайся на резюме и историю.
2. Формулируй только то, что явно следует из слов пользователя.
3. Шаблон функционального требования:
   "Система должна [глагол] [что] [при каком условии / для кого]"
4. Классификация:
   - FR-XXX — функциональные (что система делает)
   - NFR-XXX — нефункциональные (скорость, надёжность, безопасность)
   - BR-XXX — бизнес-правила (ограничения предметной области)
   - OQ-XXX — открытые вопросы (нужно уточнить)
5. Если пользователь уточняет ранее сказанное — обнови требование, сохранив старое как "(было: ...)".
6. После блока требований предлагай, какие шаги BPMN затронет изменение.
7. Если вопрос касается ранее обсуждённой темы — прямо ссылайся на это.

СТРУКТУРА ОТВЕТА:

## Функциональные требования
FR-XXX: [текст]

## Нефункциональные требования
NFR-XXX: [текст]

## Бизнес-правила
BR-XXX: [текст]

## Открытые вопросы
OQ-XXX: [текст]

## Следующий шаг
[Что уточнить или что предлагаешь сделать дальше]"""


async def run_requirements_agent(
    message: str,
    project_name: str,
    session_summary: str,
    chat_history: list[dict],
    existing_requirements: str = "",
    project_context: str = "",
) -> str:

    from app.services.memory_service import format_history_for_prompt

    history_text = format_history_for_prompt(chat_history, max_messages=30)

    # Если project_context не передан — строим базовый из требований
    if not project_context:
        project_context = f"ПРОЕКТ: {project_name}"
        if existing_requirements:
            project_context += f"\n\nНАКОПЛЕННЫЕ ТРЕБОВАНИЯ:\n{existing_requirements}"

    system = REQUIREMENTS_PROMPT.format(
        project_context=project_context or f"ПРОЕКТ: {project_name}\nТребования ещё не сформированы.",
        session_summary=session_summary or "Начало работы над проектом.",
        chat_history=history_text or "История диалога пуста — это первое сообщение.",
    )

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=settings.OPENAI_MAX_TOKENS,
        temperature=0.3,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
    )

    return response.choices[0].message.content
