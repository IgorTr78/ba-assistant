from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import uuid

from app.services.file_processor import extract_text, get_file_type, truncate_text
from app.services import storage_service
from app.core.config import settings

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/xml",
    "text/xml",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.bpmn', '.xml', '.png', '.jpg', '.jpeg', '.webp'}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    session_id: Optional[str] = Form(None),
):
    """
    Загружает файл (документ или изображение) в Supabase Storage.
    Для документов сразу извлекает текст.
    """
    # Проверка расширения
    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый тип файла. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await file.read()

    # Проверка размера
    file_type = get_file_type(file.filename, file.content_type or "")
    max_mb = settings.MAX_IMAGE_SIZE_MB if file_type == "image" else settings.MAX_FILE_SIZE_MB
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Файл слишком большой. Максимум: {max_mb} МБ"
        )

    # Извлекаем текст (для изображений — пустая строка, анализ через Vision)
    extracted_text = ""
    if file_type != "image":
        raw_text = extract_text(content, file.filename, file.content_type or "")
        extracted_text = truncate_text(raw_text)

    # Загружаем в Storage
    folder = f"projects/{project_id}/{file_type}s"
    storage_path = await storage_service.upload_file(
        content=content,
        filename=file.filename,
        bucket=settings.SUPABASE_BUCKET_FILES,
        folder=folder,
    )

    # Сохраняем запись в БД
    record = storage_service.save_file_record(
        project_id=project_id,
        session_id=session_id,
        filename=file.filename,
        file_type=file_type,
        storage_path=storage_path,
        extracted_text=extracted_text,
        file_size=len(content),
    )

    return {
        "id": record.get("id"),
        "filename": file.filename,
        "file_type": file_type,
        "size": len(content),
        "extracted_text_length": len(extracted_text),
        "storage_path": storage_path,
        "ready_for_analysis": True,
    }


@router.get("/{file_id}")
async def get_file_info(file_id: str):
    """Возвращает метаданные файла."""
    record = storage_service.get_file_record(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="Файл не найден")
    # Не возвращаем extracted_text — он может быть большим
    return {k: v for k, v in record.items() if k != "extracted_text"}


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    """Удаляет файл из Storage и БД."""
    record = storage_service.get_file_record(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="Файл не найден")

    await storage_service.delete_file(
        bucket=settings.SUPABASE_BUCKET_FILES,
        path=record["storage_path"],
    )

    from app.core.database import get_supabase
    get_supabase().table("uploaded_files").delete().eq("id", file_id).execute()

    return {"deleted": True, "file_id": file_id}
