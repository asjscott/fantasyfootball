# /ml — Prediction model

Trains a model to predict FPL points per player per gameweek, and generates predictions for an upcoming gameweek. Reads exclusively from Postgres (populated by `/ingestion`) and writes predictions back to Postgres — no network calls happen here.

## The core idea: leakage-safe rolling features

The hardest thing to get right in a "predict the future from the past" problem is making sure a row's features don't secretly contain information from its own future. `features.py` is built around one rule: every rolling-average feature (`form_points_3`, `form_minutes_5`, etc.) is computed with `.shift(1)` **before** `.rolling()` — meaning gameweek 10's "form" is the average of gameweeks 7-9, never including gameweek 10 itself. This is tested directly in `tests/test_features.py::test_rolling_form_excludes_current_gameweek`, which asserts the exact numbers a hand-computed rolling average should produce.

Why this matters: if you get this wrong, a model trained with information leakage will look great in validation (because it's partially just reading the answer) and then perform badly on real future gameweeks (where that leaked information doesn't exist yet). It's the single easiest way to fool yourself in this kind of project.

## Model choice and validation

- **LightGBM regression**, `position` as a categorical feature — one model, not four separate position-specific models. Simpler pipeline; if later analysis shows the model is systematically biased by position, that's a reasonable v2 to build.
- **Walk-forward validation only** (`train.py::walk_forward_validate`) — never k-fold/random-shuffle cross-validation. This is deliberate: k-fold would let the model train on gameweek 20 and validate on gameweek 15, which is information from the future leaking into training in a different way than the feature-leakage issue above. Walk-forward always trains on gameweeks strictly *before* the one being scored, which matches how the model will actually be used.
- **A naive baseline is always computed alongside the model** (`baseline.py` — literally just "predict their trailing 5-gameweek average") and logged next to the model's own MAE in `model_runs.notes`. This exists so a broken or overfit model gets caught by "did it actually beat the dumb heuristic," rather than trusting a metric that looks reasonable in isolation.

### Why MAE is reported played-only, not just blended

`player_gameweek_stats` includes a row for every player in a squad that gameweek, whether they actually played or not — on the real 2025-26 data, **61% of rows have `minutes = 0`** (unused subs, injuries, players not selected at all). Predicting ~0 points for a player who didn't play is trivial, and a single blended MAE over the whole population is dominated by that easy majority: the reported backtest MAE of 0.978 is a blend of a 0.36 MAE on zero-minute rows (61% of rows) and a **1.96 MAE on rows where the player actually played** (39% of rows) — over 5x worse than the headline number once you restrict to the population a fantasy manager actually cares about. `ml/metrics.py::segmented_mae` reports both halves separately (`mae`/`played_mae`/`unplayed_mae`) from every evaluation path (`walk_forward_validate`, `backtest_season`) so this doesn't stay hidden. Note this is a **reporting-only** split — the model is still trained on the full population, since production also needs to predict correctly for benched/injured players, not just starters.

## Prediction pipeline: multi-gameweek, one fixture at a time

`predict.py` predicts `start_gameweek .. start_gameweek + horizon - 1` (default horizon 1), and does it **one fixture at a time**, not one gameweek at a time — that distinction matters because of a real bug this design fixes (below).

- **`compute_current_form(history_df, season, as_of_gameweek)`** computes each player's rolling-form snapshot ("form as of now") **once**, independent of which future gameweek is being predicted. It reuses `build_features` (still the single source of truth for how rolling form is computed) by appending one placeholder row per player, then keeps only the resulting `form_*` columns. Because `player_gameweek_stats` has no real row for a gameweek that hasn't been played, this form snapshot is naturally the same no matter which future gameweek you ask about — "frozen form," for free, from the same shift-before-rolling logic that makes training leakage-safe.
- **`load_predict_fixture_context`** (`ml/data.py`) returns one row per `(player, fixture)` for every fixture in the horizon — not one row per gameweek. A blank gameweek naturally contributes zero rows for that player; a double gameweek naturally contributes two. No special-casing.
- **`_score_fixtures`** merges the frozen form snapshot onto every fixture row and predicts **once per fixture**, then **`sum_fixture_predictions`** groups back to one row per `(player, gameweek)` — summing a double-gameweek player's two fixture predictions rather than picking one.

