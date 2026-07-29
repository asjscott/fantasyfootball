# CLAUDE.md

## Project
Next.js + TypeScript frontend, Golang API backend.
ML Service: Python
Database: PostgreSQL 

## Key directories
- /web - Next.js Frontend
- /api - Golang API
- /ingestion - Python ingestion scripts
- /ml - Python training scripts

## Commands
- /db: `GOOSE_DRIVER=postgres GOOSE_DBSTRING="$DATABASE_URL" GOOSE_MIGRATION_DIR=migrations goose up` — apply migrations (source of truth for schema)
- /ingestion: `python -m ingestion.main ingest-historical --season 2024-25` / `ingest-live-snapshot`
- /ingestion, /ml: `pytest` to run tests
- /ml: `python -m ml.main train --holdout-season 2024-25` / `predict` / `train-and-predict`
- /api: `go run ./cmd/server`, `go build ./...`, `sqlc generate` (after editing sqlc/queries/*.sql or a migration in /db/migrations)
- /web: `npm run dev`, `npm run build`, `npm run lint`

## Conventions
- Use named exports, not default exports (except Next.js `page.tsx`/`layout.tsx`, which the framework requires to default-export)
- Frontend as much serverside rendering as possible
- API responses follow { data, error, meta } shape
- Tests colocated with source files as *.test.ts
- /db uses goose (plain SQL migrations in /db/migrations), not Alembic/SQLAlchemy — chosen because the schema is shared between a Go service and two Python services, so a Python-specific migration tool wasn't the most neutral fit
- /api uses sqlc (sqlc/queries/*.sql + schema read directly from /db/migrations) instead of hand-written SQL scanning — sqlc understands goose's Up/Down annotations natively, so there is no separate mirrored schema file to keep in sync

## Avoid
- Don't use `any` type -- use `unknown` and narrow
- Don't add dependencies without checking bundle size impact
- Don't modify the shared package without updating both apps

## Learning workflow (mandatory — the user is learning this codebase as it's built)
Treat the user as a student building this project to learn, not just to ship it. At the end of every development stage (finishing a component, a major feature, or a phase of the build plan):
1. Write or update the README.md in each directory touched during that stage. Each README should explain: how the code works (the actual mechanics, not a restatement of file names), what judgment calls/trade-offs were made and *why* (including ones that changed mid-build), and where to find the important logic (specific files/functions to read).
2. Before starting the next stage, quiz the user on what was just built. A handful of conceptual questions — testing understanding of *why* things work the way they do and how pieces connect, not trivia or syntax recall. Wait for their answers; correct and explain rather than just grading. Do not silently skip this, even if the user seems eager to move fast — if you think skipping makes sense for a given stage, ask first rather than assuming.
Do not treat this as optional polish — it is part of the definition of done for a stage.