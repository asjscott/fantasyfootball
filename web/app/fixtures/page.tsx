import { getCurrentGameweek, getFixtures } from "@/lib/api-client";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FixturesTable } from "@/components/FixturesTable";
import { CURRENT_SEASON } from "@/lib/constants";
import type { Fixture } from "@/types/api";

type SearchParams = {
  season?: string;
  gameweek?: string;
};

export default async function FixturesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;

  let season: string;
  let gameweek: number | undefined;
  let fixtures: Fixture[];
  try {
    season = params.season ?? (await getCurrentGameweek(CURRENT_SEASON)).season;
    gameweek = params.gameweek ? Number(params.gameweek) : undefined;
    fixtures = await getFixtures(season, gameweek);
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
        Fixtures — {season}
        {gameweek ? ` GW${gameweek}` : ""}
      </h1>

      <form className="flex flex-wrap items-end gap-3 text-sm" action="/fixtures">
        <input type="hidden" name="season" value={season} />
        <label className="flex flex-col gap-1">
          Gameweek (optional)
          <input
            type="number"
            name="gameweek"
            defaultValue={gameweek}
            min={1}
            max={38}
            className="rounded border border-gray-300 px-2 py-1"
          />
        </label>
        <button
          type="submit"
          className="rounded bg-black px-3 py-1.5 text-white hover:bg-gray-800"
        >
          Apply filter
        </button>
      </form>

      <FixturesTable fixtures={fixtures} />
    </div>
  );
}
