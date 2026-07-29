# /ml — Prediction model

Trains a model to predict FPL points per player per gameweek, and generates predictions for an upcoming gameweek. Reads exclusively from Postgres (populated by `/ingestion`) and writes predictions back to Postgres — no network calls happen here.

## The core idea: leakage-safe rolling features

The hardest thing to get right in a "predict the future from the past" problem is making sure a row's features don't secretly contain information from its own future. `features.py` is built around one rule: every rolling-average feature (`form_points_3`, `form_minutes_5`, etc.) is computed with `.shift(1)` **before** `.rolling()` — meaning gameweek 10's "form" is the average of gameweeks 7-9, never including gameweek 10 itself. This is tested directly in `tests/test_features.py::test_rolling_form_excludes_current_gameweek`, which asserts the exact numbers a hand-computed rolling average should produce.

Why this matters: if you get this wrong, a model trained with information leakage will look great in validation (because it's partially just reading the answer) and then perform badly on real future gameweeks (where that leaked information doesn't exist yet). It's the single easiest way to fool yourself in this kind of project.

## Model choice and validation

- **LightGBM regression**, `position` as a categorical feature — one model, not four separate position-specific models. Simpler pipeline; if later analysis shows the model is systematically biased by position, that's a reasonable v2 to build.
- **Walk-forward validation only** (`train.py::walk_forward_validate`) — never k-fold/random-shuffle cross-validation. This is deliberate: k-fold would let the model train on gameweek 20 and validate on gameweek 15, which is information from the future leaking into training in a different way than the feature-leakage issue above. Walk-forward always trains on gameweeks strictly *before* the one being scored, which matches how the model will actually be used.
- **A naive baseline is always computed alongside the model** (`baseline.py` — literally just "predict their trailing 5-gameweek average") and logged next to the model's own MAE in `model_runs.notes`. This exists so a broken or overfit model gets caught by "did it actually beat the dumb heuristic," rather than trusting a metric that looks reasonable in isolation.

## Prediction pipeline

`predict.py::build_predict_frame` is the trickiest piece of code in this directory, worth understanding: to predict an upcoming gameweek, we need that gameweek's *rolling form* features, which depend on gameweeks that **have already happened**. Rather than duplicating the rolling-window logic, it appends a synthetic row for the upcoming fixture (known: opponent, home/away, difficulty; unknown: the target `total_points`) onto the real history, and reuses the exact same `build_features` function used for training. The shift-before-rolling logic then naturally computes "form entering this gameweek" correctly, because it was written to never look at a row's own outcome anyway.

Predictions are scaled by `chance_of_playing_this_round` (pulled from `player_current_status`) before being written — a player flagged 50% likely to play gets roughly half the model's raw predicted points, so an injury doubt doesn't rank above a fully fit player with a genuinely lower expected score.

## Judgment calls worth knowing about

- **Model artifacts live on disk** (`ml/artifacts/<model_version>.txt`, gitignored), **not in Postgres**. Only the metadata (`model_runs` — hyperparameters, validation scores) and the predictions themselves live in the database. Keeps the DB small and the model files out of git.
- **Retrain unconditionally, every time**, rather than building a "did the data change enough to bother" heuristic. With the data volumes involved (order 100k-150k rows), LightGBM trains in seconds — the complexity of a smarter retrain-or-skip decision isn't worth it yet.
- **`predictions` is overwritten per (player, season, gameweek)**, not versioned — the API/frontend never has to reason about "which model version is authoritative," there's just one current prediction per gameweek. The `model_version` column on each row still records which model produced it, for debugging.

## Where to look

- `ml/features.py` — the feature list and the leakage-safe rolling logic.
- `ml/train.py::walk_forward_validate` — how validation actually works, and how the baseline comparison is wired in.
- `ml/predict.py::build_predict_frame` — the synthetic-row trick described above.
- `ml/tests/test_features.py` — three tests: leakage is excluded, rolling windows don't cross between players, and home/away strength splitting works. Good starting point for understanding the feature shape by example.

## Running it

```
source ../.venv-ml/bin/activate   # or create one: python3 -m venv .venv-ml
pip install -r requirements.txt
pytest tests/
python -m ml.main train --holdout-season 2024-25
python -m ml.main predict --gameweek 1 --model-version <version from train output>
python -m ml.main train-and-predict --gameweek 1 --holdout-season 2024-25   # what the weekly job runs
```

Note: LightGBM needs Apple's OpenMP runtime on macOS (`brew install libomp`) — without it, `import lightgbm` fails at the OS level, not a code issue.
