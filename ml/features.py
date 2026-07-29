"""Leakage-safe feature engineering: every rolling window is computed on
values strictly BEFORE the target gameweek (`.shift(1)` before `.rolling()`),
so a row's features never see that row's own outcome.
"""

import numpy as np
import pandas as pd

TARGET_COLUMN = "total_points"
CATEGORICAL_COLUMNS = ["position"]
FEATURE_COLUMNS = [
    "position",
    "was_home",
    "value",
    "form_points_3",
    "form_points_5",
    "form_points_10",
    "form_minutes_3",
    "form_minutes_5",
    "form_goals_5",
    "form_assists_5",
    "form_bps_5",
    "form_ict_5",
    "own_difficulty",
    "opponent_attack_strength",
    "opponent_defence_strength",
]

_ROLLING_SPECS = [
    ("total_points", "form_points_3", 3),
    ("total_points", "form_points_5", 5),
    ("total_points", "form_points_10", 10),
    ("minutes", "form_minutes_3", 3),
    ("minutes", "form_minutes_5", 5),
    ("goals_scored", "form_goals_5", 5),
    ("assists", "form_assists_5", 5),
    ("bps", "form_bps_5", 5),
    ("ict_index", "form_ict_5", 5),
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """`df` must be sorted-able by (player_id, season, gameweek) and contain
    the raw columns from `ml.data.load_training_frame`. Returns a copy with
    feature columns appended.
    """
    out = df.sort_values(["player_id", "season", "gameweek"]).copy()

    for source_col, feature_col, window in _ROLLING_SPECS:
        out[feature_col] = out.groupby("player_id", sort=False)[source_col].transform(
            lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean()
        )

    out["own_difficulty"] = np.where(out["was_home"], out["home_difficulty"], out["away_difficulty"])
    out["opponent_attack_strength"] = np.where(
        out["was_home"], out["opp_strength_attack_away"], out["opp_strength_attack_home"]
    )
    out["opponent_defence_strength"] = np.where(
        out["was_home"], out["opp_strength_defence_away"], out["opp_strength_defence_home"]
    )

    out["position"] = out["position"].astype("category")
    out["was_home"] = out["was_home"].astype(bool)

    return out
