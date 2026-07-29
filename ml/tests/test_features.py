import numpy as np
import pandas as pd

from ml.features import build_features

_BASE_ROW = {
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


def _rows(player_id: int, points_sequence: list[int]) -> list[dict]:
    return [
        {**_BASE_ROW, "player_id": player_id, "season": "2024-25", "gameweek": gw,
         "was_home": gw % 2 == 0, "minutes": 90, "total_points": points}
        for gw, points in enumerate(points_sequence, start=1)
    ]


def test_rolling_form_excludes_current_gameweek():
    df = pd.DataFrame(_rows(player_id=1, points_sequence=[2, 4, 6, 8, 10]))
    out = build_features(df).set_index("gameweek")

    assert pd.isna(out.loc[1, "form_points_3"])  # no prior gameweeks yet
    assert out.loc[2, "form_points_3"] == 2  # mean of [2]
    assert out.loc[3, "form_points_3"] == 3  # mean of [2, 4]
    assert out.loc[4, "form_points_3"] == 4  # mean of [2, 4, 6] — NOT including gw4's own 8
    assert out.loc[5, "form_points_3"] == 6  # mean of [4, 6, 8]


def test_rolling_form_does_not_cross_players():
    df = pd.DataFrame(
        _rows(player_id=1, points_sequence=[10, 10, 10])
        + _rows(player_id=2, points_sequence=[0, 0, 0])
    )
    out = build_features(df)

    player_2_gw3 = out[(out["player_id"] == 2) & (out["gameweek"] == 3)].iloc[0]
    assert player_2_gw3["form_points_3"] == 0  # unaffected by player 1's high scores


def test_own_and_opponent_strength_use_home_away_split():
    df = pd.DataFrame(_rows(player_id=1, points_sequence=[5]))
    df.loc[0, "was_home"] = True
    df.loc[0, "home_difficulty"] = 2
    df.loc[0, "away_difficulty"] = 4
    out = build_features(df)

    assert out.iloc[0]["own_difficulty"] == 2  # was_home=True -> home_difficulty
