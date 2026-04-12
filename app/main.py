from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.api import chat, projects, sessions, files, export
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="BA Assistant API",
    version="0.1.0",
    description="ИИ-ассистент для бизнес-аналитиков",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ──
app.include_router(chat.router,     prefix="/api/chat",     tags=["chat"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(files.router,    prefix="/api/files",    tags=["files"])
app.include_router(export.router,   prefix="/api/export",   tags=["export"])


# ── Frontend ──
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Отдаём фронтенд на корневом URL."""
    if os.path.exists(FRONTEND_PATH):
        return FileResponse(FRONTEND_PATH, media_type="text/html")
    return {"message": "BA Assistant API", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
