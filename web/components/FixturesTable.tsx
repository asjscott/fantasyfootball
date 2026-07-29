import type { Fixture } from "@/types/api";

export function FixturesTable({ fixtures }: { fixtures: Fixture[] }) {
  if (fixtures.length === 0) {
    return <p className="text-sm text-gray-500">No fixtures for this gameweek yet.</p>;
  }

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-gray-200 text-gray-500">
          <th className="py-2 pr-4">Gameweek</th>
          <th className="py-2 pr-4">Fixture</th>
          <th className="py-2 pr-4">Kickoff</th>
          <th className="py-2 pr-4">Score</th>
        </tr>
      </thead>
      <tbody>
        {fixtures.map((fixture) => (
          <tr key={fixture.id} className="border-b border-gray-100">
            <td className="py-2 pr-4">{fixture.gameweek ?? "-"}</td>
            <td className="py-2 pr-4">
              {fixture.home_team} vs {fixture.away_team}
            </td>
            <td className="py-2 pr-4">
              {fixture.kickoff_time ? new Date(fixture.kickoff_time).toLocaleString() : "TBD"}
            </td>
            <td className="py-2 pr-4">
              {fixture.finished
                ? `${fixture.home_score ?? "-"} - ${fixture.away_score ?? "-"}`
                : "Not played"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
