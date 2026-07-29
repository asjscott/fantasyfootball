-- +goose Up

CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    fpl_code INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE team_seasons (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    season TEXT NOT NULL,
    fpl_season_team_id INTEGER NOT NULL,
    strength INTEGER,
    strength_attack_home INTEGER,
    strength_attack_away INTEGER,
    strength_defence_home INTEGER,
    strength_defence_away INTEGER,
    UNIQUE (team_id, season)
);

CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    fpl_code INTEGER NOT NULL UNIQUE,
    first_name TEXT,
    second_name TEXT,
    web_name TEXT
);

CREATE TABLE player_seasons (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    season TEXT NOT NULL,
    fpl_season_element_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL REFERENCES team_seasons(id),
    position TEXT NOT NULL,
    UNIQUE (player_id, season)
);

CREATE TABLE player_id_map (
    id SERIAL PRIMARY KEY,
    season TEXT NOT NULL,
    source_element_id INTEGER NOT NULL,
    source_code INTEGER,
    matched_player_id INTEGER REFERENCES players(id),
    match_method TEXT NOT NULL,
    confidence NUMERIC,
    reviewed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fixtures (
    id SERIAL PRIMARY KEY,
    season TEXT NOT NULL,
    fpl_fixture_code INTEGER NOT NULL UNIQUE,
    gameweek INTEGER,
    kickoff_time TIMESTAMPTZ,
    home_team_id INTEGER NOT NULL REFERENCES team_seasons(id),
    away_team_id INTEGER NOT NULL REFERENCES team_seasons(id),
    home_score INTEGER,
    away_score INTEGER,
    finished BOOLEAN NOT NULL DEFAULT false,
    home_difficulty INTEGER,
    away_difficulty INTEGER
);
CREATE INDEX ix_fixtures_season_gameweek ON fixtures (season, gameweek);

CREATE TABLE player_gameweek_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    season TEXT NOT NULL,
    gameweek INTEGER NOT NULL,
    fixture_id INTEGER REFERENCES fixtures(id),
    team_id INTEGER REFERENCES team_seasons(id),
    opponent_team_id INTEGER REFERENCES team_seasons(id),
    was_home BOOLEAN,
    minutes INTEGER,
    total_points INTEGER,
    goals_scored INTEGER,
    assists INTEGER,
    clean_sheets INTEGER,
    goals_conceded INTEGER,
    own_goals INTEGER,
    penalties_saved INTEGER,
    penalties_missed INTEGER,
    yellow_cards INTEGER,
    red_cards INTEGER,
    saves INTEGER,
    bonus INTEGER,
    bps INTEGER,
    influence NUMERIC,
    creativity NUMERIC,
    threat NUMERIC,
    ict_index NUMERIC,
    starts INTEGER,
    expected_goals NUMERIC,
    expected_assists NUMERIC,
    expected_goal_involvements NUMERIC,
    expected_goals_conceded NUMERIC,
    defensive_contribution INTEGER,
    value INTEGER,
    selected INTEGER,
    source TEXT NOT NULL CHECK (source IN ('github_historical', 'live_api')),
    UNIQUE (player_id, season, gameweek)
);
CREATE INDEX ix_player_gameweek_stats_season_gameweek ON player_gameweek_stats (season, gameweek);

CREATE TABLE player_current_status (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    season TEXT NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    team_id INTEGER REFERENCES team_seasons(id),
    position TEXT,
    now_cost INTEGER,
    status TEXT,
    chance_of_playing_this_round INTEGER,
    chance_of_playing_next_round INTEGER,
    news TEXT,
    form NUMERIC,
    selected_by_percent NUMERIC,
    ep_this NUMERIC,
    ep_next NUMERIC
);
CREATE INDEX ix_player_current_status_player_as_of ON player_current_status (player_id, as_of);

CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    season TEXT NOT NULL,
    gameweek INTEGER NOT NULL,
    predicted_points NUMERIC NOT NULL,
    model_version TEXT NOT NULL,
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (player_id, season, gameweek)
);
CREATE INDEX ix_predictions_season_gameweek ON predictions (season, gameweek);

CREATE TABLE model_runs (
    id SERIAL PRIMARY KEY,
    model_version TEXT NOT NULL UNIQUE,
    trained_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    training_seasons JSONB,
    hyperparams JSONB,
    validation_mae NUMERIC,
    validation_rmse NUMERIC,
    notes TEXT
);

CREATE TABLE ingestion_runs (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    season TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    rows_loaded INTEGER,
    status TEXT NOT NULL,
    error_message TEXT
);

-- +goose Down

DROP TABLE ingestion_runs;
DROP TABLE model_runs;
DROP TABLE predictions;
DROP TABLE player_current_status;
DROP TABLE player_gameweek_stats;
DROP TABLE fixtures;
DROP TABLE player_id_map;
DROP TABLE player_seasons;
DROP TABLE players;
DROP TABLE team_seasons;
DROP TABLE teams;
