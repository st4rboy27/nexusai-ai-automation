"""Environment configuration. Values from the OS environment take precedence over .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

class Settings:
    app_name = os.getenv("APP_NAME", "NexusAI")
    database_path = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "nexusai.db"))
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5").strip()
    llm_timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))

settings = Settings()
