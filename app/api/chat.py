import uuid
import asyncio
import httpx
from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest, ChatResponse, AgentName
from app.agents.orchestrator import run_orchestrator
from app.agents.requirements_agent import run_requirements_agent
from app.agents.document_agent import run_document_analyst, run_image_analyst, encode_image_to_base64
from app.agents.bpmn_agent import run_bpmn_agent
from app.agents.competitor_agent import run_competitor_analyst
from app.agents.entity_agent import run_entity_agent
from app.services import storage_service
from app.services.memory_service import (
    build_project_context,
    get_or_create_summary,
    update_project_memory,
    format_history_for_prompt,
)
from app.core.database import get_supabase

router = APIRouter()


def _get_project(project_id: str) -> dict:
    sb = get_supabase()
    result = sb.table("projects").select("*").eq("id", str(project_id)).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return result.data


def _get_session_messages(session_id: str) -> list[dict]:
    sb = get_supabase()
    result = sb.table("sessions").select("messages").eq("id", str(session_id)).single().execute()
    if result.data:
        return result.data.get("messages", [])
    return []


def _save_message(session_id: str, role: str, content: str, agent: str | None = None):
    sb = get_supabase()
    messages = _get_session_messages(str(session_id))
    messages.append({
        "role": role,
        "content": content,
        "agent": agent,
    })
    sb.table("sessions").update({"messages": messages}).eq("id", str(session_id)).execute()


def _format_requirements(requirements: list[dict]) -> str:
    if not requirements:
        return ""
    return "\n".join(f"{r.get('code','')}: {r.get('content','')}" for r in requirements)


def _extract_url(message: str) -> str | None:
    import re
    urls = re.findall(r'https?://[^\s]+', message)
    return urls[0] if urls else None


