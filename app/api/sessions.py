from fastapi import APIRouter, HTTPException
from app.models.schemas import SessionCreate
from app.core.database import get_supabase
import uuid

router = APIRouter()


@router.post("/")
async def create_session(body: SessionCreate):
    sb = get_supabase()
    result = sb.table("sessions").insert({
        "project_id": str(body.project_id),
        "user_id": str(uuid.uuid4()),   # заменить на auth user
        "title": body.title or "Новая сессия",
        "messages": [],
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Ошибка создания сессии")
    return result.data[0]


@router.get("/{session_id}")
async def get_session(session_id: str):
    sb = get_supabase()
    result = sb.table("sessions").select("*").eq("id", session_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return result.data


@router.get("/project/{project_id}")
async def list_sessions(project_id: str):
    sb = get_supabase()
    result = (
        sb.table("sessions")
        .select("id, title, created_at, updated_at")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@router.patch("/{session_id}/title")
async def rename_session(session_id: str, title: str):
    sb = get_supabase()
    sb.table("sessions").update({"title": title}).eq("id", session_id).execute()
    return {"updated": True}
