"""Orchestrates fetch -> clean -> resolve -> upsert for one season or one live snapshot.

Idempotent: every write is an upsert keyed on the natural keys defined in the
schema, so re-running for the same season/gameweek is always safe.
"""

from datetime import datetime, timezone

import pandas as pd

from ingestion import fetch
from ingestion.clean import clean_fixtures, clean_gameweek_stats, clean_players_raw, clean_teams
from ingestion.config import CURRENT_SEASON
from ingestion.db import get_connection
from ingestion.resolve_players import resolve_player, upsert_player_season, upsert_team, upsert_team_season

_POSITION_BY_ELEMENT_TYPE = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def _record_ingestion_run(cur, source: str, season: str | None, started_at: datetime,
                           rows_loaded: int, status: str, error_message: str | None = None) -> None:
    cur.execute(
        """
        INSERT INTO ingestion_runs (source, season, started_at, finished_at, rows_loaded, status, error_message)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (source, season, started_at, datetime.now(timezone.utc), rows_loaded, status, error_message),
    )


def load_historical_season(season: str) -> int:
    started_at = datetime.now(timezone.utc)
    rows_loaded = 0

    teams_df = clean_teams(fetch.fetch_historical_csv(season, "teams"), season)
    players_df = clean_players_raw(fetch.fetch_historical_csv(season, "players_raw"), season)
    fixtures_df = clean_fixtures(fetch.fetch_historical_csv(season, "fixtures"), season)
    gw_stats_df = clean_gameweek_stats(fetch.fetch_historical_csv(season, "merged_gw"), season)

    with get_connection() as conn:
        cur = conn.cursor()
        try:
            team_season_by_fpl_id: dict[int, int] = {}
            for row in teams_df.itertuples():
                team_id = upsert_team(cur, row.fpl_code, row.name)
                team_season_id = upsert_team_season(
                    cur, team_id, season, row.fpl_season_team_id, row.strength,
                    row.strength_attack_home, row.strength_attack_away,
                    row.strength_defence_home, row.strength_defence_away,
                )
                team_season_by_fpl_id[row.fpl_season_team_id] = team_season_id

            player_id_by_fpl_element: dict[int, int] = {}
            player_team_season_by_fpl_element: dict[int, int] = {}
            for row in players_df.itertuples():
                fpl_code = None if pd_isna(row.fpl_code) else int(row.fpl_code)
                player_id = resolve_player(
                    cur, season, row.fpl_season_element_id, fpl_code,
                    row.first_name, row.second_name, row.web_name,
                )
                team_season_id = team_season_by_fpl_id.get(row.fpl_season_team_id)
                upsert_player_season(
                    cur, player_id, season, row.fpl_season_element_id, team_season_id, row.position
                )
                player_id_by_fpl_element[row.fpl_season_element_id] = player_id
                player_team_season_by_fpl_element[row.fpl_season_element_id] = team_season_id

            fixture_id_by_fpl_season_id: dict[int, int] = {}
            for row in fixtures_df.itertuples():
                home_team_season_id = team_season_by_fpl_id.get(row.fpl_season_home_team_id)
                away_team_season_id = team_season_by_fpl_id.get(row.fpl_season_away_team_id)
                if home_team_season_id is None or away_team_season_id is None:
                    continue
                cur.execute(
                    """
                    INSERT INTO fixtures (
                        season, fpl_fixture_code, gameweek, kickoff_time,
                        home_team_id, away_team_id, home_score, away_score,
                        finished, home_difficulty, away_difficulty
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (fpl_fixture_code) DO UPDATE SET
                        gameweek = EXCLUDED.gameweek,
                        kickoff_time = EXCLUDED.kickoff_time,
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score,
                        finished = EXCLUDED.finished,
                        home_difficulty = EXCLUDED.home_difficulty,
                        away_difficulty = EXCLUDED.away_difficulty
                    RETURNING id
                    """,
                    (season, row.fpl_fixture_code, none_if_nan(row.gameweek), none_if_nan(row.kickoff_time),
                     home_team_season_id, away_team_season_id, none_if_nan(row.home_score),
                     none_if_nan(row.away_score), bool(row.finished), none_if_nan(row.home_difficulty),
                     none_if_nan(row.away_difficulty)),
                )
                fixture_id_by_fpl_season_id[row.fpl_season_fixture_id] = cur.fetchone()[0]

            for row in gw_stats_df.itertuples():
                player_id = player_id_by_fpl_element.get(row.fpl_season_element_id)
                if player_id is None:
                    continue
                # NOTE: team_id is the player's season-long team, not resolved
                # per-gameweek — acceptable for v1 since mid-season transfers
                # are rare relative to model signal.
                team_season_id = player_team_season_by_fpl_element.get(row.fpl_season_element_id)
                opponent_team_season_id = team_season_by_fpl_id.get(row.fpl_season_opponent_team_id)
                fixture_id = fixture_id_by_fpl_season_id.get(row.fpl_season_fixture_id)

                cur.execute(
                    """
                    INSERT INTO player_gameweek_stats (
                        player_id, season, gameweek, fixture_id, team_id, opponent_team_id,
                        was_home, minutes, total_points, goals_scored, assists, clean_sheets,
                        goals_conceded, own_goals, penalties_saved, penalties_missed,
                        yellow_cards, red_cards, saves, bonus, bps, influence, creativity,
                        threat, ict_index, starts, expected_goals, expected_assists,
                        expected_goal_involvements, expected_goals_conceded,
                        defensive_contribution, value, selected, source
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (player_id, season, gameweek) DO UPDATE SET
                        minutes = EXCLUDED.minutes,
                        total_points = EXCLUDED.total_points,
                        goals_scored = EXCLUDED.goals_scored,
                        assists = EXCLUDED.assists,
                        bonus = EXCLUDED.bonus,
                        bps = EXCLUDED.bps,
                        value = EXCLUDED.value,
                        selected = EXCLUDED.selected
                    """,
                    (player_id, season, row.gameweek, fixture_id, team_season_id, opponent_team_season_id,
                     row.was_home, none_if_nan(row.minutes), none_if_nan(row.total_points),
                     none_if_nan(row.goals_scored), none_if_nan(row.assists), none_if_nan(row.clean_sheets),
                     none_if_nan(row.goals_conceded), none_if_nan(row.own_goals),
                     none_if_nan(row.penalties_saved), none_if_nan(row.penalties_missed),
                     none_if_nan(row.yellow_cards), none_if_nan(row.red_cards), none_if_nan(row.saves),
                     none_if_nan(row.bonus), none_if_nan(row.bps), none_if_nan(row.influence),
                     none_if_nan(row.creativity), none_if_nan(row.threat), none_if_nan(row.ict_index),
                     none_if_nan(row.starts), none_if_nan(row.expected_goals),
                     none_if_nan(row.expected_assists), none_if_nan(row.expected_goal_involvements),
                     none_if_nan(row.expected_goals_conceded), none_if_nan(row.defensive_contribution),
                     none_if_nan(row.value), none_if_nan(row.selected), row.source),
                )
                rows_loaded += 1

            _record_ingestion_run(cur, "github_historical", season, started_at, rows_loaded, "success")
        except Exception as exc:
            _record_ingestion_run(cur, "github_historical", season, started_at, rows_loaded, "failed", str(exc))
            raise

    return rows_loaded


def load_live_snapshot(season: str = CURRENT_SEASON) -> int:
    """Pulls current squads, prices, injury status and fixtures from the live
    FPL API. Does not touch historical seasons. Safe to run repeatedly —
    every write is an upsert, and player_current_status is append-only so
    each run adds one more snapshot row per player rather than overwriting.
    """
    started_at = datetime.now(timezone.utc)
    rows_loaded = 0

    bootstrap = fetch.fetch_bootstrap_static()
    live_fixtures = fetch.fetch_live_fixtures()

    with get_connection() as conn:
        cur = conn.cursor()
        try:
            team_season_by_fpl_id: dict[int, int] = {}
            for team in bootstrap["teams"]:
                team_id = upsert_team(cur, team["code"], team["name"])
                team_season_id = upsert_team_season(
                    cur, team_id, season, team["id"], team.get("strength"),
                    team.get("strength_attack_home"), team.get("strength_attack_away"),
                    team.get("strength_defence_home"), team.get("strength_defence_away"),
                )
                team_season_by_fpl_id[team["id"]] = team_season_id

            for element in bootstrap["elements"]:
                player_id = resolve_player(
                    cur, season, element["id"], element["code"],
                    element["first_name"], element["second_name"], element["web_name"],
                )
                team_season_id = team_season_by_fpl_id.get(element["team"])
                position = _POSITION_BY_ELEMENT_TYPE.get(element["element_type"], "UNK")
                upsert_player_season(cur, player_id, season, element["id"], team_season_id, position)

                cur.execute(
                    """
                    INSERT INTO player_current_status (
                        player_id, season, as_of, team_id, position, now_cost, status,
                        chance_of_playing_this_round, chance_of_playing_next_round, news,
                        form, selected_by_percent, ep_this, ep_next
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (player_id, season, started_at, team_season_id, position, element.get("now_cost"),
                     element.get("status"), element.get("chance_of_playing_this_round"),
                     element.get("chance_of_playing_next_round"), element.get("news"),
                     element.get("form"), element.get("selected_by_percent"),
                     element.get("ep_this"), element.get("ep_next")),
                )
                rows_loaded += 1

            for fx in live_fixtures:
                home_team_season_id = team_season_by_fpl_id.get(fx["team_h"])
                away_team_season_id = team_season_by_fpl_id.get(fx["team_a"])
                if home_team_season_id is None or away_team_season_id is None:
                    continue
                cur.execute(
                    """
                    INSERT INTO fixtures (
                        season, fpl_fixture_code, gameweek, kickoff_time,
                        home_team_id, away_team_id, home_score, away_score,
                        finished, home_difficulty, away_difficulty
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (fpl_fixture_code) DO UPDATE SET
                        gameweek = EXCLUDED.gameweek,
                        kickoff_time = EXCLUDED.kickoff_time,
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score,
                        finished = EXCLUDED.finished,
                        home_difficulty = EXCLUDED.home_difficulty,
                        away_difficulty = EXCLUDED.away_difficulty
                    """,
                    (season, fx["code"], fx.get("event"), fx.get("kickoff_time"),
                     home_team_season_id, away_team_season_id, fx.get("team_h_score"),
                     fx.get("team_a_score"), bool(fx.get("finished")), fx.get("team_h_difficulty"),
                     fx.get("team_a_difficulty")),
                )

            _record_ingestion_run(cur, "live_api", season, started_at, rows_loaded, "success")
        except Exception as exc:
            _record_ingestion_run(cur, "live_api", season, started_at, rows_loaded, "failed", str(exc))
            raise

    return rows_loaded


def pd_isna(value) -> bool:
    return bool(pd.isna(value))


def none_if_nan(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value
