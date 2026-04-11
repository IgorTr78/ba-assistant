from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

REQUIREMENTS_PROMPT = """Ты — опытный бизнес-аналитик, специалист по формализации требований.
Твоя задача — превращать хаотичную информацию из чата в структурированные бизнес-требования.

ПРОЕКТ: {project_name}
КОНТЕКСТ СЕССИИ: {session_summary}

НАКОПЛЕННЫЕ ТРЕБОВАНИЯ (текущая версия):
{existing_requirements}

ПРИНЦИПЫ:
1. Формулируй только то, что явно следует из слов пользователя. Не домысливай.
2. Шаблон функционального требования:
   "Система должна [глагол] [что] [при каком условии / для кого]"
3. Классификация:
   - FR-XXX — функциональные (что система делает)
   - NFR-XXX — нефункциональные (как: скорость, надёжность, безопасность)
   - BR-XXX — бизнес-правила (ограничения предметной области)
   - OQ-XXX — открытые вопросы (нужно уточнить)
4. Если пользователь уточняет ранее сказанное — обнови требование, сохранив старое в скобках "(было: ...)".
5. После блока требований предлагай, какие шаги BPMN затронет это изменение.

ИСТОРИЯ ДИАЛОГА:
{chat_history}

СТРУКТУРА ОТВЕТА (строго):

## Функциональные требования
FR-XXX: [текст]

## Нефункциональные требования
NFR-XXX: [текст]

## Бизнес-правила
BR-XXX: [текст]

## Открытые вопросы
OQ-XXX: [текст]

## Следующий шаг
[Что уточнить или предлагаешь сделать дальше]"""


async def run_requirements_agent(
    message: str,
    project_name: str,
    session_summary: str,
    chat_history: list[dict],
    existing_requirements: str = "",
) -> str:

    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in chat_history[-10:]  # последние 10 сообщений
    )

    system = REQUIREMENTS_PROMPT.format(
        project_name=project_name,
        session_summary=session_summary or "Новая сессия",
        existing_requirements=existing_requirements or "Требования ещё не сформированы",
        chat_history=history_text,
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
