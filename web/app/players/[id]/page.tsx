import { getCurrentGameweek, getPlayer, getPlayerPredictions } from "@/lib/api-client";
import { ErrorNotice } from "@/components/ErrorNotice";
import { PlayerPredictionsTable } from "@/components/PlayerPredictionsTable";
import { CURRENT_SEASON } from "@/lib/constants";
import type { Player, PlayerPrediction } from "@/types/api";

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let player: Player;
  let predictions: PlayerPrediction[];
  try {
    player = await getPlayer(Number(id));
    const gameweek = await getCurrentGameweek(CURRENT_SEASON);
    predictions = await getPlayerPredictions(Number(id), gameweek.season, gameweek.gameweek, 5);
  } catch (error) {
    return (
      <div className="p-6">
        <ErrorNotice message={error instanceof Error ? error.message : String(error)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div>
        <h1 className="text-xl font-semibold">
          {player.web_name ?? `${player.first_name ?? ""} ${player.second_name ?? ""}`.trim()}
        </h1>
        <p className="text-sm text-gray-600">
          {player.first_name} {player.second_name}
        </p>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-medium text-gray-500">Upcoming gameweeks</h2>
        <PlayerPredictionsTable predictions={predictions} />
      </div>
    </div>
  );
}
