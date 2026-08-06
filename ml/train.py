"""Walk-forward validated LightGBM training. Explicitly does NOT use k-fold /
random-shuffle cross-validation: that leaks future gameweeks into rolling-
average features and would give a falsely optimistic score for what is,
at inference time, a strictly-forward prediction task.
"""

import os

import lightgbm as lgb
import numpy as np
import pandas as pd

from ml.baseline import predict_baseline
from ml.config import ARTIFACTS_DIR
from ml.features import CATEGORICAL_COLUMNS, FEATURE_COLUMNS, TARGET_COLUMN, build_features
from ml.metrics import segmented_mae

DEFAULT_HYPERPARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "random_state": 42,
}


def _rmse(actual: pd.Series, predicted: pd.Series) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def _fit_model(train_df: pd.DataFrame, hyperparams: dict) -> lgb.LGBMRegressor:
    model = lgb.LGBMRegressor(**hyperparams, verbosity=-1)
    model.fit(
        train_df[FEATURE_COLUMNS],
        train_df[TARGET_COLUMN],
        categorical_feature=CATEGORICAL_COLUMNS,
    )
    return model


def walk_forward_predict(
    features_df: pd.DataFrame, holdout_season: str, hyperparams: dict = DEFAULT_HYPERPARAMS,
    min_train_rows: int = 50,
):
    """Expanding-window walk-forward over every gameweek of `holdout_season`,
    training fresh each time on rows strictly before the gameweek being
    scored. Yields (gameweek, test_data, predictions) per gameweek.

    Shared by `walk_forward_validate` (aggregate MAE/RMSE for model
    selection) and `ml/backtest.py` (persists the actual per-player
    predictions for a full historical season replay) — same walk-forward
    discipline, two different uses of the result.
    """
    df = features_df.dropna(subset=[TARGET_COLUMN])
    train_pool = df[df["season"] != holdout_season]
    holdout = df[df["season"] == holdout_season].sort_values("gameweek")

    for gw in sorted(holdout["gameweek"].unique()):
        train_data = pd.concat([train_pool, holdout[holdout["gameweek"] < gw]])
        test_data = holdout[holdout["gameweek"] == gw]
        if len(train_data) < min_train_rows or test_data.empty:
            continue

        model = _fit_model(train_data, hyperparams)
        preds = model.predict(test_data[FEATURE_COLUMNS])
        yield gw, test_data, preds


def walk_forward_validate(
    features_df: pd.DataFrame, holdout_season: str, hyperparams: dict = DEFAULT_HYPERPARAMS,
    min_train_rows: int = 50,
) -> dict:
    model_rmses = []
    model_segs, baseline_segs = [], []

    for _gw, test_data, preds in walk_forward_predict(features_df, holdout_season, hyperparams, min_train_rows):
        actual = test_data[TARGET_COLUMN]
        minutes = test_data["minutes"]
        model_rmses.append(_rmse(actual, preds))
        model_segs.append(segmented_mae(actual, preds, minutes))
        baseline_segs.append(segmented_mae(actual, predict_baseline(test_data), minutes))

    def _avg(segs, key):
        vals = [s[key] for s in segs if s[key] is not None]
        return float(np.mean(vals)) if vals else None

    model_mae = _avg(model_segs, "mae")
    model_played_mae = _avg(model_segs, "played_mae")
    model_unplayed_mae = _avg(model_segs, "unplayed_mae")
    baseline_mae = _avg(baseline_segs, "mae")
    baseline_played_mae = _avg(baseline_segs, "played_mae")

    return {
        "model_mae": model_mae,
        "model_rmse": float(np.mean(model_rmses)) if model_rmses else None,
        "model_played_mae": model_played_mae,
        "model_unplayed_mae": model_unplayed_mae,
        "baseline_mae": baseline_mae,
        "baseline_played_mae": baseline_played_mae,
        "played_rows": sum(s["played_rows"] for s in model_segs),
        "unplayed_rows": sum(s["unplayed_rows"] for s in model_segs),
        "gameweeks_evaluated": len(model_segs),
        "beats_baseline": bool(model_segs) and model_mae is not None and baseline_mae is not None
        and model_mae < baseline_mae,
        "beats_baseline_played": (
            model_played_mae is not None and baseline_played_mae is not None
            and model_played_mae < baseline_played_mae
        ),
    }


def train_final_model(
    features_df: pd.DataFrame, hyperparams: dict = DEFAULT_HYPERPARAMS
) -> lgb.LGBMRegressor:
    df = features_df.dropna(subset=[TARGET_COLUMN])
    return _fit_model(df, hyperparams)


def save_model(model: lgb.LGBMRegressor, model_version: str) -> str:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    path = os.path.join(ARTIFACTS_DIR, f"{model_version}.txt")
    model.booster_.save_model(path)
    return path


def load_model(model_version: str) -> lgb.Booster:
    path = os.path.join(ARTIFACTS_DIR, f"{model_version}.txt")
    return lgb.Booster(model_file=path)


def train_and_evaluate(raw_df: pd.DataFrame, holdout_season: str, model_version: str) -> dict:
    """Full pipeline: features -> walk-forward validation on the holdout
    season -> final model trained on everything -> saved to disk.
    Returns validation metrics; callers persist them via ml.data.record_model_run.
    """
    features_df = build_features(raw_df)
    metrics = walk_forward_validate(features_df, holdout_season)

    final_model = train_final_model(features_df)
    save_model(final_model, model_version)

    return metrics
