import { densityPerKmYear } from "../map/density";
import type { SelectedBin, StatsResponse } from "../types";

interface StatsPanelProps {
  stats: StatsResponse | undefined;
  selectedBin: SelectedBin | null;
}

export function StatsPanel({ stats, selectedBin }: StatsPanelProps) {
  return (
    <div className="stats-panel">
      <h3>Statistieken</h3>
      {selectedBin ? (
        <div className="selected-bin">
          <h4>Geselecteerde bin</h4>
          <p>
            {selectedBin.road_number} · km { (selectedBin.bin_start_m / 1000).toFixed(1)}–
            {(selectedBin.bin_end_m / 1000).toFixed(1)}
          </p>
          <p>
            Ongevallen: <strong>{selectedBin.accident_count}</strong> · Dichtheid:{" "}
            {densityPerKmYear({ ...selectedBin }).toFixed(2)}/km/jaar
            {selectedBin.year_span > 1 ? ` (gem. over ${selectedBin.year_span} jr)` : ""}
          </p>
          <p className="muted">{selectedBin.geometry_quality}</p>
        </div>
      ) : (
        <p className="muted">Klik op een bin voor details.</p>
      )}

      {stats && (
        <>
          <p>
            Totaal {stats.road_number}:{" "}
            <strong>{stats.total_accidents.toLocaleString("nl-NL")}</strong>
          </p>
          <p className="muted">
            Onopgelost: {stats.unresolved_accidents.toLocaleString("nl-NL")}
          </p>
          <h4>Top bins (1 km)</h4>
          <ol className="top-bins">
            {stats.top_bins.slice(0, 5).map((b) => (
              <li key={b.bin_id}>
                {(b.bin_start_m / 1000).toFixed(0)}–{(b.bin_end_m / 1000).toFixed(0)} km: {b.accident_count}
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
