# /api — Go backend

Serves data from Postgres to the frontend as JSON. Read-only from the API's perspective — all writes come from `/ingestion` and `/ml`.

## Request flow

`cmd/server/main.go` wires everything together: loads config, opens a connection pool, builds the handler set, registers routes, starts listening. Following one request end to end:

```
HTTP request
  → net/http ServeMux (routes by method + path, e.g. "GET /api/v1/predictions")
  → internal/api/handlers.go (parses query params, validates required ones)
  → internal/store (sqlc-generated — runs the actual SQL, scans rows into Go structs)
  → internal/api/convert.go (translates DB-shaped types to clean JSON-shaped types)
  → internal/api/response.go (wraps the result in the {data, error, meta} envelope)
```

## Why sqlc instead of hand-written SQL scanning (a mid-build change)

The original plan called for hand-written `pgx.CollectRows`/`RowToStructByName` calls per repository method. Partway through, we switched to [sqlc](https://sqlc.dev/): you write plain SQL in `sqlc/queries/*.sql`, sqlc reads the schema to know the table shapes, and it generates typed Go query functions + result structs into `internal/store/`. Concretely: `sqlc/queries/predictions.sql` has one `-- name: ListPredictions :many` query, and `sqlc generate` produces `internal/store/predictions.sql.go` with a `ListPredictions(ctx, params) ([]ListPredictionsRow, error)` method — no manual `rows.Scan(&i.Field, ...)` code to maintain by hand.

This still uses `pgx` underneath (sqlc is a code-generation layer, not a different driver) — `internal/db/db.go` (the connection pool) is still hand-written and separate from the generated code.

**Where sqlc gets the schema from**: `sqlc.yaml`'s `schema:` points directly at `../db/migrations` — the same goose migration files `/db` applies to the real database (see `db/README.md`). This wasn't the original setup: `/db` used to run on Alembic, and sqlc read a separate, hand-maintained plain-SQL mirror file, which was a real duplication risk (nothing enforced the mirror staying in sync with the real migration). Switching `/db` to goose turned out to remove that problem entirely — sqlc understands goose's `-- +goose Up`/`-- +goose Down` annotations natively and only reads the `Up` sections, so there is now exactly one place the schema is written down, applied by goose and read by sqlc.

**Sharp edge already hit once**: sqlc infers Go types from the SQL, including nullability. The `CurrentGameweek` query originally used `MIN(gameweek)` without a fallback, and sqlc inferred a non-nullable `int32` — but `MIN()` over zero rows returns SQL `NULL`, which would have caused a scan panic for a fully-finished season. Fixed with `COALESCE(MIN(gameweek), 0)` in `sqlc/queries/gameweeks.sql`, with `0` documented as a "no upcoming gameweek" sentinel. Worth remembering: sqlc's nullability inference isn't infallible, especially around aggregates.

## Predicted vs. actual points

`GET /api/v1/predictions` returns an `actual_points` field alongside `predicted_points` (`sqlc/queries/predictions.sql`) — a `LEFT JOIN` to `player_gameweek_stats` on `(player_id, season, gameweek)`. It's `null` for a gameweek that hasn't been played yet (no matching row exists to join against) and populated for any gameweek that has real results — which today means every backtest gameweek from `ml/backtest.py`'s 2025-26 replay. No new column was added to `predictions` itself for this — the actual result already lives in `player_gameweek_stats` from ingestion, so the join reuses it rather than duplicating it.

## The `{data, error, meta}` envelope

Every endpoint responds with the same shape (`internal/api/response.go`): `data` holds the payload (or `null` on error), `error` is `null` on success or `{code, message}` on failure, `meta` carries extras like `{"total": N}`. One shared `WriteData`/`WriteError` pair of functions is used by every handler, so this can't drift per-endpoint. `/healthz` is the one deliberate exception — it returns a plain `200 ok` text body, since it's a liveness check, not API data.

## Judgment calls worth knowing about

- **pgx over an ORM**: the query surface is small (~6 endpoints) and all hand-written SQL, so an ORM's relational/migration machinery wouldn't earn its complexity here.
- **stdlib `net/http` router** (Go 1.22+'s method-aware `ServeMux`, e.g. `"GET /api/v1/players/{id}"`) instead of a third-party router — not enough routes to justify the dependency.
- **`pgtype.Numeric`/`pgtype.Timestamptz` are converted explicitly to `float64`/`*time.Time`** at the handler boundary (`internal/api/convert.go`) rather than relying on however those types serialize to JSON by default — keeps the actual JSON shape predictable and independent of pgx-internal behavior.

## Where to look

- `api/sqlc/queries/*.sql` — the actual SQL for every endpoint; usually the fastest way to understand what an endpoint returns and how it filters.
- `api/internal/api/handlers.go` — request parsing/validation and the route table (`Register`).
- `api/internal/api/response.go` — the envelope helper.
- `api/internal/store/` — generated code; read it to see exact Go types, but never hand-edit it (it says `DO NOT EDIT` at the top of every file for a reason — edits get silently overwritten by the next `sqlc generate`).

## Running it

```
go build ./...
go vet ./...
DATABASE_URL=postgresql://... go run ./cmd/server
# after editing sqlc/queries/*.sql or a migration in /db/migrations:
sqlc generate
```
