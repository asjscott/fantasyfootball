# /ingestion — Data ingestion

Pulls data from two external sources and loads it into Postgres. This is the **only** part of the system that talks to the network — `/ml` reads exclusively from the database (see `ml/README.md` for why).

## The two data sources, and why they're handled differently

1. **Historical GitHub repo** ([vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League)) — a community-maintained mirror of past completed seasons. This is the **training data**: real results, already known, going back multiple years.
2. **Live official FPL API** (`fantasy.premierleague.com/api`) — the current season's squads, prices, injury status, and fixtures. This is **current-season context**: what's needed to generate a prediction for a gameweek that hasn't happened yet.

The dividing line in code is `main.py`'s two commands: `ingest-historical` (rare — run once per season, mostly a one-off backfill) and `ingest-live-snapshot` (frequent — meant to run weekly via the scheduled job, see the root plan).

## Pipeline: fetch → clean → resolve → load

Each stage is its own file, and each does one job:

- **`fetch.py`** — downloads raw CSVs (historical) or hits the live API (current season). Historical downloads are cached locally under `.cache/<season>/` so re-running during development doesn't re-download every time. This is plain `requests` + `pandas.read_csv`, nothing clever.
- **`clean.py`** — the schema-normalization layer. The two data sources (and even different historical seasons) don't use identical column names or have identical columns available — e.g. `defensive_contribution` doesn't exist before 2025-26. Each `clean_*` function selects the columns that matter, renames them to the schema's naming, and fills in `NaN` for any column missing from a given season rather than erroring. **I verified real column names against the live repo/API before writing this** (not from memory) — see the git history if you want the exact `curl` commands used to check.
- **`resolve_players.py`** — the identity crosswalk described in `db/README.md`. Exact join on the stable `code` field is the primary path; fuzzy name matching (`rapidfuzz`) only kicks in if `code` is missing, and every resolution — exact or fuzzy — gets logged to `player_id_map` for auditability rather than trusted silently.
- **`load.py`** — orchestrates the above and writes to Postgres with `INSERT ... ON CONFLICT DO UPDATE` (upserts) keyed on the natural keys from the schema. This makes every load **idempotent** — running `ingest-historical --season 2024-25` twice doesn't create duplicates or error, it just re-confirms the same rows. Every run also writes a row to `ingestion_runs` (start time, rows loaded, success/failure) for a basic audit trail.

`main.py` is the CLI (built with `typer`) that wires these together.

## Judgment calls worth knowing about

- **Ingestion owns all network I/O, on purpose.** The original brief's wording could be read as "ml also calls the live API directly." I deliberately kept `/ml` as a pure batch job that only touches Postgres, and put every external call here instead — it's easier to test, retry, and audit one thing that talks to the network than two.
- **Historical backfill now covers 2019-20 through 2025-26** (`DEFAULT_HISTORICAL_SEASONS` in `config.py`) — deeper than the original ~5-season plan. 2025-26 is included as full historical data because it's the season `ml/backtest.py` replays gameweek-by-gameweek; the extra 2019-20 season exists so even that replay's earliest gameweeks have a deep pre-season training base. Earlier seasons still have thinner stat coverage (no `ict_index`/expected-stats components before 2022-23, no `starts` either — see the `_OPTIONAL_GW_STAT_COLUMNS` comment in `clean.py`), which the ML feature engineering already handles as `NaN`.
- **A player's team for a given historical gameweek is approximated from their season-long `player_seasons.team_id`**, not re-resolved per gameweek. Mid-season transfers are rare enough relative to the training signal that this was an acceptable simplification for v1 — flagged with a comment in `load.py` at the point it matters, in case it turns out to matter more than expected once real predictions are being judged.
- **Fixture IDs**: the historical CSVs have both a `code` (globally stable) and an `id` (season-scoped) for each fixture. `merged_gw.csv`'s `fixture` column references the season-scoped `id`, not `code` — this tripped me up once while writing `clean.py`/`load.py` and is worth knowing if you're ever debugging a fixture join that looks wrong.
- **The source data itself has duplicate rows for some seasons** — confirmed directly: 2020-21's `merged_gw.csv` has 1,437 duplicate `(element, GW)` pairs, 2021-22 has 2,217, and every other season has some too. The idempotent upsert in `load.py` (`ON CONFLICT DO UPDATE`) handles this transparently — it just means the CLI's "N rows loaded" count is an upsert-attempt count, not a guarantee that N distinct rows exist afterward; query the table directly if you need the true row count for a season.
- **2019-20's gameweek numbers jump from 29 to 39** — no 30-38 exist in the source data at all, almost certainly an artifact of that season's COVID suspension/resumption. This doesn't break anything: gameweek 39 genuinely happened after gameweek 29 chronologically, and nothing in this codebase assumes gameweeks are numbered 1-38 or contiguous — `ml/train.py`'s walk-forward loop iterates over whatever gameweek values actually exist for a season.

## Where to look

- `ingestion/config.py` — which seasons get backfilled by default, and where the live/historical base URLs point.
- `ingestion/resolve_players.py:resolve_player` — the crosswalk logic, if you want to understand exactly how a CSV row becomes (or matches) a `players` row.
- `ingestion/tests/test_clean.py` — runnable examples of what raw vs. cleaned rows look like for each source file.

## Running it

```
source ../.venv-ingestion/bin/activate   # or create one: python3 -m venv .venv-ingestion
pip install -r requirements.txt
python -m ingestion.main ingest-historical --season 2024-25
python -m ingestion.main ingest-live-snapshot
pytest tests/
```
