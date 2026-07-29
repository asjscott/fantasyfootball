import { getPlayer } from "@/lib/api-client";
import { ErrorNotice } from "@/components/ErrorNotice";
import type { Player } from "@/types/api";

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let player: Player;
  try {
    player = await getPlayer(Number(id));
  } catch (error) {
    return (
      <div className="p-6">
        <ErrorNotice message={error instanceof Error ? error.message : String(error)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 p-6">
      <h1 className="text-xl font-semibold">
        {player.web_name ?? `${player.first_name ?? ""} ${player.second_name ?? ""}`.trim()}
      </h1>
      <p className="text-sm text-gray-600">
        {player.first_name} {player.second_name}
      </p>
    </div>
  );
}
