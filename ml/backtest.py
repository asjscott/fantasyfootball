"""Replays a completed season gameweek-by-gameweek: for each gameweek, trains
fresh on strictly-prior data (same walk-forward discipline as
ml/train.py:walk_forward_validate) and persists the resulting predictions to
Postgres, so predicted vs. actual points can be compared per player per
gameweek once the season is already known.

This exists to test the full weekly-cycle mechanics (train -> predict -> API
-> frontend) against a real, complete season before the live 2026-27 season
starts, and to have a concrete accuracy baseline to improve on.
"""

from ml.data import load_training_frame, record_model_run, write_predictions
from ml.features import build_features
from ml.metrics import segmented_mae
from ml.train import DEFAULT_HYPERPARAMS, walk_forward_predict


def backtest_season(
    target_season: str, training_seasons: list[str], hyperparams: dict = DEFAULT_HYPERPARAMS,
) -> list[dict]:
    """`training_seasons` should be the seasons strictly before
    `target_season` — `target_season` itself is included in the query
    automatically so its own earlier gameweeks are available as training
    data for its later ones.
    """
    all_seasons = [s for s in training_seasons if s != target_season] + [target_season]
    raw_df = load_training_frame(all_seasons)
    features_df = build_features(raw_df)

    summary = []
    for gw, test_data, preds in walk_forward_predict(features_df, target_season, hyperparams):
        model_version = f"backtest-{target_season}-gw{int(gw):02d}"

        rows = [
            {
                "player_id": int(player_id),
                "season": target_season,
                "gameweek": int(gw),
                "predicted_points": round(float(points), 2),
            }
            for player_id, points in zip(test_data["player_id"], preds)
        ]
        write_predictions(rows, model_version)

        actual = test_data["total_points"]
        seg = segmented_mae(actual, preds, test_data["minutes"])
        record_model_run(
            model_version, all_seasons, hyperparams,
            validation_mae=seg["mae"], validation_rmse=float(((actual - preds) ** 2).mean() ** 0.5),
            notes=(
                f"backtest replay, gameweek {int(gw)}, {len(test_data)} players, "
                f"played_mae={seg['played_mae']}, played_rows={seg['played_rows']}, "
                f"unplayed_mae={seg['unplayed_mae']}, unplayed_rows={seg['unplayed_rows']}"
            ),
        )
        summary.append({
            "gameweek": int(gw), "players": len(test_data), "mae": seg["mae"],
            "played_mae": seg["played_mae"], "played_players": seg["played_rows"],
            "unplayed_mae": seg["unplayed_mae"], "unplayed_players": seg["unplayed_rows"],
        })

    return summary