Predictions are scaled by `chance_of_playing_this_round` (pulled from `player_current_status`) before being written — a player flagged 50% likely to play gets roughly half the model's raw predicted points, so an injury doubt doesn't rank above a fully fit player with a genuinely lower expected score.

### The double-gameweek bug this design fixes

The original single-gameweek design (append one synthetic row, run it through `build_features`, done) quietly assumed exactly one fixture per player per gameweek. Checked directly whether that assumption ever breaks, rather than assuming it doesn't:

- **2020-21 gameweek 19** is a real double gameweek — Aston Villa played twice (fixtures 562 and 565).
- Checking a real player's stored row for it (`player_gameweek_stats`, Ollie Watkins, 2020-21 GW19): `minutes=90, fixture_id=562, total_points=6` — only **one** of his two matches that gameweek is represented at all, not a combined total. The historical training data has always slightly under-counted points/minutes for the small number of (player, double-gameweek) rows in the dataset — inherited from the source CSVs, not introduced here, and not worth chasing given how few of ~178,700 rows it touches.
- The old prediction path had an **active bug**, just never triggered (no double gameweek had been scheduled for 2026-27 yet when this was found): the old `load_predict_context` joined to `fixtures` with no dedup, so it *correctly* returned two rows for a double-gameweek player — but concatenating those with history and running through `build_features` meant two same-gameweek rows sorting in an arbitrary, unstable order, corrupting the rolling-form calc for whichever landed second. The old `write_predictions` upsert (keyed only on `player_id, season, gameweek`) then let the second fixture's prediction silently overwrite the first — losing half a double-gameweek player's expected points instead of correctly valuing the extra fixture.

Real 2026-27 fixtures don't have a double gameweek yet (checked directly via `psql`; they typically appear later via mid-season rescheduling), so this can't be tested against the live season yet. `ml/tests/test_predict.py` covers it with a fabricated scenario instead, since `ml/backtest.py` can't exercise this path either — it replays already-collapsed historical rows, not the live per-fixture prediction path.

## Confidence rating: what worked, what didn't, and why

`predictions.confidence` is a 0.0-1.0 score, but **it is not a claim about points-prediction accuracy** — that framing was tried first and empirically failed. Worth understanding both halves of this, not just the version that shipped:

**First attempt (dropped)**: a heuristic combining "has recent points history," "recent minutes reliability," and "injury doubt," framed as "how much to trust this points estimate." Before shipping it, it was checked against the 2025-26 backtest's real predicted-vs-actual points (`ml/validate_confidence.py`) — **correlation with actual error was 0.044, statistically indistinguishable from zero, and the wrong sign**. Checking further (position, recent-minutes quartile) found no other simple signal that discriminated real points-prediction error either — the only thing that correlated with error size was the prediction's own magnitude (bigger predicted points → bigger absolute error), which is a scale effect (a heteroscedasticity confound: players expected to score more have more room to be wrong in absolute terms), not a trustworthiness signal, and using it as "confidence" would have meant labeling your best captaincy picks as *less* confident than your bench filler. Dropped rather than shipped as a misleading label.

**What shipped instead**: `compute_confidence` measures **playing-time certainty** — how likely a player is to get real minutes this gameweek — from `form_minutes_5` (recent minutes trend) and `chance_of_playing_this_round` (live injury/rotation status), with a horizon-decay multiplier for gameweeks further out (a tunable heuristic, not derived — certainty about rotation/injury genuinely degrades with distance). This is a *different empirical claim* than the first attempt, and it validates cleanly: `form_minutes_5`-based signal correlates **0.77** with actual future minutes on the same real 2025-26 data, with a clean, monotonic split across quartiles (~1 vs. ~29 vs. ~69 average actual minutes; P(60+ minutes) goes 0.9% → 27.8% → 75.5%). Re-run `python -m ml.validate_confidence` any time the heuristic's weights change — it's a real regression test for "does this number still mean something," not a one-time check.

