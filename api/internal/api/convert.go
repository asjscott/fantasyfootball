package api

import (
	"time"

	"github.com/jackc/pgx/v5/pgtype"

	"fantasyfootball/api/internal/store"
)

// sqlc generates pgtype.Numeric/pgtype.Timestamptz for nullable Postgres
// numeric/timestamp columns. These converters translate them to plain
// float64/*time.Time at the API boundary so the JSON response shape stays
// predictable rather than depending on pgtype's own (undocumented-for-us)
// marshaling behavior.

func numericToFloat64(n pgtype.Numeric) float64 {
	f, err := n.Float64Value()
	if err != nil || !f.Valid {
		return 0
	}
	return f.Float64
}

func timestamptzToTimePtr(t pgtype.Timestamptz) *time.Time {
	if !t.Valid {
		return nil
	}
	return &t.Time
}

type FixtureResponse struct {
	ID             int32      `json:"id"`
	Season         string     `json:"season"`
	Gameweek       *int32     `json:"gameweek"`
	KickoffTime    *time.Time `json:"kickoff_time"`
	HomeTeam       string     `json:"home_team"`
	AwayTeam       string     `json:"away_team"`
	HomeScore      *int32     `json:"home_score"`
	AwayScore      *int32     `json:"away_score"`
	Finished       bool       `json:"finished"`
	HomeDifficulty *int32     `json:"home_difficulty"`
	AwayDifficulty *int32     `json:"away_difficulty"`
}

func toFixtureResponse(row store.ListFixturesRow) FixtureResponse {
	return FixtureResponse{
		ID:             row.ID,
		Season:         row.Season,
		Gameweek:       row.Gameweek,
		KickoffTime:    timestamptzToTimePtr(row.KickoffTime),
		HomeTeam:       row.HomeTeam,
		AwayTeam:       row.AwayTeam,
		HomeScore:      row.HomeScore,
		AwayScore:      row.AwayScore,
		Finished:       row.Finished,
		HomeDifficulty: row.HomeDifficulty,
		AwayDifficulty: row.AwayDifficulty,
	}
}

type PredictionResponse struct {
	PlayerID        int32   `json:"player_id"`
	WebName         *string `json:"web_name"`
	Team            string  `json:"team"`
	Position        string  `json:"position"`
	Season          string  `json:"season"`
	Gameweek        int32   `json:"gameweek"`
	PredictedPoints float64 `json:"predicted_points"`
	ModelVersion    string  `json:"model_version"`
}

func toPredictionResponse(row store.ListPredictionsRow) PredictionResponse {
	return PredictionResponse{
		PlayerID:        row.PlayerID,
		WebName:         row.WebName,
		Team:            row.Team,
		Position:        row.Position,
		Season:          row.Season,
		Gameweek:        row.Gameweek,
		PredictedPoints: numericToFloat64(row.PredictedPoints),
		ModelVersion:    row.ModelVersion,
	}
}
