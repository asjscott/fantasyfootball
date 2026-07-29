import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")
CURRENT_SEASON = os.environ.get("CURRENT_SEASON", "2026-27")
ARTIFACTS_DIR = os.environ.get("ML_ARTIFACTS_DIR", os.path.join(os.path.dirname(__file__), "artifacts"))


def require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in, "
            "or export DATABASE_URL directly."
        )
    return DATABASE_URL
