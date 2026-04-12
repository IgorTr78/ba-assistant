"""
Сервис памяти для BA Assistant.

Три уровня:
1. Краткосрочная — последние 30 сообщений диалога
2. Сессионная — автосаммари каждые 15 сообщений
3. Проектная — накопленный контекст: требования, решения, сущности, глоссарий
"""

from openai import AsyncOpenAI
from app.core.config import settings
from app.core.database import get_supabase

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

MAX_HISTORY = 30          # сообщений в контексте
SUMMARY_EVERY = 15        # сжимаем каждые N сообщений
MAX_SUMMARY_CHARS = 1500  # максимум символов в саммари


# ─────────────────────────────────────────
# ПОЛУЧЕНИЕ ПОЛНОГО КОНТЕКСТА ПРОЕКТА
# ─────────────────────────────────────────

def build_project_context(
    project_id: str,
    project_name: str,
    project_description: str = "",
) -> str:
    """
    Собирает весь накопленный контекст проекта:
    - Описание проекта
    - Требования (FR/NFR/BR/OQ)
    - Сущности и источники данных
    - Принятые решения и открытые вопросы
    - Глоссарий
    """
    sb = get_supabase()
    parts = []

    # Описание проекта
    parts.append(f"ПРОЕКТ: {project_name}")
    if project_description:
        parts.append(f"ОПИСАНИЕ: {project_description}")

    # Требования
    try:
        reqs = sb.table("requirements").select("*").eq("project_id", project_id).order("code").execute()
        if reqs.data:
            req_lines = []
            for r in reqs.data:
                req_lines.append(f"  {r['code']}: {r['content']}")
            parts.append("НАКОПЛЕННЫЕ ТРЕБОВАНИЯ:\n" + "\n".join(req_lines))
    except Exception:
        pass

    # Последняя BPMN схема (описание, не XML)
    try:
        bpmn = sb.table("bpmn_diagrams").select("version,updated_at").eq("project_id", project_id).order("version", desc=True).limit(1).execute()
        if bpmn.data:
            parts.append(f"BPMN-СХЕМА: версия {bpmn.data[0]['version']}, обновлена {bpmn.data[0]['updated_at'][:10]}")
    except Exception:
        pass

    # Проектная память (доп. заметки)
    try:
        mem = sb.table("project_memory").select("*").eq("project_id", project_id).order("updated_at", desc=True).limit(1).execute()
        if mem.data:
            m = mem.data[0]
            if m.get("key_decisions"):
                parts.append("КЛЮЧЕВЫЕ РЕШЕНИЯ:\n" + m["key_decisions"])
            if m.get("glossary"):
                parts.append("ГЛОССАРИЙ:\n" + m["glossary"])
            if m.get("open_questions"):
                parts.append("ОТКРЫТЫЕ ВОПРОСЫ:\n" + m["open_questions"])
            if m.get("stakeholders"):
                parts.append("СТЕЙКХОЛДЕРЫ:\n" + m["stakeholders"])
    except Exception:
        pass

    return "\n\n".join(parts)


# ─────────────────────────────────────────
# САММАРИ СЕССИИ
# ─────────────────────────────────────────

async def get_or_create_summary(session_id: str, messages: list[dict]) -> str:
    """
    Возвращает актуальное саммари сессии.
    Если сообщений стало много — обновляет саммари через GPT.
    """
    sb = get_supabase()

    # Читаем текущее саммари
    try:
        result = sb.table("sessions").select("summary,summary_up_to").eq("id", session_id).single().execute()
        current_summary = result.data.get("summary", "") if result.data else ""
        summary_up_to = result.data.get("summary_up_to", 0) if result.data else 0
    except Exception:
        current_summary = ""
        summary_up_to = 0

    # Если новых сообщений меньше SUMMARY_EVERY — возвращаем старое
    new_messages_count = len(messages) - summary_up_to
    if new_messages_count < SUMMARY_EVERY:
        return current_summary

    # Нужно обновить саммари
    new_summary = await _generate_summary(
        existing_summary=current_summary,
        new_messages=messages[summary_up_to:],
        project_name="",
    )

    # Сохраняем в БД
    try:
        sb.table("sessions").update({
            "summary": new_summary,
            "summary_up_to": len(messages),
        }).eq("id", session_id).execute()
    except Exception:
        pass

    return new_summary


