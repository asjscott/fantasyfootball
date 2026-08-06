"""One-off diagnostic, not part of the training/prediction pipeline: checks
whether ml.predict.compute_confidence's playing-time-certainty score
actually predicts real playing time, using the 2025-26 season's already-
known actual minutes. Run manually when tuning the heuristic — not wired
into ml/main.py's CLI or any scheduled job.

This is the second version of this script. The first validated an earlier
confidence design (which also folded in a points-history signal, framed as
"how much to trust the points estimate") against real predicted-vs-actual
points error from the 2025-26 backtest, and found ~zero correlation
(0.044, wrong sign) — FPL points have enough game-to-game randomness that
recent history doesn't meaningfully predict single-match points error.
That framing was dropped. This script validates the playing-time-certainty
reframing that replaced it, which is a genuinely different empirical claim
("will they get minutes", not "how accurate is the points number").
"""

import pandas as pd

from ml.data import load_training_frame
from ml.features import build_features
from ml.predict import compute_confidence

SEASON = "2025-26"


def main() -> None:
    raw_df = load_training_frame([SEASON])
    features_df = build_features(raw_df).dropna(subset=["form_minutes_5"]).copy()

    # chance_of_playing_this_round doesn't exist for historical rows (see
    # ml/README.md) so this validates the minutes-trend signal in isolation
    # — the part of compute_confidence that's checkable against this data.
    features_df["chance_of_playing_this_round"] = float("nan")
    features_df["confidence"] = features_df.apply(lambda row: compute_confidence(row, 0), axis=1)
    features_df["played_60plus"] = (features_df["minutes"] >= 60).astype(int)

    print(f"Playing-time-certainty validation for {SEASON} ({len(features_df)} rows):\n")

    print(f"Correlation(confidence, actual minutes): {features_df['confidence'].corr(features_df['minutes']):.4f}")

    features_df["bucket"] = pd.qcut(features_df["confidence"], 4, duplicates="drop")
    print("\nActual minutes by confidence quartile:")
    print(features_df.groupby("bucket")["minutes"].agg(["mean", "count"]))

    print("\nP(played 60+ minutes) by confidence quartile:")
    print(features_df.groupby("bucket")["played_60plus"].mean())


if __name__ == "__main__":
    main()
