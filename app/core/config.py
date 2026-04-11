from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── OpenAI ──
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MAX_TOKENS: int = 4000

    # ── Perplexity ──
    PERPLEXITY_API_KEY: str
    PERPLEXITY_MODEL: str = "sonar-pro"

    # ── Supabase ──
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str          # service_role key — только на бэкенде
    SUPABASE_ANON_KEY: str             # для клиентских проверок токенов

    # ── Storage ──
    SUPABASE_BUCKET_FILES: str = "project-files"
    SUPABASE_BUCKET_EXPORTS: str = "exports"

    # ── App ──
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    MAX_FILE_SIZE_MB: int = 20
    MAX_IMAGE_SIZE_MB: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
