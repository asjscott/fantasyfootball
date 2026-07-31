import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")

FPL_HISTORICAL_REPO_RAW_BASE = (
    "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data"
)
FPL_LIVE_API_BASE = "https://fantasy.premierleague.com/api"

CACHE_DIR = os.environ.get("INGESTION_CACHE_DIR", ".cache")

# Historical seasons to backfill by default. Extended back to 2019-20 (rather
# than the original 2020-21 floor) so a walk-forward replay of 2025-26 (see
# ml/backtest.py) has a deep pre-season training base even for its earliest
# gameweeks. 2025-26 itself is included as full historical data — it's the
# season being replayed gameweek-by-gameweek, and its own earlier gameweeks
# feed into training later ones within the same season.
DEFAULT_HISTORICAL_SEASONS = [
    "2019-20",
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
    "2025-26",
]

CURRENT_SEASON = "2026-27"


def require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in, "
            "or export DATABASE_URL directly."
        )
    return DATABASE_URL