One nuance worth knowing when reading confidence values: `build_features`'s rolling-form groupby is keyed by `player_id` only, not `(player_id, season)` — so a player's rolling form naturally carries across a season boundary. An established player entering 2026-27 GW1 gets their confidence from their final 2025-26 gameweeks, not a blank slate; a genuinely new-to-the-league player has no such history and gets the low `0.2` floor. This is an existing property of `build_features`, not something this stage changed, and it's arguably the right behavior (an established starter *should* enter a new season with more playing-time certainty than a total unknown) — just non-obvious if you're expecting everyone to start the season at the same baseline.

## Judgment calls worth knowing about

- **Model artifacts live on disk** (`ml/artifacts/<model_version>.txt`, gitignored), **not in Postgres**. Only the metadata (`model_runs` — hyperparameters, validation scores) and the predictions themselves live in the database. Keeps the DB small and the model files out of git.
- **Retrain unconditionally, every time**, rather than building a "did the data change enough to bother" heuristic. With the data volumes involved (order 100k-150k rows), LightGBM trains in seconds — the complexity of a smarter retrain-or-skip decision isn't worth it yet.
- **`predictions` is overwritten per (player, season, gameweek)**, not versioned — the API/frontend never has to reason about "which model version is authoritative," there's just one current prediction per gameweek. The `model_version` column on each row still records which model produced it, for debugging.

## The season backtest (`backtest.py`)

