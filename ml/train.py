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

DEFAULT_HYPERPARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "random_state": 42,
}


def _mae(actual: pd.Series, predicted: pd.Series) -> float:
    return float(np.mean(np.abs(actual - predicted)))


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


def walk_forward_validate(
    features_df: pd.DataFrame, holdout_season: str, hyperparams: dict = DEFAULT_HYPERPARAMS,
    min_train_rows: int = 50,
) -> dict:
    """Expanding-window validation over every gameweek of `holdout_season`,
    training only on rows strictly before the gameweek being scored.
    """
    df = features_df.dropna(subset=[TARGET_COLUMN])
    train_pool = df[df["season"] != holdout_season]
    holdout = df[df["season"] == holdout_season].sort_values("gameweek")

    model_maes, model_rmses, baseline_maes = [], [], []

    for gw in sorted(holdout["gameweek"].unique()):
        train_data = pd.concat([train_pool, holdout[holdout["gameweek"] < gw]])
        test_data = holdout[holdout["gameweek"] == gw]
        if len(train_data) < min_train_rows or test_data.empty:
            continue

        model = _fit_model(train_data, hyperparams)
        preds = model.predict(test_data[FEATURE_COLUMNS])
        actual = test_data[TARGET_COLUMN]

        model_maes.append(_mae(actual, preds))
        model_rmses.append(_rmse(actual, preds))
        baseline_maes.append(_mae(actual, predict_baseline(test_data)))

    return {
        "model_mae": float(np.mean(model_maes)) if model_maes else None,
        "model_rmse": float(np.mean(model_rmses)) if model_rmses else None,
        "baseline_mae": float(np.mean(baseline_maes)) if baseline_maes else None,
        "gameweeks_evaluated": len(model_maes),
        "beats_baseline": bool(model_maes) and np.mean(model_maes) < np.mean(baseline_maes),
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