async def _download_pdf(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                return r.content
    except Exception as e:
        print(f"PDF download error: {e}")
    return None


@router.post("/message", response_model=ChatResponse)
async def send_message(req: ChatRequest):

    # 1. Загружаем проект
    project = _get_project(str(req.project_id))

    # 2. Файлы и изображения
    file_records = []
    image_records = []
    for fid in req.file_ids:
        rec = storage_service.get_file_record(str(fid))
        if rec:
            file_records.append(rec)
    for iid in req.image_ids:
        rec = storage_service.get_file_record(str(iid))
        if rec and rec.get("file_type") == "image":
            image_records.append(rec)

    # 3. Сохраняем сообщение пользователя
    _save_message(str(req.session_id), "user", req.message)

    # 4. Загружаем историю и память
    all_messages = _get_session_messages(str(req.session_id))

    # Проектный контекст (требования + решения + глоссарий)
    project_context = build_project_context(
        project_id=str(req.project_id),
        project_name=project["name"],
        project_description=project.get("description", ""),
    )

    # Саммари сессии (автоматически обновляется)
    session_summary = await get_or_create_summary(str(req.session_id), all_messages)

    # 5. Оркестратор
    routing = await run_orchestrator(
        message=req.message,
        project_name=project["name"],
        project_description=project.get("description", ""),
        has_files=bool(file_records),
        has_images=bool(image_records),
    )

    if routing.needs_clarification:
        _save_message(str(req.session_id), "assistant",
                      routing.clarification_question, "clarification")
        return ChatResponse(
            session_id=req.session_id,
            message_id=uuid.uuid4(),
            agent=AgentName.clarification,
            content=routing.clarification_question,
        )

    # 6. Запускаем агента
    agent = routing.priority_agent
    content = ""
    bpmn_xml = None
    artifacts = []

    # ── Изображения ──
    if agent == AgentName.image_analyst and image_records:
        images_data = []
        for rec in image_records:
            try:
                sb = get_supabase()
                file_bytes = sb.storage.from_("project-files").download(rec["storage_path"])
                media_type = "image/jpeg" if rec["filename"].lower().endswith(('jpg','jpeg')) else "image/png"
                images_data.append({
                    "base64": encode_image_to_base64(file_bytes),
                    "media_type": media_type,
                    "filename": rec["filename"],
                })
            except Exception as e:
                print(f"Image load error: {e}")
        if images_data:
            content = await run_image_analyst(
                images=images_data,
                project_name=project["name"],
                additional_context=req.message + "\n\nКОНТЕКСТ ПРОЕКТА:\n" + project_context,
            )
        else:
            content = "Не удалось загрузить изображения."

    # ── Анализ документов ──
    elif agent == AgentName.document_analyst:
        if file_records:
            rec = file_records[0]
            content = await run_document_analyst(
                extracted_text=rec.get("extracted_text", ""),
                filename=rec["filename"],
                file_type=rec["file_type"],
                project_name=project["name"],
            )
        else:
            url = _extract_url(req.message)
            if url and url.lower().split('?')[0].endswith('.pdf'):
                pdf_bytes = await _download_pdf(url)
                if pdf_bytes:
                    from app.services.file_processor import extract_text_from_pdf, truncate_text
                    extracted = truncate_text(extract_text_from_pdf(pdf_bytes))
                    content = await run_document_analyst(
                        extracted_text=extracted,
                        filename=url.split('/')[-1].split('?')[0] or "document.pdf",
                        file_type="pdf",
                        project_name=project["name"],
                    )
                    content = f"📄 Документ загружен по ссылке\n\n" + content
                else:
                    content = (
                        f"Не удалось скачать PDF: {url}\n\n"
                        "Скачайте файл и загрузите через кнопку 📎 в чате."
                    )
            else:
                # Нет файла — передаём в агент требований с полным контекстом
                content = await run_requirements_agent(
                    message=req.message,
                    project_name=project["name"],
                    session_summary=session_summary,
                    chat_history=all_messages,
                    project_context=project_context,
                )

    # ── Требования ──
    elif agent == AgentName.requirements:
        content = await run_requirements_agent(
            message=req.message,
            project_name=project["name"],
            session_summary=session_summary,
            chat_history=all_messages,
            project_context=project_context,
        )

    # ── BPMN ──
    elif agent == AgentName.bpmn:
        existing_reqs = storage_service.get_project_requirements(str(req.project_id))
        existing_bpmn = storage_service.get_latest_bpmn(str(req.project_id))
        result = await run_bpmn_agent(
            requirements_text=_format_requirements(existing_reqs) or req.message,
            project_name=project["name"],
            existing_bpmn_xml=existing_bpmn.get("xml_content") if existing_bpmn else None,
        )
        bpmn_xml = result.get("xml", "")
        content = result.get("description", "")
        if bpmn_xml:
            version = (existing_bpmn.get("version", 0) + 1) if existing_bpmn else 1
            storage_service.save_bpmn(
                project_id=str(req.project_id),
                xml_content=bpmn_xml,
                edited_by=str(req.session_id),
                version=version,
            )
            artifacts.append({"type": "bpmn", "version": version})

    # ── Конкуренты ──
    elif agent == AgentName.competitor:
        content = await run_competitor_analyst(
            query=req.message,
            project_name=project["name"],
            domain=project.get("description", ""),
        )

    # ── Сущности ──
    elif agent == AgentName.entity:
        reqs = storage_service.get_project_requirements(str(req.project_id))
        content = await run_entity_agent(
            context=_format_requirements(reqs) or req.message,
            project_name=project["name"],
        )

    # ── Фолбэк ──
    else:
        content = await run_requirements_agent(
            message=req.message,
            project_name=project["name"],
            session_summary=session_summary,
            chat_history=all_messages,
            project_context=project_context,
        )

    # 7. Сохраняем ответ
    _save_message(str(req.session_id), "assistant", content, agent.value)

    # 8. Обновляем проектную память асинхронно (не блокируем ответ)
    updated_messages = _get_session_messages(str(req.session_id))
    asyncio.create_task(update_project_memory(
        project_id=str(req.project_id),
        project_name=project["name"],
        recent_messages=updated_messages[-20:],
    ))

    return ChatResponse(
        session_id=req.session_id,
        message_id=uuid.uuid4(),
        agent=agent,
        content=content,
        artifacts=artifacts,
        bpmn_xml=bpmn_xml,
    )


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    messages = _get_session_messages(session_id)
    return {"session_id": session_id, "messages": messages}
