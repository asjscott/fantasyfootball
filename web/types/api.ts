export type Team = {
  id: number;
  name: string;
};

export type Player = {
  id: number;
  first_name: string | null;
  second_name: string | null;
  web_name: string | null;
};

export type Fixture = {
  id: number;
  season: string;
  gameweek: number | null;
  kickoff_time: string | null;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  finished: boolean;
  home_difficulty: number | null;
  away_difficulty: number | null;
};

export type Prediction = {
  player_id: number;
  web_name: string | null;
  team: string;
  position: string;
  season: string;
  gameweek: number;
  predicted_points: number;
  model_version: string;
  // null until the gameweek has actually been played (historical/backtest
  // gameweeks have it; future ones don't).
  actual_points: number | null;
};

export type CurrentGameweek = {
  season: string;
  gameweek: number;
};
