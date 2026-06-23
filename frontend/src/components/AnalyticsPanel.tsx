import { useMemo, useState } from "react";
import { colorForDensity } from "../map/colorScale";
import type { ColorStep } from "../map/colorScale";
import { isBarHighlighted } from "../map/selection";
import { CollapsiblePanel } from "./CollapsiblePanel";
import type { GeoJSONFeatureCollection, MapSelection } from "../types";

export type BarChartSort = "km" | "accidents";

interface BinBarChartProps {
  bins: GeoJSONFeatureCollection | undefined;
  colorSteps: ColorStep[];
  selection: MapSelection;
  sortBy: BarChartSort;
  onSelect: (selection: MapSelection) => void;
}

interface ChartBar {
  id: string;
  startKm: number;
  endKm: number;
  startM: number;
  endM: number;
  density: number;
  count: number;
}

export function BinBarChart({ bins, colorSteps, selection, sortBy, onSelect }: BinBarChartProps) {
  const bars = useMemo<ChartBar[]>(() => {
    if (!bins) return [];
    const mapped = bins.features.map((feature) => ({
      id: feature.properties.bin_id,
      startKm: feature.properties.bin_start_m / 1000,
      endKm: feature.properties.bin_end_m / 1000,
      startM: feature.properties.bin_start_m,
      endM: feature.properties.bin_end_m,
      density: feature.properties.density_per_km_year,
      count: feature.properties.accident_count,
    }));

    if (sortBy === "accidents") {
      return [...mapped].sort((a, b) => b.count - a.count || a.startM - b.startM);
    }
    return [...mapped].sort((a, b) => a.startM - b.startM);
  }, [bins, sortBy]);

  const maxBarValue = useMemo(() => {
    if (!bars.length) return 1;
    if (sortBy === "accidents") {
      return Math.max(...bars.map((bar) => bar.count), 1);
    }
    return Math.max(...bars.map((bar) => bar.density), 1);
  }, [bars, sortBy]);

  if (!bars.length) {
    return <p className="muted chart-empty">Geen bins om te tonen.</p>;
  }

  const axisStart =
    sortBy === "km"
      ? `${bars[0].startKm.toFixed(0)} km`
      : `${bars[0].count} ong.`;
  const axisEnd =
    sortBy === "km"
      ? `${bars[bars.length - 1].endKm.toFixed(0)} km`
      : `${bars[bars.length - 1].count} ong.`;

  return (
    <div className="bin-bar-chart">
      <div className="bin-bar-chart-scroll">
        <div className="bin-bar-chart-bars" style={{ minWidth: `${bars.length * 18}px` }}>
          {bars.map((bar) => {
            const barValue = sortBy === "accidents" ? bar.count : bar.density;
            const heightPct = Math.max((barValue / maxBarValue) * 100, barValue > 0 ? 4 : 0);
            const isSelected = isBarHighlighted(selection, bar.id, bar.startM, bar.endM);
            return (
              <button
                key={bar.id}
                type="button"
                className={`bin-bar ${isSelected ? "selected" : ""}`}
                title={`km ${bar.startKm.toFixed(1)}–${bar.endKm.toFixed(1)} · ${bar.density.toFixed(1)}/km/jaar · ${bar.count} ongevallen`}
                onClick={() =>
                  onSelect(isSelected ? null : { type: "bin", binId: bar.id })
                }
              >
                <span
                  className="bin-bar-fill"
                  style={{
                    height: `${heightPct}%`,
                    background: colorForDensity(bar.density, colorSteps),
                  }}
                />
              </button>
            );
          })}
        </div>
      </div>
      <div className="bin-bar-chart-axis muted">
        <span>{axisStart}</span>
        <span>{sortBy === "accidents" ? "gesorteerd op ongevallen" : ""}</span>
        <span>{axisEnd}</span>
      </div>
    </div>
  );
}

interface AnalyticsPanelProps {
  bins: GeoJSONFeatureCollection | undefined;
  binsFilter: GeoJSONFeatureCollection["filter"];
  colorSteps: ColorStep[];
  yearFrom: number;
  yearTo: number;
  selection: MapSelection;
  selectionLabel: string | null;
  onSelect: (selection: MapSelection) => void;
}

export function AnalyticsPanel({
  bins,
  binsFilter,
  colorSteps,
  yearFrom,
  yearTo,
  selection,
  selectionLabel,
  onSelect,
}: AnalyticsPanelProps) {
  const [chartSort, setChartSort] = useState<BarChartSort>("km");
  const yearSpan = Math.max(yearTo - yearFrom + 1, 1);
  const bars = bins?.features ?? [];
  const densities = bars.map((f) => f.properties.density_per_km_year);
  const totalAccidents = binsFilter?.accident_count ?? 0;
  const avgDensity = densities.length
    ? densities.reduce((sum, value) => sum + value, 0) / densities.length
    : 0;
  const maxBin = bars.length
    ? [...bars].sort((a, b) => b.properties.density_per_km_year - a.properties.density_per_km_year)[0]
    : null;

  return (
    <CollapsiblePanel title="Analyse" side="left">
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Ongevallen</span>
          <strong className="kpi-value">{totalAccidents.toLocaleString("nl-NL")}</strong>
          <span className="kpi-hint muted">{yearFrom}–{yearTo}</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Gem. dichtheid</span>
          <strong className="kpi-value">{avgDensity.toFixed(1)}</strong>
          <span className="kpi-hint muted">/km/jaar</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Bins</span>
          <strong className="kpi-value">{bars.length}</strong>
          <span className="kpi-hint muted">{yearSpan} jr gemiddeld</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Piek</span>
          <strong className="kpi-value">
            {maxBin ? maxBin.properties.density_per_km_year.toFixed(1) : "—"}
          </strong>
          <span className="kpi-hint muted">
            {maxBin
              ? `km ${(maxBin.properties.bin_start_m / 1000).toFixed(1)}–${(maxBin.properties.bin_end_m / 1000).toFixed(1)}`
              : "—"}
          </span>
        </div>
      </div>

      <section className="analytics-section">
        <div className="section-heading-row">
          <h3>Dichtheid per bin</h3>
          <div className="pill-group pill-group--compact" role="group" aria-label="Sorteer grafiek">
            <button
              type="button"
              className={`pill ${chartSort === "km" ? "active" : ""}`}
              onClick={() => setChartSort("km")}
            >
              Km
            </button>
            <button
              type="button"
              className={`pill ${chartSort === "accidents" ? "active" : ""}`}
              onClick={() => setChartSort("accidents")}
            >
              Ongevallen
            </button>
          </div>
        </div>
        <p className="section-hint muted">Klik op een staaf om het traject op de kaart te markeren.</p>
        <BinBarChart
          bins={bins}
          colorSteps={colorSteps}
          selection={selection}
          sortBy={chartSort}
          onSelect={onSelect}
        />
      </section>

      {selection && selectionLabel && (
        <section className="analytics-section selected-bin-card">
          <h3>Geselecteerd op kaart</h3>
          <p>{selectionLabel}</p>
          <button type="button" className="clear-selection" onClick={() => onSelect(null)}>
            Selectie wissen
          </button>
        </section>
      )}
    </CollapsiblePanel>
  );
}
