"""Generates next-gameweek predictions from a trained model.

Current form (rolling averages) is computed by appending the upcoming
fixture's context as a row with the target unknown, then reusing
`build_features`'s shift(1)-before-rolling logic — this guarantees the
prediction row's form features are computed exactly the same way training
rows were, with no special-cased duplicate logic.
"""

import pandas as pd

from ml.data import load_predict_context, load_training_frame, write_predictions
from ml.features import FEATURE_COLUMNS, build_features
from ml.train import load_model


def build_predict_frame(history_seasons: list[str], season: str, gameweek: int) -> pd.DataFrame:
    history_df = load_training_frame(history_seasons)
    context_df = load_predict_context(season, gameweek)

    combined = pd.concat([history_df, context_df], ignore_index=True, sort=False)
    features_df = build_features(combined)

    predict_rows = features_df[
        (features_df["season"] == season) & (features_df["gameweek"] == gameweek)
    ].copy()
    predict_rows["chance_of_playing_this_round"] = context_df.set_index("player_id")[
        "chance_of_playing_this_round"
    ].reindex(predict_rows["player_id"]).values
    return predict_rows


def predict_gameweek(
    history_seasons: list[str], season: str, gameweek: int, model_version: str
) -> list[dict]:
    predict_rows = build_predict_frame(history_seasons, season, gameweek)
    if predict_rows.empty:
        return []

    model = load_model(model_version)
    raw_preds = model.predict(predict_rows[FEATURE_COLUMNS])

    # Scale down predictions for players who are doubtful/injured so their
    # rank reflects real selection risk, not just raw model output.
    chance = predict_rows["chance_of_playing_this_round"].fillna(100) / 100.0
    scaled_preds = raw_preds * chance

    rows = [
        {
            "player_id": int(player_id),
            "season": season,
            "gameweek": gameweek,
            "predicted_points": round(float(points), 2),
        }
        for player_id, points in zip(predict_rows["player_id"], scaled_preds)
    ]
    write_predictions(rows, model_version)
    return rows
