import Link from "next/link";

import { getCurrentGameweek, getPredictions } from "@/lib/api-client";
import { ErrorNotice } from "@/components/ErrorNotice";
import { PredictionsTable } from "@/components/PredictionsTable";
import { CURRENT_SEASON } from "@/lib/constants";
import type { CurrentGameweek, Prediction } from "@/types/api";

export default async function HomePage() {
  let gameweek: CurrentGameweek;
  let predictions: Prediction[];
  try {
    gameweek = await getCurrentGameweek(CURRENT_SEASON);
    predictions = await getPredictions(gameweek.season, gameweek.gameweek);
  } catch (error) {
    return (
      <div className="p-6">
        <ErrorNotice message={error instanceof Error ? error.message : String(error)} />
      </div>
    );
  }

  const topPredictions = predictions.slice(0, 20);

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-xl font-semibold">
        Top predicted points — {gameweek.season} GW{gameweek.gameweek}
      </h1>
      <PredictionsTable predictions={topPredictions} />
      <Link href="/predictions" className="text-sm hover:underline">
        See all predictions with filters &rarr;
      </Link>
    </div>
  );
}
