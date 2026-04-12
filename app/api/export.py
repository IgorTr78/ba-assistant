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
        raise HTTPException(status_code=404, detail="Project not found")
    return result.data


@router.post("/")
async def export_artifacts(req: ExportRequest):
    project = _get_project(str(req.project_id))
    requirements = storage_service.get_project_requirements(str(req.project_id))
    bpmn = storage_service.get_latest_bpmn(str(req.project_id))
    bpmn_xml = bpmn.get("xml_content", "") if bpmn else ""
    results = []
    for fmt in req.formats:
        if fmt == ExportFormat.word and req.include_requirements:
            file_bytes = generate_word(project_name=project["name"], requirements=requirements)
            results.append({"format": "word", "filename": "requirements.docx"})
        elif fmt == ExportFormat.bpmn and req.include_bpmn:
            if not bpmn_xml:
                raise HTTPException(status_code=404, detail="BPMN diagram not found")
            results.append({"format": "bpmn", "filename": "process.bpmn"})
    return {"project_id": str(req.project_id), "files": results}


@router.get("/word/{project_id}")
async def download_word(project_id: str):
    project = _get_project(project_id)
    requirements = storage_service.get_project_requirements(project_id)
    file_bytes = generate_word(project_name=project["name"], requirements=requirements)
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=\"requirements.docx\""},
    )


@router.get("/pdf/{project_id}")
async def download_pdf(project_id: str):
    project = _get_project(project_id)
    requirements = storage_service.get_project_requirements(project_id)
    file_bytes = generate_pdf(project_name=project["name"], requirements=requirements)
    return Response(
        content=file_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=\"requirements.pdf\""},
    )


@router.get("/bpmn/{project_id}")
async def download_bpmn(project_id: str):
    _get_project(project_id)
    bpmn = storage_service.get_latest_bpmn(project_id)
    if not bpmn or not bpmn.get("xml_content"):
        raise HTTPException(status_code=404, detail="BPMN diagram not found")
    file_bytes = prepare_bpmn_file(bpmn["xml_content"])
    return Response(
        content=file_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=\"process.bpmn\""},
    )
