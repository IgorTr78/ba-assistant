import httpx
from app.core.config import settings

COMPETITOR_PROMPT = """Ты — аналитик конкурентной среды для команды бизнес-аналитиков.
Найди актуальную информацию о практиках конкурентов и структурируй её как входные данные для требований.

ПРОЕКТ: {project_name}
ОБЛАСТЬ: {domain}

ИНСТРУКЦИЯ:
1. Ищи в открытых источниках: сайты компаний, отраслевые обзоры, новости, публичные кейсы,
   App Store/Google Play отзывы, вакансии (раскрывают стек и процессы).
2. Фокусируйся на том, что практически применимо для проекта.
3. Указывай дату источника. Если старше 1 года — отметь.

СТРУКТУРА ОТВЕТА:

### Обзор рынка
[ключевые игроки, уровень зрелости решений]

### Практики конкурентов
Для каждого (не более 5):
**[Название]**
- Что делают: ...
- Как реализовано: ...
- Сильные стороны: ...
- Слабые стороны / жалобы: ...
- Источник: [ссылка]

### Общие паттерны отрасли
[что делают все — де-факто стандарт]

### Незакрытые потребности рынка
[возможности для дифференциации]

### Выводы для требований
[конкретные рекомендации: что включить в BRD]"""


async def run_competitor_analyst(
    query: str,
    project_name: str,
    domain: str = "",
) -> str:

    system = COMPETITOR_PROMPT.format(
        project_name=project_name,
        domain=domain or "не указана",
    )

    async with httpx.AsyncClient(timeout=30.0) as http:
        response = await http.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.PERPLEXITY_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": query},
                ],
                "max_tokens": 2000,
                "temperature": 0.2,
                "return_citations": True,
                "search_recency_filter": "month",  # только свежие источники
            },
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]

    # Добавляем цитаты если Perplexity их вернул
    citations = data.get("citations", [])
    if citations:
        sources = "\n\n---\n**Источники:**\n" + "\n".join(
            f"{i+1}. {url}" for i, url in enumerate(citations[:8])
        )
        content += sources

    return content
