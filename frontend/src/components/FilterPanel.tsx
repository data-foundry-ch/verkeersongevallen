import type { HealthResponse } from "../api";
import { BIN_SIZE_OPTIONS } from "../constants";
import type { ColorStep } from "../map/colorScale";
import type { BinsFilterMeta, FilterState, MetaResponse, RoadSummary } from "../types";
import { CollapsiblePanel } from "./CollapsiblePanel";
import { Legend } from "./Legend";

interface FilterPanelProps {
  meta: MetaResponse | undefined;
  health: HealthResponse | undefined;
  roads: RoadSummary[] | undefined;
  filters: FilterState;
  binsFilter: BinsFilterMeta | undefined;
  binsLoading: boolean;
  colorSteps: ColorStep[];
  onChange: (patch: Partial<FilterState>) => void;
}

export function FilterPanel({
  meta,
  health,
  roads,
  filters,
  binsFilter,
  binsLoading,
  colorSteps,
  onChange,
}: FilterPanelProps) {
  const apiOk = !health || health.status === "ok" || health.duckdb_ok;
  const minYear = meta?.year_from ?? 2000;
  const maxYear = meta?.year_to ?? 2030;
  const roadOptions = roads?.length ? roads : [{ road_number: "A2", status: "implemented" as const }];

  return (
    <CollapsiblePanel title="Filters" side="right">
      {health && !apiOk && (
        <p className="filter-status warn">
          Backend v{health.api_version ?? "?"} — herstart met <code>.\make.ps1 backend</code>
        </p>
      )}

      <label className="field">
        <span>Weg</span>
        <select
          value={filters.road}
          onChange={(e) => onChange({ road: e.target.value })}
        >
          {roadOptions.map((road) => (
            <option
              key={road.road_number}
              value={road.road_number}
              disabled={road.status !== "implemented"}
            >
              {road.road_number}
              {road.status !== "implemented" ? " (binnenkort)" : ""}
            </option>
          ))}
        </select>
      </label>

      <div className="field">
        <span>Periode</span>
        <div className="year-range-value">
          {filters.yearFrom} – {filters.yearTo}
        </div>
        <div className="year-range-sliders">
          <input
            type="range"
            className="year-range-input"
            min={minYear}
            max={maxYear}
            value={filters.yearFrom}
            onChange={(e) => {
              const yearFrom = Number(e.target.value);
              onChange({
                yearFrom,
                yearTo: Math.max(yearFrom, filters.yearTo),
              });
            }}
          />
          <input
            type="range"
            className="year-range-input"
            min={minYear}
            max={maxYear}
            value={filters.yearTo}
            onChange={(e) => {
              const yearTo = Number(e.target.value);
              onChange({
                yearTo,
                yearFrom: Math.min(filters.yearFrom, yearTo),
              });
            }}
          />
        </div>
        <div className="year-range-bounds muted">
          {minYear} – {maxYear}
        </div>
      </div>

      <div className="field">
        <span>Bin-grootte</span>
        <div className="pill-group" role="group" aria-label="Bin-grootte">
          {BIN_SIZE_OPTIONS.map((size) => (
            <button
              key={size}
              type="button"
              className={`pill ${filters.binSizeKm === size ? "active" : ""}`}
              onClick={() => onChange({ binSizeKm: size })}
            >
              {size} km
            </button>
          ))}
        </div>
      </div>

      {binsLoading && <p className="filter-status muted">Bins herberekenen…</p>}

      {binsFilter && !binsLoading && (
        <p className="filter-status muted">
          {binsFilter.feature_count} bins · {binsFilter.accident_count.toLocaleString("nl-NL")} ongevallen
        </p>
      )}

      <section className="legend-section">
        <Legend steps={colorSteps} />
      </section>
    </CollapsiblePanel>
  );
}
