-- name: ListPlayers :many
SELECT id, first_name, second_name, web_name
FROM players
ORDER BY second_name;

-- name: GetPlayer :one
SELECT id, first_name, second_name, web_name
FROM players
WHERE id = $1;
