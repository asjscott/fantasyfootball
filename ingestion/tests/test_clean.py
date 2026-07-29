import pandas as pd

from ingestion.clean import clean_fixtures, clean_gameweek_stats, clean_players_raw, clean_teams


def test_clean_teams_renames_and_selects_columns():
    df = pd.DataFrame([{
        "code": 3, "id": 1, "name": "Arsenal", "strength": 4,
        "strength_attack_home": 1300, "strength_attack_away": 1250,
        "strength_defence_home": 1300, "strength_defence_away": 1280,
        "draw": 5, "loss": 3,  # extra columns should be dropped
    }])
    out = clean_teams(df, "2024-25")
    assert list(out["fpl_code"]) == [3]
    assert list(out["fpl_season_team_id"]) == [1]
    assert out["season"].iloc[0] == "2024-25"
    assert "draw" not in out.columns


def test_clean_players_raw_maps_element_type_to_position():
    df = pd.DataFrame([
        {"id": 10, "code": 100, "first_name": "Bukayo", "second_name": "Saka",
         "web_name": "Saka", "team": 1, "element_type": 3},
    ])
    out = clean_players_raw(df, "2024-25")
    assert out["position"].iloc[0] == "MID"
    assert out["fpl_season_element_id"].iloc[0] == 10


def test_clean_gameweek_stats_fills_missing_optional_columns():
    # Simulates a pre-2025-26 season file with no defensive_contribution column.
    df = pd.DataFrame([{
        "element": 10, "GW": 1, "fixture": 5, "team": "Arsenal", "opponent_team": 2,
        "was_home": True, "minutes": 90, "total_points": 8, "goals_scored": 1,
        "assists": 0, "clean_sheets": 1, "goals_conceded": 0, "own_goals": 0,
        "penalties_saved": 0, "penalties_missed": 0, "yellow_cards": 0, "red_cards": 0,
        "saves": 0, "bonus": 2, "bps": 30, "influence": 40.0, "creativity": 20.0,
        "threat": 30.0, "ict_index": 9.0, "starts": 1, "value": 85, "selected": 500000,
    }])
    out = clean_gameweek_stats(df, "2021-22")
    assert out["defensive_contribution"].isna().all()
    assert out["expected_goals"].isna().all()
    assert out["source"].iloc[0] == "github_historical"
    assert out["fpl_season_fixture_id"].iloc[0] == 5


def test_clean_fixtures_renames_home_away_columns():
    df = pd.DataFrame([{
        "id": 1, "code": 12345, "event": 1, "kickoff_time": "2024-08-16T19:00:00Z",
        "team_h": 1, "team_a": 2, "team_h_score": 2, "team_a_score": 0,
        "finished": True, "team_h_difficulty": 2, "team_a_difficulty": 4,
    }])
    out = clean_fixtures(df, "2024-25")
    assert out["fpl_season_fixture_id"].iloc[0] == 1
    assert out["home_difficulty"].iloc[0] == 2
