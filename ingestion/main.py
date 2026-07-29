import typer

from ingestion.config import CURRENT_SEASON, DEFAULT_HISTORICAL_SEASONS
from ingestion.load import load_historical_season, load_live_snapshot

app = typer.Typer(help="FPL data ingestion CLI")


@app.command("ingest-historical")
def ingest_historical(
    season: str = typer.Option(None, help="e.g. 2024-25. Omit to backfill all default seasons."),
    all_seasons: bool = typer.Option(False, "--all-seasons", help="Backfill every default season."),
) -> None:
    """One-off/rare: backfill training data from the GitHub historical repo."""
    seasons = DEFAULT_HISTORICAL_SEASONS if all_seasons or not season else [season]
    for s in seasons:
        typer.echo(f"Ingesting historical season {s}...")
        rows = load_historical_season(s)
        typer.echo(f"  {rows} gameweek-stat rows loaded for {s}")


@app.command("ingest-live-snapshot")
def ingest_live_snapshot(
    season: str = typer.Option(CURRENT_SEASON, help="Current season, e.g. 2026-27"),
) -> None:
    """Weekly: pull current squads/prices/status/fixtures from the live FPL API."""
    typer.echo(f"Ingesting live snapshot for {season}...")
    rows = load_live_snapshot(season)
    typer.echo(f"  {rows} player status rows loaded")


if __name__ == "__main__":
    app()
