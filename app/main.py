from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

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

app.include_router(chat.router,     prefix="/api/chat",     tags=["chat"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(files.router,    prefix="/api/files",    tags=["files"])
app.include_router(export.router,   prefix="/api/export",   tags=["export"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
