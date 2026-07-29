-- name: ListFixtures :many
SELECT
    f.id, f.season, f.gameweek, f.kickoff_time,
    ht.name AS home_team, at.name AS away_team,
    f.home_score, f.away_score, f.finished,
    f.home_difficulty, f.away_difficulty
FROM fixtures f
JOIN team_seasons hts ON hts.id = f.home_team_id
JOIN teams ht ON ht.id = hts.team_id
JOIN team_seasons ats ON ats.id = f.away_team_id
JOIN teams at ON at.id = ats.team_id
WHERE f.season = $1
    AND (sqlc.narg('gameweek')::int IS NULL OR f.gameweek = sqlc.narg('gameweek'))
ORDER BY f.gameweek, f.kickoff_time;
