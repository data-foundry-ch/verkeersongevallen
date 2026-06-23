import type { BinsFilterMeta, FilterState, MetaResponse } from "../types";
import type { HealthResponse } from "../api";

interface ControlsProps {
  meta: MetaResponse | undefined;
  health: HealthResponse | undefined;
  filters: FilterState;
  binsFilter: BinsFilterMeta | undefined;
  binsLoading: boolean;
  onChange: (patch: Partial<FilterState>) => void;
}

export function Controls({ meta, health, filters, binsFilter, binsLoading, onChange }: ControlsProps) {
  const apiOk = health?.api_version === "0.1.9";
  const geometryDirection = meta?.geometry_direction ?? "H";

  return (
    <div className="controls">
      <p className="mvp-label">MVP target road: A2</p>
      <h1>Verkeersongevallen A2</h1>

      {health && !apiOk && (
        <p className="filter-status warn">
          Backend is verouderd (v{health.api_version ?? "?"}). Sluit het backend-venster en start opnieuw:{" "}
          <code>.\make.ps1 backend</code>
        </p>
      )}

      <label className="field">
        <span>Jaar van</span>
        <input
          type="number"
          value={filters.yearFrom}
          min={meta?.year_from ?? 2000}
          max={filters.yearTo}
          onChange={(e) => onChange({ yearFrom: Number(e.target.value) })}
        />
      </label>

      <label className="field">
        <span>Jaar tot</span>
        <input
          type="number"
          value={filters.yearTo}
          min={filters.yearFrom}
          max={meta?.year_to ?? 2030}
          onChange={(e) => onChange({ yearTo: Number(e.target.value) })}
        />
      </label>

      <label className="field">
        <span>Bin-grootte (km)</span>
        <select
          value={filters.binSizeKm}
          onChange={(e) => onChange({ binSizeKm: Number(e.target.value) })}
        >
          {(meta?.bin_sizes_km ?? [1, 2, 5, 10, 20]).map((s) => (
            <option key={s} value={s}>
              {s} km
            </option>
          ))}
        </select>
      </label>

      <span className="field-hint muted">
        De kaart volgt officiële hectometer-km (NWB) op de {geometryDirection}-rijbaan;
        ongevallen van beide rijrichtingen (H+T) worden samengeteld.
      </span>

      {binsLoading && (
        <p className="filter-status muted">Bins herberekenen… (kan ~30 s duren)</p>
      )}

      {binsFilter && !binsLoading && (
        <p className="filter-status muted">
          Kaart: {binsFilter.feature_count} bins ·{" "}
          {binsFilter.accident_count.toLocaleString("nl-NL")} ongevallen
        </p>
      )}

      {meta && (
        <div className="meta-summary">
          <p>
            A2 ongevallen: <strong>{meta.a2_accident_count.toLocaleString("nl-NL")}</strong>
          </p>
          <p className="muted">
            Onopgelost: {meta.a2_unresolved_count.toLocaleString("nl-NL")} · Segmenten:{" "}
            {(meta.a2_mainroad_segment_count ?? meta.a2_segment_count).toLocaleString("nl-NL")} hoofdrijbaan
          </p>
        </div>
      )}
    </div>
  );
}
