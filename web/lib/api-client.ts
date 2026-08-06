import type {
  CurrentGameweek,
  Fixture,
  Player,
  PlayerPrediction,
  Prediction,
  Team,
} from "@/types/api";

type Envelope = {
  data: unknown;
  error: { code: string; message: string } | null;
  meta: unknown;
};

function isEnvelope(value: unknown): value is Envelope {
  if (typeof value !== "object" || value === null) return false;
  return "data" in value && "error" in value;
}

function apiBaseUrl(): string {
  const base = process.env.API_BASE_URL;
  if (!base) {
    throw new Error("API_BASE_URL is not set (server-only env var, see .env.example)");
  }
  return base;
}

async function apiFetch<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const url = new URL(path, apiBaseUrl());
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }

  const response = await fetch(url.toString());
  const body: unknown = await response.json();

  if (!isEnvelope(body)) {
    throw new Error(`Unexpected response shape from ${url.pathname}`);
  }
  if (body.error) {
    throw new Error(`${body.error.code}: ${body.error.message}`);
  }
  return body.data as T;
}

export function getCurrentGameweek(season: string): Promise<CurrentGameweek> {
  return apiFetch<CurrentGameweek>("/api/v1/gameweeks/current", { season });
}

export function getPredictions(
  season: string,
  gameweek: number,
  filters?: { position?: string; team?: string },
): Promise<Prediction[]> {
  return apiFetch<Prediction[]>("/api/v1/predictions", {
    season,
    gameweek,
    position: filters?.position,
    team: filters?.team,
  });
}

export function getFixtures(season: string, gameweek?: number): Promise<Fixture[]> {
  return apiFetch<Fixture[]>("/api/v1/fixtures", { season, gameweek });
}

export function getPlayers(): Promise<Player[]> {
  return apiFetch<Player[]>("/api/v1/players");
}

export function getPlayer(id: number): Promise<Player> {
  return apiFetch<Player>(`/api/v1/players/${id}`);
}

export function getPlayerPredictions(
  id: number,
  season: string,
  fromGameweek: number,
  horizon?: number,
): Promise<PlayerPrediction[]> {
  return apiFetch<PlayerPrediction[]>(`/api/v1/players/${id}/predictions`, {
    season,
    from_gameweek: fromGameweek,
    horizon,
  });
}

export function getTeams(): Promise<Team[]> {
  return apiFetch<Team[]>("/api/v1/teams");
}