async def _generate_summary(
    existing_summary: str,
    new_messages: list[dict],
    project_name: str,
) -> str:
    """Генерирует сжатое саммари диалога."""
    history = "\n".join(
        f"{m['role'].upper()}: {m['content'][:300]}"
        for m in new_messages[-20:]
    )

    prompt = f"""Ты — ассистент бизнес-аналитика. Сожми историю диалога в краткое структурированное резюме.

{'ПРЕДЫДУЩЕЕ РЕЗЮМЕ:\n' + existing_summary if existing_summary else ''}

НОВЫЕ СООБЩЕНИЯ:
{history}

Напиши резюме (максимум 500 слов) которое включает:
- Что обсуждалось (процессы, требования, проблемы)
- Ключевые решения которые были приняты
- Открытые вопросы которые ещё не решены
- Важные детали предметной области

Пиши кратко, по делу, без вводных слов."""

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=800,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content[:MAX_SUMMARY_CHARS]
    except Exception as e:
        return existing_summary or ""


# ─────────────────────────────────────────
# ОБНОВЛЕНИЕ ПРОЕКТНОЙ ПАМЯТИ
# ─────────────────────────────────────────

async def update_project_memory(
    project_id: str,
    project_name: str,
    recent_messages: list[dict],
):
    """
    После каждого ответа обновляет проектную память:
    ключевые решения, глоссарий, стейкхолдеры.
    Вызывается асинхронно, не блокирует ответ.
    """
    if len(recent_messages) < 5:
        return

    sb = get_supabase()

    # Берём последние сообщения для анализа
    history = "\n".join(
        f"{m['role'].upper()}: {m['content'][:400]}"
        for m in recent_messages[-10:]
    )

    prompt = f"""Проанализируй диалог бизнес-аналитика и обнови проектную память.

ПРОЕКТ: {project_name}

ДИАЛОГ:
{history}

Верни ТОЛЬКО валидный JSON (без markdown):
{{
  "key_decisions": "Принятые решения через точку с запятой. Только если есть новые.",
  "open_questions": "Открытые вопросы через точку с запятой. Только если есть новые.",
  "glossary": "термин: определение; термин2: определение2. Только новые термины.",
  "stakeholders": "Роль: описание; Роль2: описание2. Только если упоминались."
}}

Если информации нет — пустая строка для этого поля."""

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=500,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        data = json.loads(response.choices[0].message.content)

        # Читаем существующую память
        existing = sb.table("project_memory").select("*").eq("project_id", project_id).execute()

        if existing.data:
            old = existing.data[0]
            # Объединяем старое с новым
            def merge(old_val: str, new_val: str) -> str:
                if not new_val:
                    return old_val or ""
                if not old_val:
                    return new_val
                return old_val + "; " + new_val

            sb.table("project_memory").update({
                "key_decisions": merge(old.get("key_decisions",""), data.get("key_decisions","")),
                "open_questions": merge(old.get("open_questions",""), data.get("open_questions","")),
                "glossary": merge(old.get("glossary",""), data.get("glossary","")),
                "stakeholders": merge(old.get("stakeholders",""), data.get("stakeholders","")),
            }).eq("project_id", project_id).execute()
        else:
            sb.table("project_memory").insert({
                "project_id": project_id,
                "key_decisions": data.get("key_decisions", ""),
                "open_questions": data.get("open_questions", ""),
                "glossary": data.get("glossary", ""),
                "stakeholders": data.get("stakeholders", ""),
            }).execute()

    except Exception as e:
        print(f"Memory update error: {e}")


# ─────────────────────────────────────────
# ФОРМАТИРОВАНИЕ КОНТЕКСТА ДЛЯ ПРОМПТА
# ─────────────────────────────────────────

def format_history_for_prompt(messages: list[dict], max_messages: int = MAX_HISTORY) -> str:
    """Форматирует историю для передачи в промпт."""
    recent = messages[-max_messages:]
    lines = []
    for m in recent:
        role = "АНАЛИТИК" if m["role"] == "user" else "АССИСТЕНТ"
        content = m["content"][:800]  # ограничиваем длину одного сообщения
        agent = f" [{m['agent']}]" if m.get("agent") else ""
        lines.append(f"{role}{agent}: {content}")
    return "\n\n".join(lines)
