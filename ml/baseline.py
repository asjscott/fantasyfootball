"""Naive heuristic: predict a player's next points as their trailing 5-gameweek
average. Every trained model must beat this on held-out data to be trusted —
see ml/train.py.
"""

import pandas as pd


def predict_baseline(features_df: pd.DataFrame) -> pd.Series:
    return features_df["form_points_5"].fillna(0)
