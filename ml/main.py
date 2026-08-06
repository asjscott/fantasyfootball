from datetime import datetime, timezone

import typer

from ml.backtest import backtest_season
from ml.config import CURRENT_SEASON
from ml.data import load_training_frame, record_model_run
from ml.predict import predict_gameweeks
from ml.train import DEFAULT_HYPERPARAMS, train_and_evaluate

app = typer.Typer(help="FPL points-prediction ML CLI")

# Every complete historical season (mirrors ingestion.config.
# DEFAULT_HISTORICAL_SEASONS) plus the live CURRENT_SEASON. Real train/predict
# runs want 2025-26 included — it's the most recent complete season, and
# excluding it would be a genuine modeling mistake, not just a smaller
# default. It's only left out of DEFAULT_BACKTEST_TRAINING_SEASONS below,
# where it plays a different role: the season being replayed, not trained on.
DEFAULT_SEASONS = [
    "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26", CURRENT_SEASON,
]
DEFAULT_BACKTEST_TARGET_SEASON = "2025-26"
DEFAULT_BACKTEST_TRAINING_SEASONS = [
    "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25",
]


def _new_model_version() -> str:
    return "lgbm-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


@app.command()
def train(
    holdout_season: str = typer.Option(..., help="Season to walk-forward validate against"),
    seasons: str = typer.Option(",".join(DEFAULT_SEASONS), help="Comma-separated training seasons"),
) -> None:
    season_list = seasons.split(",")
    model_version = _new_model_version()

    typer.echo(f"Loading training data for {season_list}...")
    raw_df = load_training_frame(season_list)
    typer.echo(f"  {len(raw_df)} rows loaded")

    metrics = train_and_evaluate(raw_df, holdout_season, model_version)
    record_model_run(
        model_version, season_list, DEFAULT_HYPERPARAMS,
        metrics["model_mae"] or -1, metrics["model_rmse"] or -1,
        notes=(
            f"baseline_mae={metrics['baseline_mae']}, beats_baseline={metrics['beats_baseline']}, "
            f"model_played_mae={metrics['model_played_mae']}, model_unplayed_mae={metrics['model_unplayed_mae']}, "
            f"baseline_played_mae={metrics['baseline_played_mae']}, "
            f"beats_baseline_played={metrics['beats_baseline_played']}"
        ),
    )
    typer.echo(f"Trained {model_version}: {metrics}")


@app.command()
def predict(
    season: str = typer.Option(CURRENT_SEASON),
    gameweek: int = typer.Option(..., help="First gameweek to predict"),
    horizon: int = typer.Option(1, help="Number of gameweeks to predict, starting from --gameweek"),
    model_version: str = typer.Option(..., help="Model version saved by `train`"),
    seasons: str = typer.Option(",".join(DEFAULT_SEASONS), help="Comma-separated history seasons"),
) -> None:
    rows = predict_gameweeks(seasons.split(","), season, gameweek, horizon, model_version)
    typer.echo(f"Wrote {len(rows)} predictions for {season} GW{gameweek}-{gameweek + horizon - 1}")


@app.command("train-and-predict")
def train_and_predict(
    season: str = typer.Option(CURRENT_SEASON),
    gameweek: int = typer.Option(..., help="First gameweek to predict"),
    horizon: int = typer.Option(1, help="Number of gameweeks to predict, starting from --gameweek"),
    holdout_season: str = typer.Option(..., help="Season to walk-forward validate against"),
    seasons: str = typer.Option(",".join(DEFAULT_SEASONS), help="Comma-separated training/history seasons"),
) -> None:
    """The single command the weekly scheduled job calls."""
    season_list = seasons.split(",")
    model_version = _new_model_version()

    raw_df = load_training_frame(season_list)
    metrics = train_and_evaluate(raw_df, holdout_season, model_version)
    record_model_run(
        model_version, season_list, DEFAULT_HYPERPARAMS,
        metrics["model_mae"] or -1, metrics["model_rmse"] or -1,
        notes=(
            f"baseline_mae={metrics['baseline_mae']}, beats_baseline={metrics['beats_baseline']}, "
            f"model_played_mae={metrics['model_played_mae']}, model_unplayed_mae={metrics['model_unplayed_mae']}, "
            f"baseline_played_mae={metrics['baseline_played_mae']}, "
            f"beats_baseline_played={metrics['beats_baseline_played']}"
        ),
    )
    typer.echo(f"Trained {model_version}: {metrics}")

    rows = predict_gameweeks(season_list, season, gameweek, horizon, model_version)
    typer.echo(f"Wrote {len(rows)} predictions for {season} GW{gameweek}-{gameweek + horizon - 1}")


@app.command()
def backtest(
    target_season: str = typer.Option(DEFAULT_BACKTEST_TARGET_SEASON),
    training_seasons: str = typer.Option(
        ",".join(DEFAULT_BACKTEST_TRAINING_SEASONS), help="Comma-separated seasons strictly before target_season"
    ),
) -> None:
    """Replays target_season gameweek-by-gameweek, writing real predictions
    to Postgres for every gameweek so predicted-vs-actual can be reviewed.
    """
    typer.echo(f"Backtesting {target_season} against training seasons {training_seasons}...")
    summary = backtest_season(target_season, training_seasons.split(","))
    for row in summary:
        played_str = f"{row['played_mae']:.3f}" if row["played_mae"] is not None else "n/a"
        typer.echo(
            f"  GW{row['gameweek']:02d}: {row['players']} players, MAE={row['mae']:.3f} "
            f"(played MAE={played_str}, n={row['played_players']}; unplayed n={row['unplayed_players']})"
        )
    if summary:
        overall_mae = sum(r["mae"] * r["players"] for r in summary) / sum(r["players"] for r in summary)
        typer.echo(f"Backtest complete: {len(summary)} gameweeks, player-weighted MAE={overall_mae:.3f}")

        played_rows_total = sum(r["played_players"] for r in summary if r["played_mae"] is not None)
        if played_rows_total:
            overall_played_mae = sum(
                r["played_mae"] * r["played_players"] for r in summary if r["played_mae"] is not None
            ) / played_rows_total
            typer.echo(
                f"  Played-only player-weighted MAE={overall_played_mae:.3f} ({played_rows_total} played rows)"
            )


if __name__ == "__main__":
    app()
