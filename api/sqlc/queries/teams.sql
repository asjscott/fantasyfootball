-- name: ListTeams :many
SELECT id, name
FROM teams
ORDER BY name;
