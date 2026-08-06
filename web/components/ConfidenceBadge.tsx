// Thresholds mirror ml/validate_confidence.py's bucketing (_HIGH_THRESHOLD /
// _MEDIUM_THRESHOLD) — kept in sync by convention, not shared code, since
// Python and TypeScript don't share a module here.
function bucket(confidence: number): "High" | "Medium" | "Low" {
  if (confidence >= 0.7) return "High";
  if (confidence >= 0.4) return "Medium";
  return "Low";
}

const BUCKET_STYLES: Record<string, string> = {
  High: "bg-green-100 text-green-800",
  Medium: "bg-yellow-100 text-yellow-800",
  Low: "bg-red-100 text-red-800",
};

export function ConfidenceBadge({ confidence }: { confidence: number | null }) {
  if (confidence === null) {
    return <span className="text-xs text-gray-400">—</span>;
  }

  const label = bucket(confidence);
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${BUCKET_STYLES[label]}`}
      title="Playing-time certainty — how likely this player is to get real minutes, not points-prediction accuracy"
    >
      {label}
    </span>
  );
}
