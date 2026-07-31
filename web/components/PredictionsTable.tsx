import Link from "next/link";

import type { Prediction } from "@/types/api";

export function PredictionsTable({ predictions }: { predictions: Prediction[] }) {
  if (predictions.length === 0) {
    return <p className="text-sm text-gray-500">No predictions for this gameweek yet.</p>;
  }

  const hasActuals = predictions.some((prediction) => prediction.actual_points !== null);

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-gray-200 text-gray-500">
          <th className="py-2 pr-4">Player</th>
          <th className="py-2 pr-4">Team</th>
          <th className="py-2 pr-4">Position</th>
          <th className="py-2 pr-4 text-right">Predicted points</th>
          {hasActuals && <th className="py-2 pr-4 text-right">Actual points</th>}
          {hasActuals && <th className="py-2 pr-4 text-right">Difference</th>}
        </tr>
      </thead>
      <tbody>
        {predictions.map((prediction) => {
          const diff =
            prediction.actual_points === null
              ? null
              : prediction.predicted_points - prediction.actual_points;

          return (
            <tr key={prediction.player_id} className="border-b border-gray-100">
              <td className="py-2 pr-4">
                <Link href={`/players/${prediction.player_id}`} className="hover:underline">
                  {prediction.web_name ?? `Player ${prediction.player_id}`}
                </Link>
              </td>
              <td className="py-2 pr-4">{prediction.team}</td>
              <td className="py-2 pr-4">{prediction.position}</td>
              <td className="py-2 pr-4 text-right">{prediction.predicted_points.toFixed(1)}</td>
              {hasActuals && (
                <td className="py-2 pr-4 text-right">
                  {prediction.actual_points === null ? "—" : prediction.actual_points}
                </td>
              )}
              {hasActuals && (
                <td className="py-2 pr-4 text-right">{diff === null ? "—" : diff.toFixed(1)}</td>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
