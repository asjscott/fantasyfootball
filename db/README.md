# /db — Schema

This directory owns the Postgres schema via [goose](https://github.com/pressly/goose) migrations — plain SQL files, applied and tracked by the `goose` CLI (a Go binary, not part of any of this project's application code). It's the single source of truth: `/ingestion`, `/ml`, and `/api` all read/write tables defined here, but none of them define or change schema themselves.

**This started out on Alembic** (a Python migration tool built on SQLAlchemy). We switched to goose once it became clear the schema is genuinely shared infrastructure between a Go service and two Python services, so a Python-specific tool wasn't the most neutral fit — a fair point raised mid-build, given prior experience with goose elsewhere. The switch turned out to unlock something better than a like-for-like swap too (see below).

## How it works

- `migrations/00001_initial_schema.sql` is a single migration file with `-- +goose Up` and `-- +goose Down` sections — plain `CREATE TABLE`/`DROP TABLE` SQL, no ORM, no Python. Real projects accumulate many small migration files over time (`00002_...`, `00003_...`); there's only one so far because the schema hasn't shipped yet.
- Goose reads its target database from `GOOSE_DRIVER`/`GOOSE_DBSTRING` env vars (or CLI args) — it does **not** read `.env` files itself, so those need to be set explicitly (or copy `DATABASE_URL` into them) when running goose commands.

Run migrations with:
```
cd db
GOOSE_DRIVER=postgres GOOSE_DBSTRING="$DATABASE_URL" GOOSE_MIGRATION_DIR=migrations goose up
```

## A nice side effect of the switch: sqlc reads these files directly

`/api` uses `sqlc` to generate typed Go query code (see `api/README.md`), and sqlc needs to know the table shapes to do that. With Alembic, that meant hand-maintaining a second, plain-SQL copy of the schema (`api/sqlc/schema.sql`) just for sqlc to read — a real duplication problem, since nothing enforced the two staying in sync.

It turns out **sqlc natively understands goose's `-- +goose Up`/`-- +goose Down` annotations** — verified empirically before relying on it, not assumed from documentation. `api/sqlc.yaml`'s `schema:` now points straight at `../db/migrations`, and sqlc correctly reads only the `Up` sections when inferring table shapes, ignoring the `Down` sections' `DROP TABLE` statements. That duplicated mirror file is gone — there is now exactly one place the schema is written down.

## Schema design — the judgment calls

**Identity is normalized across seasons; stats are denormalized into one wide table.** Those are opposite design choices made deliberately for different reasons:

- A player's or team's *identity* has to survive season boundaries — teams get promoted/relegated, players transfer. So `players` and `teams` are tiny master tables keyed by a stable id, and `player_seasons`/`team_seasons` hold the season-scoped details (which team a player was on, their position, a team's strength ratings *that season*). Anything that needs "the current team_id for this player in season X" joins through `player_seasons`.
- A gameweek's *stats*, by contrast, are always queried together (you basically never want `goals_scored` without `assists` and `minutes` in the same query) and FPL's scoring stat set is fixed and small. So `player_gameweek_stats` is one wide fact table — 30-ish columns, one row per (player, season, gameweek) — rather than a normalized "one row per stat" model. Normalizing that would mean a join (or 30) for every query that just wants "how did this player do."

**The player/team identity crosswalk problem turned out to be easy.** Before writing this schema, I checked the actual data (both the historical GitHub CSVs and the live FPL API) rather than assuming. Both sources expose a `code` field that's stable for a real player/team across seasons and across the two data sources — unlike `id`, which is scoped to one season and can change after a transfer. That meant the crosswalk (`player_id_map` table, resolved in `ingestion/resolve_players.py`) could be a straightforward exact join on `code`, with fuzzy name-matching only as a rare fallback — not the primary mechanism, which is what I'd originally assumed before checking.

**`player_current_status` is append-only, not upserted.** Every ingestion run adds a new row (timestamped `as_of`) rather than overwriting the previous snapshot. That's slightly more storage for basically free, and it means injury/price-change history falls out naturally later without having to plan for it now — the API/ML code just reads the latest row per player (`DISTINCT ON (player_id) ... ORDER BY as_of DESC`).

**`player_gameweek_stats.source`** distinguishes `github_historical` from `live_api` rows, because the two data sources have overlapping coverage near a season boundary and it's useful to know which one populated a given row.

**Some stat columns are nullable because the data itself doesn't go back that far**: `expected_goals`/`expected_assists`/etc. don't exist before the 2021-22 season, and `defensive_contribution` is a 2025-26 rule change. Rather than backfilling fake values, these are left `NULL` and the ML feature engineering (see `ml/README.md`) is built to handle that natively.

## Where to look

- `db/migrations/00001_initial_schema.sql` — the whole schema, table by table, with structure that mirrors this README's grouping (identity tables, then season tables, then fact tables, then prediction/ops tables).
- `api/sqlc.yaml` — where sqlc is pointed at this directory to generate Go types from it directly.
