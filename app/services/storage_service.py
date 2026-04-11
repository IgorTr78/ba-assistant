import uuid
from app.core.database import get_supabase
from app.core.config import settings


async def upload_file(
    content: bytes,
    filename: str,
    bucket: str,
    folder: str = "",
) -> str:
    """
    Загружает файл в Supabase Storage.
    Возвращает путь в бакете.
    """
    sb = get_supabase()
    unique_name = f"{uuid.uuid4()}_{filename}"
    path = f"{folder}/{unique_name}".lstrip("/")

    sb.storage.from_(bucket).upload(
        path=path,
        file=content,
        file_options={"content-type": _guess_content_type(filename)},
    )
    return path


async def get_signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    """Генерирует временную ссылку на файл."""
    sb = get_supabase()
    result = sb.storage.from_(bucket).create_signed_url(path, expires_in)
    return result.get("signedURL", "")


async def delete_file(bucket: str, path: str) -> None:
    sb = get_supabase()
    sb.storage.from_(bucket).remove([path])


def _guess_content_type(filename: str) -> str:
    ext = filename.rsplit('.', 1)[-1].lower()
    mapping = {
        'pdf':  'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'bpmn': 'application/xml',
        'xml':  'application/xml',
        'png':  'image/png',
        'jpg':  'image/jpeg',
        'jpeg': 'image/jpeg',
        'webp': 'image/webp',
    }
    return mapping.get(ext, 'application/octet-stream')


# ── DB helpers ──

def save_file_record(
    project_id: str,
    session_id: str | None,
    filename: str,
    file_type: str,
    storage_path: str,
    extracted_text: str,
    file_size: int,
) -> dict:
    sb = get_supabase()
    result = sb.table("uploaded_files").insert({
        "project_id": project_id,
        "session_id": session_id,
        "filename": filename,
        "file_type": file_type,
        "storage_path": storage_path,
        "extracted_text": extracted_text,
        "file_size": file_size,
    }).execute()
    return result.data[0] if result.data else {}


def get_file_record(file_id: str) -> dict | None:
    sb = get_supabase()
    result = sb.table("uploaded_files").select("*").eq("id", file_id).single().execute()
    return result.data


def save_requirement(
    project_id: str,
    session_id: str | None,
    req_type: str,
    code: str,
    content: str,
    created_by: str,
) -> dict:
    sb = get_supabase()
    result = sb.table("requirements").insert({
        "project_id": project_id,
        "session_id": session_id,
        "type": req_type,
        "code": code,
        "content": content,
        "created_by": created_by,
        "version": 1,
    }).execute()
    return result.data[0] if result.data else {}


def get_project_requirements(project_id: str) -> list[dict]:
    sb = get_supabase()
    result = (
        sb.table("requirements")
        .select("*")
        .eq("project_id", project_id)
        .order("code")
        .execute()
    )
    return result.data or []


def save_bpmn(
    project_id: str,
    xml_content: str,
    edited_by: str,
    version: int = 1,
) -> dict:
    sb = get_supabase()
    result = sb.table("bpmn_diagrams").insert({
        "project_id": project_id,
        "xml_content": xml_content,
        "edited_by": edited_by,
        "version": version,
    }).execute()
    return result.data[0] if result.data else {}


def get_latest_bpmn(project_id: str) -> dict | None:
    sb = get_supabase()
    result = (
        sb.table("bpmn_diagrams")
        .select("*")
        .eq("project_id", project_id)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
