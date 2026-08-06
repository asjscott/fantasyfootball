"""Generates predictions for one or more upcoming gameweeks from a trained
model.

Scores one fixture at a time (not one gameweek at a time) so double
gameweeks (a team playing twice in one gameweek) and blank gameweeks (a
team not playing at all) are handled correctly, then groups back to one row
per (player, gameweek) — matching `predictions`' schema — by summing a
double-gameweek player's two fixture predictions rather than letting one
silently overwrite the other. See ml/README.md for how this bug was found.

Rolling-form features are computed once per player ("current form as of
now") and reused across every fixture in the horizon, rather than
recomputed per gameweek — this is what makes a multi-gameweek prediction
possible at all: `ml.features.build_features`'s shift-before-rolling logic
only ever looks at real history, so there's nothing to recompute for a
gameweek that hasn't been played yet.
"""

import numpy as np
import pandas as pd

from ml.data import load_predict_fixture_context, load_training_frame, write_predictions
from ml.features import FEATURE_COLUMNS, _ROLLING_SPECS, build_features
from ml.train import load_model

_FORM_COLUMNS = [feature_col for _source, feature_col, _window in _ROLLING_SPECS]

# Confidence lost per gameweek beyond the immediate next one — a heuristic,
# not a derived value. See ml/README.md's validation-against-backtest note.
_HORIZON_DECAY_PER_GAMEWEEK = 0.05


def compute_current_form(history_df: pd.DataFrame, season: str, as_of_gameweek: int) -> pd.DataFrame:
    """Each player's frozen rolling-form snapshot "as of now" — one row per
    player, form_* columns only. Reuses build_features (the single source
    of truth for how rolling form is computed) by appending one placeholder
    row per player at `as_of_gameweek`, which is guaranteed unplayed since
    it's the first gameweek being predicted, then keeping only the
    resulting form_* columns and discarding the placeholder's fixture-
    specific ones (those get attached per-fixture separately).
    """
    if history_df.empty:
        return pd.DataFrame(columns=["player_id", *_FORM_COLUMNS])

    player_ids = history_df["player_id"].unique()
    placeholder = pd.DataFrame({
        "player_id": player_ids,
        "season": season,
        "gameweek": as_of_gameweek,
        "position": "MID",
        "was_home": True,
        "home_difficulty": 0,
        "away_difficulty": 0,
        "opp_strength_attack_home": 0,
        "opp_strength_attack_away": 0,
        "opp_strength_defence_home": 0,
        "opp_strength_defence_away": 0,
    })
    combined = pd.concat([history_df, placeholder], ignore_index=True, sort=False)
    features_df = build_features(combined)
    snapshot = features_df[
        (features_df["season"] == season) & (features_df["gameweek"] == as_of_gameweek)
    ]
    return snapshot[["player_id", *_FORM_COLUMNS]].reset_index(drop=True)


def compute_confidence(row: pd.Series, horizon_distance: int) -> float:
    """Playing-time certainty (0.0-1.0) — how likely this player is to get
    real minutes in this gameweek. This is deliberately NOT a claim about
    points-prediction accuracy.

    An earlier version of this also folded in a "has recent points history"
    signal as a proxy for how much to trust the points estimate itself.
    Checked against the 2025-26 backtest's real predicted-vs-actual points
    (ml/validate_confidence.py) before shipping it, that version showed
    ~zero correlation with actual error (0.044, wrong sign) — FPL points
    have enough game-to-game randomness (bonus points, whether a shot goes
    in) that recent history/minutes don't meaningfully predict how close a
    single-match points estimate will land. It was dropped rather than
    shipped as a misleading "confidence" label.

    What *did* validate, on the same real data: recent minutes trend
    correlates 0.77 with actual future minutes, with a clean split across
    quartiles (~1 vs ~29 vs ~69 average actual minutes; P(60+ minutes) goes
    0.9% -> 27.8% -> 75.5%). That's what this function measures.
    """
    form_minutes_5 = row.get("form_minutes_5")
    # No prior-gameweek history at all (unlike the validated non-NaN case
    # above) isn't something this was validated against directly — treated
    # as "genuinely uncertain," not "definitely won't play."
    minutes_signal = 0.2 if pd.isna(form_minutes_5) else min(1.0, max(0.0, form_minutes_5) / 90.0)

    chance = row.get("chance_of_playing_this_round")
    playing_signal = 1.0 if pd.isna(chance) else max(0.0, min(1.0, chance / 100.0))

    decay = max(0.0, 1.0 - _HORIZON_DECAY_PER_GAMEWEEK * horizon_distance)
    return round(minutes_signal * playing_signal * decay, 3)


