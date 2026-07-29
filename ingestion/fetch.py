import os

import pandas as pd
import requests

from ingestion.config import CACHE_DIR, FPL_HISTORICAL_REPO_RAW_BASE, FPL_LIVE_API_BASE

HISTORICAL_FILES = {
    "players_raw": "players_raw.csv",
    "teams": "teams.csv",
    "fixtures": "fixtures.csv",
    "merged_gw": "gws/merged_gw.csv",
}


def _cache_path(season: str, key: str) -> str:
    return os.path.join(CACHE_DIR, season, f"{key}.csv")


def fetch_historical_csv(season: str, key: str, use_cache: bool = True) -> pd.DataFrame:
    """Download one of HISTORICAL_FILES for a season from the vaastav repo, with local caching."""
    if key not in HISTORICAL_FILES:
        raise ValueError(f"Unknown historical file key: {key}. Expected one of {list(HISTORICAL_FILES)}")

    cache_path = _cache_path(season, key)
    if use_cache and os.path.exists(cache_path):
        return pd.read_csv(cache_path, encoding="utf-8", encoding_errors="replace")

    url = f"{FPL_HISTORICAL_REPO_RAW_BASE}/{season}/{HISTORICAL_FILES[key]}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(response.content)

    return pd.read_csv(cache_path, encoding="utf-8", encoding_errors="replace")


def fetch_bootstrap_static() -> dict:
    """Live FPL API: players, teams, current gameweek/prices/status for the current season."""
    response = requests.get(f"{FPL_LIVE_API_BASE}/bootstrap-static/", timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_live_fixtures() -> list:
    response = requests.get(f"{FPL_LIVE_API_BASE}/fixtures/", timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_event_live(gameweek: int) -> dict:
    """Per-player stats for a single completed (or in-progress) gameweek."""
    response = requests.get(f"{FPL_LIVE_API_BASE}/event/{gameweek}/live/", timeout=30)
    response.raise_for_status()
    return response.json()
