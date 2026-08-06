"""Reads training/prediction context from Postgres. No network calls —
all external data (historical + live) is expected to already be loaded by
`/ingestion` before this module runs.
"""

import json

import pandas as pd

from ml.db import get_connection

_TRAINING_QUERY = """
    SELECT
        pgs.player_id, pgs.season, pgs.gameweek, ps.position, pgs.was_home,
        pgs.minutes, pgs.total_points, pgs.goals_scored, pgs.assists, pgs.bps,
        pgs.ict_index, pgs.value, pgs.expected_goals, pgs.expected_assists,
        pgs.defensive_contribution,
        own.strength_attack_home, own.strength_attack_away,
        own.strength_defence_home, own.strength_defence_away,
        opp.strength_attack_home AS opp_strength_attack_home,
        opp.strength_attack_away AS opp_strength_attack_away,
        opp.strength_defence_home AS opp_strength_defence_home,
        opp.strength_defence_away AS opp_strength_defence_away,
        f.home_difficulty, f.away_difficulty, f.kickoff_time
    FROM player_gameweek_stats pgs
    JOIN player_seasons ps ON ps.player_id = pgs.player_id AND ps.season = pgs.season
    LEFT JOIN team_seasons own ON own.id = pgs.team_id
    LEFT JOIN team_seasons opp ON opp.id = pgs.opponent_team_id
    LEFT JOIN fixtures f ON f.id = pgs.fixture_id
    WHERE pgs.season = ANY(%(seasons)s)
    ORDER BY pgs.season, pgs.gameweek, pgs.player_id
"""


def load_training_frame(seasons: list[str]) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql(_TRAINING_QUERY, conn, params={"seasons": seasons})


_LATEST_STATUS_QUERY = """
    SELECT DISTINCT ON (player_id)
        player_id, team_id, position, now_cost, status,
        chance_of_playing_this_round, chance_of_playing_next_round,
        form, selected_by_percent, ep_this, ep_next
    FROM player_current_status
    WHERE season = %(season)s
    ORDER BY player_id, as_of DESC
"""


def load_latest_status(season: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql(_LATEST_STATUS_QUERY, conn, params={"season": season})


_UPCOMING_FIXTURES_QUERY = """
    SELECT
        f.id AS fixture_id, f.gameweek, f.kickoff_time,
        f.home_team_id, f.away_team_id, f.home_difficulty, f.away_difficulty
    FROM fixtures f
    WHERE f.season = %(season)s AND f.gameweek = %(gameweek)s
"""


def load_upcoming_fixtures(season: str, gameweek: int) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql(
            _UPCOMING_FIXTURES_QUERY, conn, params={"season": season, "gameweek": gameweek}
        )


_PREDICT_FIXTURE_CONTEXT_QUERY = """
    SELECT
        ps.player_id, %(season)s::text AS season, f.gameweek, f.id AS fixture_id, ps.position,
        (f.home_team_id = ps.team_id) AS was_home,
        pcs.now_cost AS value, pcs.chance_of_playing_this_round,
        own.strength_attack_home, own.strength_attack_away,
        own.strength_defence_home, own.strength_defence_away,
        opp.strength_attack_home AS opp_strength_attack_home,
        opp.strength_attack_away AS opp_strength_attack_away,
        opp.strength_defence_home AS opp_strength_defence_home,
        opp.strength_defence_away AS opp_strength_defence_away,
        f.home_difficulty, f.away_difficulty
    FROM player_seasons ps
    JOIN fixtures f
        ON f.season = %(season)s AND f.gameweek BETWEEN %(start_gameweek)s AND %(end_gameweek)s
        AND (f.home_team_id = ps.team_id OR f.away_team_id = ps.team_id)
    JOIN team_seasons own ON own.id = ps.team_id
    JOIN team_seasons opp
        ON opp.id = CASE WHEN f.home_team_id = ps.team_id THEN f.away_team_id ELSE f.home_team_id END
    LEFT JOIN LATERAL (
        SELECT now_cost, chance_of_playing_this_round
        FROM player_current_status
        WHERE player_id = ps.player_id AND season = %(season)s
        ORDER BY as_of DESC LIMIT 1
    ) pcs ON true
    WHERE ps.season = %(season)s
"""


def load_predict_fixture_context(season: str, start_gameweek: int, end_gameweek: int) -> pd.DataFrame:
    """One row per (player, fixture) for every fixture in
    [start_gameweek, end_gameweek] — a plain join against every matching
    fixture, so a blank gameweek naturally contributes zero rows for that
    player and a double gameweek naturally contributes two, with no
    special-casing needed for either.
    """
    with get_connection() as conn:
        return pd.read_sql(
            _PREDICT_FIXTURE_CONTEXT_QUERY, conn,
            params={"season": season, "start_gameweek": start_gameweek, "end_gameweek": end_gameweek},
        )


def write_predictions(rows: list[dict], model_version: str) -> None:
    """Each row needs player_id/season/gameweek/predicted_points; confidence
    is optional (defaults to NULL) so this still works for any future caller
    that hasn't computed one.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        for row in rows:
            cur.execute(
                """
                INSERT INTO predictions (player_id, season, gameweek, predicted_points, confidence, model_version)
                VALUES (%(player_id)s, %(season)s, %(gameweek)s, %(predicted_points)s, %(confidence)s, %(model_version)s)
                ON CONFLICT (player_id, season, gameweek) DO UPDATE SET
                    predicted_points = EXCLUDED.predicted_points,
                    confidence = EXCLUDED.confidence,
                    model_version = EXCLUDED.model_version,
                    predicted_at = now()
                """,
                {"confidence": None, **row, "model_version": model_version},
            )


def record_model_run(model_version: str, training_seasons: list[str], hyperparams: dict,
                      validation_mae: float, validation_rmse: float, notes: str = "") -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO model_runs (model_version, training_seasons, hyperparams, validation_mae, validation_rmse, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (model_version) DO UPDATE SET
                training_seasons = EXCLUDED.training_seasons,
                hyperparams = EXCLUDED.hyperparams,
                validation_mae = EXCLUDED.validation_mae,
                validation_rmse = EXCLUDED.validation_rmse,
                notes = EXCLUDED.notes
            """,
            (model_version, json.dumps(training_seasons), json.dumps(hyperparams),
             validation_mae, validation_rmse, notes),
        )