Before the live 2026-27 season starts, we wanted to exercise the whole train → predict → API → frontend cycle against a real, complete season rather than trusting it blind. `backtest.py::backtest_season` replays 2025-26 gameweek-by-gameweek: for each gameweek, it trains a fresh model on everything strictly before it (2019-20 through 2024-25, plus 2025-26's own earlier gameweeks) and writes real predictions for that gameweek to Postgres — the same `predictions` table, distinguished by `model_version` values like `backtest-2025-26-gw07`.

This isn't new prediction logic — it reuses `train.py`'s exact walk-forward loop. Originally `walk_forward_validate` computed aggregate MAE/RMSE and threw away the individual predictions; it's now split into `walk_forward_predict` (a generator yielding `(gameweek, test_data, predictions)` per gameweek) and a thin `walk_forward_validate` that consumes it for metrics. `backtest.py` consumes the same generator to persist the actual per-player numbers instead. One walk-forward implementation, two uses — refactored this way specifically to avoid maintaining the loop twice.

Because the target season's real results are already known, this also gives an honest accuracy read: run locally against seven real seasons (2019-20 through 2025-26, ~178,700 rows), the full 2025-26 replay finished in about a minute and came out to a **player-weighted MAE of ~0.98 points/player/gameweek** — but see "Why MAE is reported played-only" above: that blended figure is dominated by zero-minute rows, and the **played-only MAE is ~1.96**. Worth understanding *why* GW1 is the worst gameweek on both measures (blended MAE 1.33, played MAE 2.27, versus ~0.9-1.0 blended for most of the season): every player's rolling-form features are `NaN` at the very start of a season (no prior gameweeks to average), so the model is working with the least information all year. It also can't predict rare one-off explosions (e.g. a defender scoring an unlikely 17-point haul in GW1) — that's expected of an average-seeking regression model, not a bug to fix.

## Judgment calls specific to the backtest

- **`training_seasons` passed to `backtest_season` should be strictly *before* the target season** — the target season itself is appended automatically (its own earlier gameweeks are legitimate training input for its later ones). Passing the target season in both places would just be a no-op since the function de-duplicates it, but the separation exists to make the "prior seasons vs. the season being replayed" distinction explicit in the CLI.
- **No model files are saved for backtest runs** — 38 gameweeks × a full LightGBM model would be a lot of disk for models nobody needs to reload (unlike the live `train`/`predict` path, where `predict` needs to reload the model `train` just saved). Backtest results only need to persist as `predictions` + `model_runs` rows.

## Generating real predictions for the upcoming season

`train-and-predict` is the command that generates the real thing this whole project is for — verified for real against 2026-27 (live squads/prices/fixtures pulled by `ingestion ingest-live-snapshot`, see `ingestion/README.md`): `python -m ml.main train-and-predict --gameweek 1 --holdout-season 2025-26` trained on the full historical set, walk-forward validated against 2025-26 (blended MAE 0.980, played-only MAE 1.96 — see "Why MAE is reported played-only" above; reassuringly close to `backtest_season`'s own 0.978/1.96 for the same season, since both use the exact same `walk_forward_predict` loop under the hood), confirmed it beats the naive baseline both blended (0.980 vs. 1.057) and played-only (1.96 vs. 2.22), then generated real predictions for 2026-27. With `--horizon 5`, it generated 2,820 predictions (564 players × 5 gameweeks), each with a real `confidence` — e.g. Haaland's predicted points varied sensibly by fixture across the horizon (5.67, 5.73, 6.48, 5.65, 6.48) while confidence correctly decayed with distance (0.60 → 0.48).

**A real mistake caught before this ran**: `main.py`'s `DEFAULT_SEASONS` (the season list `train`/`predict`/`train-and-predict` use unless overridden) had been narrowed to exclude 2025-26 while building the backtest feature — 2025-26 was carved out as the backtest's *target* season, and it was easy to also lose track of the fact that meant it was silently missing from the list used for *real* predictions too. Excluding the single most recent, most relevant complete season from training data for real predictions would have been a genuine modeling mistake, not just a smaller default. Caught and fixed by re-reading `DEFAULT_SEASONS` before running anything against the live season, rather than assuming a list written weeks earlier was still correct for a new purpose.

## Where to look

- `ml/features.py` — the feature list and the leakage-safe rolling logic.
- `ml/train.py::walk_forward_predict` — the shared walk-forward loop; `walk_forward_validate` and `ml/backtest.py::backtest_season` are both thin wrappers around it.
- `ml/metrics.py::segmented_mae` — splits MAE by whether the player actually played, so the zero-minute majority doesn't mask real-world accuracy; see "Why MAE is reported played-only" above. `ml/tests/test_metrics.py` covers the split logic directly.
- `ml/predict.py::compute_current_form` — the frozen-form snapshot; `_score_fixtures`/`sum_fixture_predictions` — the per-fixture-then-sum design that fixes double gameweeks; `compute_confidence` — the playing-time-certainty heuristic.
- `ml/backtest.py::backtest_season` — the season replay.
- `ml/validate_confidence.py` — the confidence heuristic's regression test against real data; re-run it whenever the heuristic's weights change.
- `ml/main.py::DEFAULT_SEASONS` vs. `DEFAULT_BACKTEST_TRAINING_SEASONS` — two different season lists for two different purposes; worth reading the comment above each rather than assuming they're interchangeable.
- `ml/tests/test_features.py` — leakage is excluded, rolling windows don't cross between players, home/away strength splitting works.
- `ml/tests/test_predict.py` — the double-gameweek fix: two fixture predictions sum rather than one overwriting the other, confidence is capped by the weaker leg not averaged, a blank gameweek contributes nothing.

## Running it

```
source ../.venv-ml/bin/activate   # or create one: python3 -m venv .venv-ml
pip install -r requirements.txt
pytest tests/
python -m ml.main train --holdout-season 2024-25
python -m ml.main predict --gameweek 1 --horizon 5 --model-version <version from train output>
python -m ml.main train-and-predict --gameweek 1 --horizon 5 --holdout-season 2024-25   # what the weekly job runs
python -m ml.main backtest   # replays 2025-26 gameweek-by-gameweek against Postgres
python -m ml.validate_confidence   # regression-tests the confidence heuristic against real data
```

Note: LightGBM needs Apple's OpenMP runtime on macOS (`brew install libomp`) — without it, `import lightgbm` fails at the OS level, not a code issue.
