import numpy as np
import pandas as pd

from ml.predict import _score_fixtures, sum_fixture_predictions

_HISTORY_BASE_ROW = {
    "position": "MID",
    "goals_scored": 0,
    "assists": 0,
    "bps": 20,
    "ict_index": 5.0,
    "value": 75,
    "expected_goals": 0.1,
    "expected_assists": 0.1,
    "defensive_contribution": np.nan,
    "strength_attack_home": 1300,
    "strength_attack_away": 1250,
    "strength_defence_home": 1300,
    "strength_defence_away": 1250,
    "opp_strength_attack_home": 1200,
    "opp_strength_attack_away": 1150,
    "opp_strength_defence_home": 1200,
    "opp_strength_defence_away": 1150,
    "home_difficulty": 3,
    "away_difficulty": 3,
    "kickoff_time": "2024-08-16T19:00:00Z",
}


def _history_rows(player_id: int, points_sequence: list[int]) -> list[dict]:
    return [
        {**_HISTORY_BASE_ROW, "player_id": player_id, "season": "2024-25", "gameweek": gw,
         "was_home": gw % 2 == 0, "minutes": 90, "total_points": points}
        for gw, points in enumerate(points_sequence, start=1)
    ]


class _FakeModel:
    """Predicts own_difficulty * 2 — deterministic and distinguishable per
    fixture, so a double-gameweek player's two fixture predictions can be
    told apart and their sum checked exactly.
    """

    def predict(self, X):
        return (X["own_difficulty"].to_numpy(dtype=float) * 2.0)


def _double_gameweek_fixture_context(player_id: int, gameweek: int) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "player_id": player_id, "season": "2024-25", "gameweek": gameweek, "fixture_id": 1001,
            "position": "MID", "was_home": True, "value": 75, "chance_of_playing_this_round": np.nan,
            "home_difficulty": 2, "away_difficulty": 4,
            "opp_strength_attack_home": 1200, "opp_strength_attack_away": 1150,
            "opp_strength_defence_home": 1200, "opp_strength_defence_away": 1150,
        },
        {
            "player_id": player_id, "season": "2024-25", "gameweek": gameweek, "fixture_id": 1002,
            "position": "MID", "was_home": False, "value": 75, "chance_of_playing_this_round": np.nan,
            "home_difficulty": 3, "away_difficulty": 5,
            "opp_strength_attack_home": 1300, "opp_strength_attack_away": 1250,
            "opp_strength_defence_home": 1300, "opp_strength_defence_away": 1250,
        },
    ])


def test_double_gameweek_predictions_sum_instead_of_overwriting():
    history_df = pd.DataFrame(_history_rows(player_id=1, points_sequence=[2, 4, 6, 8, 10]))
    fixture_context = _double_gameweek_fixture_context(player_id=1, gameweek=10)

    scored = _score_fixtures(history_df, fixture_context, _FakeModel(), season="2024-25", start_gameweek=10)

    # Two distinct fixture-level predictions: own_difficulty is 2 (home leg)
    # and 5 (away leg, away_difficulty since was_home=False) -> 4.0 and 10.0.
    assert sorted(scored["predicted_points"].tolist()) == [4.0, 10.0]
    assert len(scored) == 2  # one row per fixture, not collapsed yet

    rows = sum_fixture_predictions(scored, season="2024-25")

    assert len(rows) == 1  # collapsed to one row per (player, gameweek)
    assert rows[0]["player_id"] == 1
    assert rows[0]["gameweek"] == 10
    assert rows[0]["predicted_points"] == 14.0  # 4.0 + 10.0, not one overwriting the other


def test_double_gameweek_confidence_is_capped_by_weaker_leg():
    history_df = pd.DataFrame(_history_rows(player_id=1, points_sequence=[2, 4, 6, 8, 10]))
    fixture_context = _double_gameweek_fixture_context(player_id=1, gameweek=10)
    # Make the away leg a genuine injury doubt — should drag the combined
    # confidence down, not get averaged away by the fit home leg.
    fixture_context.loc[fixture_context["fixture_id"] == 1002, "chance_of_playing_this_round"] = 25

    scored = _score_fixtures(history_df, fixture_context, _FakeModel(), season="2024-25", start_gameweek=10)
    rows = sum_fixture_predictions(scored, season="2024-25")

    home_leg_confidence = scored.loc[scored["fixture_id"] == 1001, "confidence"].iloc[0]
    away_leg_confidence = scored.loc[scored["fixture_id"] == 1002, "confidence"].iloc[0]
    assert away_leg_confidence < home_leg_confidence
    assert rows[0]["confidence"] == away_leg_confidence  # min(), not mean()


def test_blank_gameweek_contributes_no_rows():
    history_df = pd.DataFrame(_history_rows(player_id=1, points_sequence=[2, 4, 6, 8, 10]))
    fixture_context = pd.DataFrame(columns=[
        "player_id", "season", "gameweek", "fixture_id", "position", "was_home", "value",
        "chance_of_playing_this_round", "home_difficulty", "away_difficulty",
        "opp_strength_attack_home", "opp_strength_attack_away",
        "opp_strength_defence_home", "opp_strength_defence_away",
    ])

    scored = _score_fixtures(history_df, fixture_context, _FakeModel(), season="2024-25", start_gameweek=10)
    assert scored.empty
