import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchBins,
  fetchHealth,
  fetchMeta,
  fetchRoads,
} from "./api";
import { AnalyticsPanel } from "./components/AnalyticsPanel";
import { FilterPanel } from "./components/FilterPanel";
import type { MapViewMode } from "./components/MapViewControls";
import { TitleBar } from "./components/TitleBanner";
import { BIN_SIZE_OPTIONS } from "./constants";
import { AccidentMap, type AccidentMapHandle } from "./map/AccidentMap";
import { DEFAULT_DENSITY_STEPS, buildColorSteps, densitiesFromBins } from "./map/colorScale";
import { selectionLabel } from "./map/selection";
import type { FilterState, MapSelection } from "./types";
import "./styles.css";

const queryClient = new QueryClient();

function AppInner() {
  const mapRef = useRef<AccidentMapHandle>(null);
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: fetchMeta });
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const [selection, setSelection] = useState<MapSelection>(null);
  const [viewMode, setViewMode] = useState<MapViewMode>("2d");
  const [filters, setFilters] = useState<FilterState>({
    road: "A2",
    yearFrom: 2015,
    yearTo: 2024,
    binSizeKm: 5,
  });

  const implementedRoads = useMemo(
    () => meta?.implemented_roads ?? ["A2"],
    [meta?.implemented_roads],
  );

  useEffect(() => {
    if (meta) {
      setFilters((f) => ({
        ...f,
        road: meta.target_road,
        yearFrom: meta.year_from ?? f.yearFrom,
        yearTo: meta.year_to ?? f.yearTo,
        binSizeKm: BIN_SIZE_OPTIONS.includes(f.binSizeKm as (typeof BIN_SIZE_OPTIONS)[number])
          ? f.binSizeKm
          : 5,
      }));
    }
  }, [meta]);

  useEffect(() => {
    setSelection(null);
  }, [filters.road, filters.binSizeKm, filters.yearFrom, filters.yearTo]);

  const { data: roads } = useQuery({
    queryKey: ["roads"],
    queryFn: () => fetchRoads(),
  });

  const roadImplemented = implementedRoads.includes(filters.road);

  const binsQuery = useQuery({
    queryKey: ["bins", filters.road, filters.binSizeKm, filters.yearFrom, filters.yearTo],
    queryFn: () => fetchBins(filters),
    enabled: roadImplemented,
  });

  const bbox = roads?.find((r) => r.road_number === filters.road)?.bbox ?? null;

  const colorSteps = useMemo(() => {
    if (!binsQuery.data?.features.length) return DEFAULT_DENSITY_STEPS;
    return buildColorSteps(densitiesFromBins(binsQuery.data));
  }, [binsQuery.data]);

  const activeSelectionLabel = useMemo(
    () => selectionLabel(binsQuery.data, selection),
    [binsQuery.data, selection],
  );

  return (
    <div className="app-shell">
      <div className="app-map-layer">
        {binsQuery.error && (
          <div className="error-banner">{(binsQuery.error as Error).message}</div>
        )}
        <AccidentMap
          ref={mapRef}
          bins={binsQuery.data}
          colorSteps={colorSteps}
          selection={selection}
          viewMode={viewMode}
          bbox={bbox}
          loading={binsQuery.isLoading || binsQuery.isFetching}
          onSelect={setSelection}
        />
      </div>

      <TitleBar
        road={filters.road}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        onRotateLeft={() => mapRef.current?.rotateLeft()}
        onRotateRight={() => mapRef.current?.rotateRight()}
      />

      <AnalyticsPanel
        bins={binsQuery.data}
        binsFilter={binsQuery.data?.filter}
        colorSteps={colorSteps}
        yearFrom={filters.yearFrom}
        yearTo={filters.yearTo}
        selection={selection}
        selectionLabel={activeSelectionLabel}
        onSelect={setSelection}
      />

      <FilterPanel
        meta={meta}
        health={health}
        roads={roads}
        filters={filters}
        binsFilter={binsQuery.data?.filter}
        binsLoading={binsQuery.isFetching}
        colorSteps={colorSteps}
        onChange={(patch) => setFilters((f) => ({ ...f, ...patch }))}
      />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppInner />
    </QueryClientProvider>
  );
}
