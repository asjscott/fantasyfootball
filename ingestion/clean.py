"""Schema normalization for vaastav/Fantasy-Premier-League CSVs.

Column names drift across seasons (e.g. `defensive_contribution` only exists
from 2025-26 onward). Each `clean_*` function selects/renames the columns we
care about and fills any season-absent column with NaN rather than failing,
so downstream loading always sees a stable shape.
"""

import numpy as np
import pandas as pd

# Columns that don't exist in every season. Missing ones are added as NaN.
_OPTIONAL_GW_STAT_COLUMNS = {
    "expected_goals": np.nan,
    "expected_assists": np.nan,
    "expected_goal_involvements": np.nan,
    "expected_goals_conceded": np.nan,
    "defensive_contribution": np.nan,
}


def _with_optional_columns(df: pd.DataFrame, defaults: dict) -> pd.DataFrame:
    df = df.copy()
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
    return df


def clean_teams(df: pd.DataFrame, season: str) -> pd.DataFrame:
    out = df[["code", "id", "name", "strength", "strength_attack_home", "strength_attack_away",
              "strength_defence_home", "strength_defence_away"]].copy()
    out = out.rename(columns={
        "code": "fpl_code",
        "id": "fpl_season_team_id",
    })
    out["season"] = season
    return out


def clean_players_raw(df: pd.DataFrame, season: str) -> pd.DataFrame:
    out = df[["id", "code", "first_name", "second_name", "web_name", "team", "element_type"]].copy()
    out = out.rename(columns={
        "id": "fpl_season_element_id",
        "code": "fpl_code",
        "team": "fpl_season_team_id",
    })
    out["season"] = season
    out["position"] = out["element_type"].map({1: "GK", 2: "DEF", 3: "MID", 4: "FWD"})
    return out.drop(columns=["element_type"])


def clean_fixtures(df: pd.DataFrame, season: str) -> pd.DataFrame:
    out = df[["id", "code", "event", "kickoff_time", "team_h", "team_a", "team_h_score",
              "team_a_score", "finished", "team_h_difficulty", "team_a_difficulty"]].copy()
    out = out.rename(columns={
        "id": "fpl_season_fixture_id",
        "code": "fpl_fixture_code",
        "event": "gameweek",
        "team_h": "fpl_season_home_team_id",
        "team_a": "fpl_season_away_team_id",
        "team_h_score": "home_score",
        "team_a_score": "away_score",
        "team_h_difficulty": "home_difficulty",
        "team_a_difficulty": "away_difficulty",
    })
    out["season"] = season
    return out


def clean_gameweek_stats(df: pd.DataFrame, season: str) -> pd.DataFrame:
    """Clean `gws/merged_gw.csv`. Note `team`/`opponent_team` here are the
    season-scoped team name/id, not our internal team_id — resolved at load time.
    """
    df = _with_optional_columns(df, _OPTIONAL_GW_STAT_COLUMNS)

    columns = [
        "element", "GW", "fixture", "team", "opponent_team", "was_home", "minutes",
        "total_points", "goals_scored", "assists", "clean_sheets", "goals_conceded",
        "own_goals", "penalties_saved", "penalties_missed", "yellow_cards", "red_cards",
        "saves", "bonus", "bps", "influence", "creativity", "threat", "ict_index", "starts",
        "expected_goals", "expected_assists", "expected_goal_involvements",
        "expected_goals_conceded", "defensive_contribution", "value", "selected",
    ]
    out = df[columns].copy()
    out = out.rename(columns={
        "element": "fpl_season_element_id",
        "GW": "gameweek",
        "fixture": "fpl_season_fixture_id",
        "team": "team_name",
        "opponent_team": "fpl_season_opponent_team_id",
    })
    out["season"] = season
    out["source"] = "github_historical"
    out["was_home"] = out["was_home"].astype(bool)
    return out
