from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from datetime import datetime

from app.models.schemas import ExportRequest, ExportFormat
from app.services.export_service import generate_word, generate_pdf, prepare_bpmn_file
from app.services import storage_service
from app.core.config import settings
from app.core.database import get_supabase

router = APIRouter()


def _get_project(project_id: str) -> dict:
    sb = get_supabase()
    result = sb.table("projects").select("*").eq("id", project_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return result.data


@router.post("/")
async def export_artifacts(req: ExportRequest):
    """
    Генерирует запрошенные форматы и возвращает временные ссылки.
    """
    project = _get_project(str(req.project_id))
    requirements = storage_service.get_project_requirements(str(req.project_id))
    bpmn = storage_service.get_latest_bpmn(str(req.project_id))
    bpmn_xml = bpmn.get("xml_content", "") if bpmn else ""

    results = []

    for fmt in req.formats:
        if fmt == ExportFormat.word and req.include_requirements:
            file_bytes = generate_word(
                project_name=project["name"],
                requirements=requirements,
                bpmn_description="",
            )
            path = await storage_service.upload_file(
                content=file_bytes,
                filename=f"{project['name']}_BRD.docx",
                bucket=settings.SUPABASE_BUCKET_EXPORTS,
                folder=f"projects/{req.project_id}",
            )
            url = await storage_service.get_signed_url(
                bucket=settings.SUPABASE_BUCKET_EXPORTS,
                path=path,
                expires_in=3600,
            )
            results.append({
                "format": "word",
                "filename": f"{project['name']}_BRD.docx",
                "url": url,
                "size_kb": round(len(file_bytes) / 1024),
            })

        elif fmt == ExportFormat.pdf and req.include_requirements:
            file_bytes = generate_pdf(
                project_name=project["name"],
                requirements=requirements,
            )
            path = await storage_service.upload_file(
                content=file_bytes,
                filename=f"{project['name']}_BRD.pdf",
                bucket=settings.SUPABASE_BUCKET_EXPORTS,
                folder=f"projects/{req.project_id}",
            )
            url = await storage_service.get_signed_url(
                bucket=settings.SUPABASE_BUCKET_EXPORTS,
                path=path,
                expires_in=3600,
            )
            results.append({
                "format": "pdf",
                "filename": f"{project['name']}_BRD.pdf",
                "url": url,
                "size_kb": round(len(file_bytes) / 1024),
            })

        elif fmt == ExportFormat.bpmn and req.include_bpmn:
            if not bpmn_xml:
                raise HTTPException(status_code=404, detail="BPMN-схема не найдена")
            file_bytes = prepare_bpmn_file(bpmn_xml)
            path = await storage_service.upload_file(
                content=file_bytes,
                filename=f"{project['name']}_process.bpmn",
                bucket=settings.SUPABASE_BUCKET_EXPORTS,
                folder=f"projects/{req.project_id}",
            )
            url = await storage_service.get_signed_url(
                bucket=settings.SUPABASE_BUCKET_EXPORTS,
                path=path,
                expires_in=3600,
            )
            results.append({
                "format": "bpmn",
                "filename": f"{project['name']}_process.bpmn",
                "url": url,
                "size_kb": round(len(file_bytes) / 1024),
            })

    return {
        "project_id": str(req.project_id),
        "files": results,
        "expires_in_minutes": 60,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ── Прямые эндпоинты скачивания (без Supabase Storage) ──

@router.get("/word/{project_id}")
async def download_word(project_id: str):
    """Скачать Word напрямую без промежуточного сохранения."""
    project = _get_project(project_id)
    requirements = storage_service.get_project_requirements(project_id)

    file_bytes = generate_word(
        project_name=project["name"],
        requirements=requirements,
    )
    filename = f"{project['name']}_BRD.docx"

    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf/{project_id}")
async def download_pdf(project_id: str):
    """Скачать PDF напрямую."""
    project = _get_project(project_id)
    requirements = storage_service.get_project_requirements(project_id)

    file_bytes = generate_pdf(
        project_name=project["name"],
        requirements=requirements,
    )
    filename = f"{project['name']}_BRD.pdf"

    return Response(
        content=file_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/bpmn/{project_id}")
async def download_bpmn(project_id: str):
    """Скачать .bpmn файл напрямую."""
    project = _get_project(project_id)
    bpmn = storage_service.get_latest_bpmn(project_id)

    if not bpmn or not bpmn.get("xml_content"):
        raise HTTPException(status_code=404, detail="BPMN-схема не найдена")

    file_bytes = prepare_bpmn_file(bpmn["xml_content"])
    filename = f"{project['name']}_process.bpmn"

    return Response(
        content=file_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
