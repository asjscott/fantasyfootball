package api

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/jackc/pgx/v5"

	"fantasyfootball/api/internal/store"
)

type Handlers struct {
	Queries *store.Queries
}

func (h *Handlers) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /healthz", h.handleHealthz)
	mux.HandleFunc("GET /api/v1/players", h.handleListPlayers)
	mux.HandleFunc("GET /api/v1/players/{id}", h.handleGetPlayer)
	mux.HandleFunc("GET /api/v1/players/{id}/predictions", h.handleListPlayerPredictions)
	mux.HandleFunc("GET /api/v1/teams", h.handleListTeams)
	mux.HandleFunc("GET /api/v1/fixtures", h.handleListFixtures)
	mux.HandleFunc("GET /api/v1/predictions", h.handleListPredictions)
	mux.HandleFunc("GET /api/v1/gameweeks/current", h.handleCurrentGameweek)
}

func (h *Handlers) handleHealthz(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok"))
}

func (h *Handlers) handleListPlayers(w http.ResponseWriter, r *http.Request) {
	players, err := h.Queries.ListPlayers(r.Context())
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "internal_error", err.Error())
		return
	}
	WriteData(w, http.StatusOK, players, map[string]any{"total": len(players)})
}

func (h *Handlers) handleGetPlayer(w http.ResponseWriter, r *http.Request) {
	id, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		WriteError(w, http.StatusBadRequest, "invalid_id", "id must be an integer")
		return
	}

	player, err := h.Queries.GetPlayer(r.Context(), int32(id))
	if errors.Is(err, pgx.ErrNoRows) {
		WriteError(w, http.StatusNotFound, "not_found", "player not found")
		return
	}
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "internal_error", err.Error())
		return
	}
	WriteData(w, http.StatusOK, player, nil)
}

func (h *Handlers) handleListPlayerPredictions(w http.ResponseWriter, r *http.Request) {
	id, err := strconv.Atoi(r.PathValue("id"))
	if err != nil {
		WriteError(w, http.StatusBadRequest, "invalid_id", "id must be an integer")
		return
	}

	query := r.URL.Query()
	season := query.Get("season")
	if season == "" {
		WriteError(w, http.StatusBadRequest, "missing_param", "season is required")
		return
	}

	fromGameweek, err := strconv.Atoi(query.Get("from_gameweek"))
	if err != nil {
		WriteError(w, http.StatusBadRequest, "missing_param", "from_gameweek is required and must be an integer")
		return
	}

	horizon := 5
	if raw := query.Get("horizon"); raw != "" {
		horizon, err = strconv.Atoi(raw)
		if err != nil || horizon < 1 {
			WriteError(w, http.StatusBadRequest, "invalid_param", "horizon must be a positive integer")
			return
		}
	}

	rows, err := h.Queries.ListPlayerPredictions(r.Context(), store.ListPlayerPredictionsParams{
		PlayerID:     int32(id),
		Season:       season,
		FromGameweek: int32(fromGameweek),
		ToGameweek:   int32(fromGameweek + horizon - 1),
	})
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "internal_error", err.Error())
		return
	}

	predictions := make([]PlayerPredictionResponse, len(rows))
	for i, row := range rows {
		predictions[i] = toPlayerPredictionResponse(row)
	}
	WriteData(w, http.StatusOK, predictions, map[string]any{"total": len(predictions)})
}

func (h *Handlers) handleListTeams(w http.ResponseWriter, r *http.Request) {
	teams, err := h.Queries.ListTeams(r.Context())
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "internal_error", err.Error())
		return
	}
	WriteData(w, http.StatusOK, teams, map[string]any{"total": len(teams)})
}

func (h *Handlers) handleListFixtures(w http.ResponseWriter, r *http.Request) {
	season := r.URL.Query().Get("season")
	if season == "" {
		WriteError(w, http.StatusBadRequest, "missing_param", "season is required")
		return
	}

	gameweek, err := parseOptionalInt32(r.URL.Query().Get("gameweek"))
	if err != nil {
		WriteError(w, http.StatusBadRequest, "invalid_param", "gameweek must be an integer")
		return
	}

	rows, err := h.Queries.ListFixtures(r.Context(), store.ListFixturesParams{
		Season: season, Gameweek: gameweek,
	})
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "internal_error", err.Error())
		return
	}

	fixtures := make([]FixtureResponse, len(rows))
	for i, row := range rows {
		fixtures[i] = toFixtureResponse(row)
	}
	WriteData(w, http.StatusOK, fixtures, map[string]any{"total": len(fixtures)})
}

func (h *Handlers) handleListPredictions(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query()
	season := query.Get("season")
	if season == "" {
		WriteError(w, http.StatusBadRequest, "missing_param", "season is required")
		return
	}

	gameweek, err := strconv.Atoi(query.Get("gameweek"))
	if err != nil {
		WriteError(w, http.StatusBadRequest, "missing_param", "gameweek is required and must be an integer")
		return
	}

	rows, err := h.Queries.ListPredictions(r.Context(), store.ListPredictionsParams{
		Season:   season,
		Gameweek: int32(gameweek),
		Position: optionalString(query.Get("position")),
		Team:     optionalString(query.Get("team")),
	})
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "internal_error", err.Error())
		return
	}

	predictions := make([]PredictionResponse, len(rows))
	for i, row := range rows {
		predictions[i] = toPredictionResponse(row)
	}
	WriteData(w, http.StatusOK, predictions, map[string]any{"total": len(predictions)})
}

func (h *Handlers) handleCurrentGameweek(w http.ResponseWriter, r *http.Request) {
	season := r.URL.Query().Get("season")
	if season == "" {
		WriteError(w, http.StatusBadRequest, "missing_param", "season is required")
		return
	}

	gw, err := h.Queries.CurrentGameweek(r.Context(), season)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "internal_error", err.Error())
		return
	}
	WriteData(w, http.StatusOK, gw, nil)
}

func parseOptionalInt32(raw string) (*int32, error) {
	if raw == "" {
		return nil, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return nil, err
	}
	converted := int32(value)
	return &converted, nil
}

func optionalString(raw string) *string {
	if raw == "" {
		return nil
	}
	return &raw
}
