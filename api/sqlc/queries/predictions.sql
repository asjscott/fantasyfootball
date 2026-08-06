-- name: ListPredictions :many
-- actual_points is NULL for a gameweek that hasn't been played yet (no
-- matching player_gameweek_stats row); populated for backtest/historical
-- gameweeks so predicted-vs-actual can be compared directly. confidence is
-- playing-time certainty (0-1), not points-accuracy — see ml/README.md.
SELECT
    p.player_id, pl.web_name, t.name AS team, ps.position,
    p.season, p.gameweek, p.predicted_points, p.confidence, p.model_version,
    pgs.total_points AS actual_points
FROM predictions p
JOIN players pl ON pl.id = p.player_id
JOIN player_seasons ps ON ps.player_id = p.player_id AND ps.season = p.season
JOIN team_seasons ts ON ts.id = ps.team_id
JOIN teams t ON t.id = ts.team_id
LEFT JOIN player_gameweek_stats pgs
    ON pgs.player_id = p.player_id AND pgs.season = p.season AND pgs.gameweek = p.gameweek
WHERE p.season = $1 AND p.gameweek = $2
    AND (sqlc.narg('position')::text IS NULL OR ps.position = sqlc.narg('position'))
    AND (sqlc.narg('team')::text IS NULL OR t.name = sqlc.narg('team'))
ORDER BY p.predicted_points DESC;

-- name: ListPlayerPredictions :many
-- One player's predictions across a gameweek range — the per-player,
-- multi-gameweek view (predicted points + confidence per upcoming
-- gameweek), same actual_points join as ListPredictions above.
SELECT
    p.season, p.gameweek, p.predicted_points, p.confidence, p.model_version,
    pgs.total_points AS actual_points
FROM predictions p
LEFT JOIN player_gameweek_stats pgs
    ON pgs.player_id = p.player_id AND pgs.season = p.season AND pgs.gameweek = p.gameweek
WHERE p.player_id = $1 AND p.season = $2
    AND p.gameweek BETWEEN sqlc.arg('from_gameweek') AND sqlc.arg('to_gameweek')
ORDER BY p.gameweek;
