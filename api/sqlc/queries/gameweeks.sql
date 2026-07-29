-- name: CurrentGameweek :one
-- Earliest not-yet-finished gameweek for a season — the next one a user
-- would want predictions for. MIN() always returns exactly one row; when a
-- season has no unfinished fixtures left, gameweek is coalesced to 0 as a
-- "no upcoming gameweek" sentinel rather than a nullable/scan-failing NULL.
SELECT
    sqlc.arg('season')::text AS season,
    COALESCE(MIN(gameweek), 0)::int AS gameweek
FROM fixtures
WHERE season = sqlc.arg('season') AND finished = false;
