import { getCurrentGameweek, getPredictions } from "@/lib/api-client";
import { ErrorNotice } from "@/components/ErrorNotice";
import { PredictionsTable } from "@/components/PredictionsTable";
import { CURRENT_SEASON } from "@/lib/constants";
import type { Prediction } from "@/types/api";

const POSITIONS = ["GK", "DEF", "MID", "FWD"];

type SearchParams = {
  season?: string;
  gameweek?: string;
  position?: string;
  team?: string;
};

export default async function PredictionsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;

  let season: string;
  let gameweek: number;
  let predictions: Prediction[];
  try {
    season = params.season ?? (await getCurrentGameweek(CURRENT_SEASON)).season;
    gameweek = params.gameweek
      ? Number(params.gameweek)
      : (await getCurrentGameweek(season)).gameweek;
    predictions = await getPredictions(season, gameweek, {
      position: params.position || undefined,
      team: params.team || undefined,
    });
  } catch (error) {
    return (
      <div className="p-6">
        <ErrorNotice message={error instanceof Error ? error.message : String(error)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-xl font-semibold">
        Predictions — {season} GW{gameweek}
      </h1>

      <form className="flex flex-wrap items-end gap-3 text-sm" action="/predictions">
        <input type="hidden" name="season" value={season} />
        <label className="flex flex-col gap-1">
          Gameweek
          <input
            type="number"
            name="gameweek"
            defaultValue={gameweek}
            min={1}
            max={38}
            className="rounded border border-gray-300 px-2 py-1"
          />
        </label>
        <label className="flex flex-col gap-1">
          Position
          <select
            name="position"
            defaultValue={params.position ?? ""}
            className="rounded border border-gray-300 px-2 py-1"
          >
            <option value="">All</option>
            {POSITIONS.map((position) => (
              <option key={position} value={position}>
                {position}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Team
          <input
            type="text"
            name="team"
            defaultValue={params.team ?? ""}
            placeholder="e.g. Arsenal"
            className="rounded border border-gray-300 px-2 py-1"
          />
        </label>
        <button
          type="submit"
          className="rounded bg-black px-3 py-1.5 text-white hover:bg-gray-800"
        >
          Apply filters
        </button>
      </form>

      <PredictionsTable predictions={predictions} />
    </div>
  );
}
