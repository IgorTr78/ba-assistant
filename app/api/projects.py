from fastapi import APIRouter, HTTPException
from app.models.schemas import ProjectCreate, ProjectUpdate, SessionCreate
from app.core.database import get_supabase
import uuid

# ── Projects ──
router = APIRouter()


@router.get("/")
async def list_projects():
    sb = get_supabase()
    result = sb.table("projects").select("*").order("created_at", desc=True).execute()
    return result.data or []


@router.post("/")
async def create_project(body: ProjectCreate):
    sb = get_supabase()
    result = sb.table("projects").insert({
        "name": body.name,
        "description": body.description,
        "color": body.color,
        "status": "active",
        "team_id": str(body.team_id) if body.team_id else None,
        "created_by": str(uuid.uuid4()),  # заменить на user_id из auth
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Ошибка создания проекта")
    return result.data[0]


@router.get("/{project_id}")
async def get_project(project_id: str):
    sb = get_supabase()
    result = sb.table("projects").select("*").eq("id", project_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return result.data


@router.patch("/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate):
    sb = get_supabase()
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    result = sb.table("projects").update(update_data).eq("id", project_id).execute()
    return result.data[0] if result.data else {}


@router.delete("/{project_id}")
async def archive_project(project_id: str):
    sb = get_supabase()
    sb.table("projects").update({"status": "archived"}).eq("id", project_id).execute()
    return {"archived": True, "project_id": project_id}


@router.get("/{project_id}/requirements")
async def get_requirements(project_id: str):
    from app.services import storage_service
    return storage_service.get_project_requirements(project_id)


@router.get("/{project_id}/bpmn")
async def get_bpmn(project_id: str):
    from app.services import storage_service
    diagram = storage_service.get_latest_bpmn(project_id)
    if not diagram:
        raise HTTPException(status_code=404, detail="BPMN-схема не найдена")
    return diagram