def _score_fixtures(
    history_df: pd.DataFrame, fixture_context: pd.DataFrame, model, season: str, start_gameweek: int
) -> pd.DataFrame:
    """One row per (player, fixture) with predicted_points + confidence."""
    form = compute_current_form(history_df, season, start_gameweek)
    merged = fixture_context.merge(form, on="player_id", how="left")

    merged["position"] = merged["position"].astype("category")
    merged["was_home"] = merged["was_home"].astype(bool)
    merged["own_difficulty"] = np.where(merged["was_home"], merged["home_difficulty"], merged["away_difficulty"])
    merged["opponent_attack_strength"] = np.where(
        merged["was_home"], merged["opp_strength_attack_away"], merged["opp_strength_attack_home"]
    )
    merged["opponent_defence_strength"] = np.where(
        merged["was_home"], merged["opp_strength_defence_away"], merged["opp_strength_defence_home"]
    )

    raw_preds = model.predict(merged[FEATURE_COLUMNS])
    chance = merged["chance_of_playing_this_round"].fillna(100) / 100.0
    merged["predicted_points"] = raw_preds * chance
    merged["confidence"] = [
        compute_confidence(row, int(row["gameweek"]) - start_gameweek) for _, row in merged.iterrows()
    ]
    return merged


def predict_gameweeks(
    history_seasons: list[str], season: str, start_gameweek: int, horizon: int, model_version: str
) -> list[dict]:
    """Predicts start_gameweek .. start_gameweek + horizon - 1. Loads
    history and the model once and reuses them across the whole horizon —
    same "load once, reuse across a loop" shape as
    ml.backtest.backtest_season — rather than reloading per gameweek.
    """
    end_gameweek = start_gameweek + horizon - 1
    fixture_context = load_predict_fixture_context(season, start_gameweek, end_gameweek)
    if fixture_context.empty:
        return []

    history_df = load_training_frame(history_seasons)
    model = load_model(model_version)
    scored = _score_fixtures(history_df, fixture_context, model, season, start_gameweek)
    rows = sum_fixture_predictions(scored, season)

    write_predictions(rows, model_version)
    return rows


def sum_fixture_predictions(scored: pd.DataFrame, season: str) -> list[dict]:
    """Collapses one-row-per-fixture predictions back to one row per
    (player, gameweek) — the shape `predictions` expects. A double-gameweek
    player's two fixture predictions are summed, not left to silently
    overwrite each other; a double-gameweek's overall confidence is capped
    by its weaker leg, not averaged up by its stronger one. Pulled out as
    its own pure function (no DB/model dependency) so the double-gameweek
    behavior is directly testable — see ml/tests/test_predict.py.
    """
    summed = scored.groupby(["player_id", "gameweek"], as_index=False).agg(
        predicted_points=("predicted_points", "sum"),
        confidence=("confidence", "min"),
    )
    return [
        {
            "player_id": int(r.player_id),
            "season": season,
            "gameweek": int(r.gameweek),
            "predicted_points": round(float(r.predicted_points), 2),
            "confidence": float(r.confidence),
        }
        for r in summed.itertuples()
    ]


def predict_gameweek(
    history_seasons: list[str], season: str, gameweek: int, model_version: str
) -> list[dict]:
    """Single-gameweek convenience wrapper — the CLI's `predict` command
    without an explicit --horizon still calls this.
    """
    return predict_gameweeks(history_seasons, season, gameweek, 1, model_version)
