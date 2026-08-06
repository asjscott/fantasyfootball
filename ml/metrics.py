"""Evaluation-only metrics. Segments MAE by whether the player actually
played (minutes > 0) that gameweek, because ~61% of player_gameweek_stats
rows are unused subs/injured/not-in-squad players with 0 minutes — a plain
blended MAE over all rows is dominated by "predict near-zero for a player
who didn't play," which is a much easier task than predicting points for
players who did play, and hides the real error where it matters. This does
NOT change what the model is trained on — it's purely a reporting split.
"""

import numpy as np


def segmented_mae(actual, predicted, minutes) -> dict:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    minutes = np.asarray(minutes, dtype=float)
    abs_err = np.abs(actual - predicted)
    played = minutes > 0

    def _mean_or_none(mask):
        return float(abs_err[mask].mean()) if mask.any() else None

    return {
        "mae": float(abs_err.mean()) if len(abs_err) else None,
        "played_mae": _mean_or_none(played),
        "unplayed_mae": _mean_or_none(~played),
        "played_rows": int(played.sum()),
        "unplayed_rows": int((~played).sum()),
    }
