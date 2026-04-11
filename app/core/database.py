from supabase import create_client, Client
from app.core.config import settings

_supabase: Client | None = None


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _supabase


async def init_db():
    """Проверяем подключение к Supabase при старте."""
    try:
        sb = get_supabase()
        sb.table("projects").select("id").limit(1).execute()
        print("✓ Supabase connected")
    except Exception as e:
        print(f"✗ Supabase connection error: {e}")
