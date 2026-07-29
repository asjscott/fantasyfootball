-- name: ListPredictions :many
SELECT
    p.player_id, pl.web_name, t.name AS team, ps.position,
    p.season, p.gameweek, p.predicted_points, p.model_version
FROM predictions p
JOIN players pl ON pl.id = p.player_id
JOIN player_seasons ps ON ps.player_id = p.player_id AND ps.season = p.season
JOIN team_seasons ts ON ts.id = ps.team_id
JOIN teams t ON t.id = ts.team_id
WHERE p.season = $1 AND p.gameweek = $2
    AND (sqlc.narg('position')::text IS NULL OR ps.position = sqlc.narg('position'))
    AND (sqlc.narg('team')::text IS NULL OR t.name = sqlc.narg('team'))
ORDER BY p.predicted_points DESC;
