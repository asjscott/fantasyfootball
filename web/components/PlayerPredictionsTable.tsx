import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import type { PlayerPrediction } from "@/types/api";

export function PlayerPredictionsTable({ predictions }: { predictions: PlayerPrediction[] }) {
  if (predictions.length === 0) {
    return <p className="text-sm text-gray-500">No upcoming predictions yet.</p>;
  }

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-gray-200 text-gray-500">
          <th className="py-2 pr-4">Gameweek</th>
          <th className="py-2 pr-4 text-right">Predicted points</th>
          <th className="py-2 pr-4">Confidence</th>
          <th className="py-2 pr-4 text-right">Actual points</th>
        </tr>
      </thead>
      <tbody>
        {predictions.map((prediction) => (
          <tr key={prediction.gameweek} className="border-b border-gray-100">
            <td className="py-2 pr-4">GW{prediction.gameweek}</td>
            <td className="py-2 pr-4 text-right">{prediction.predicted_points.toFixed(1)}</td>
            <td className="py-2 pr-4">
              <ConfidenceBadge confidence={prediction.confidence} />
            </td>
            <td className="py-2 pr-4 text-right">
              {prediction.actual_points === null ? "—" : prediction.actual_points}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
