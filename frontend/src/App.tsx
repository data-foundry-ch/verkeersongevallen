import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchBins,
  fetchHealth,
  fetchMeta,
  fetchRoads,
} from "./api";
import { AnalyticsPanel } from "./components/AnalyticsPanel";
import { BottomSheet } from "./components/BottomSheet";
import { FilterPanel } from "./components/FilterPanel";
import type { MapViewMode } from "./components/MapViewControls";
import { MapViewControls } from "./components/MapViewControls";
import { MobileDock, type MobileSheet } from "./components/MobileDock";
import { TitleBar } from "./components/TitleBanner";
import { BIN_SIZE_OPTIONS } from "./constants";
import { MOBILE_MEDIA_QUERY, useMediaQuery } from "./hooks/useMediaQuery";
import { AccidentMap, type AccidentMapHandle } from "./map/AccidentMap";
import { DEFAULT_DENSITY_STEPS, buildColorSteps, densitiesFromBins } from "./map/colorScale";
import { selectionLabel } from "./map/selection";
import type { FilterState, MapSelection } from "./types";
import "./styles.css";

const queryClient = new QueryClient();

function initialViewMode(): MapViewMode {
  if (typeof window === "undefined") return "2d";
  return window.matchMedia(MOBILE_MEDIA_QUERY).matches ? "3d" : "2d";
}

function AppInner() {
  const mapRef = useRef<AccidentMapHandle>(null);
  const isMobile = useMediaQuery(MOBILE_MEDIA_QUERY);
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: fetchMeta });
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const [selection, setSelection] = useState<MapSelection>(null);
  const [viewMode, setViewMode] = useState<MapViewMode>(initialViewMode);
  const [mobileSheet, setMobileSheet] = useState<MobileSheet>(null);
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

  useEffect(() => {
    if (!isMobile) {
      setMobileSheet(null);
    }
  }, [isMobile]);

  useEffect(() => {
    if (!mobileSheet) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileSheet(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileSheet]);

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

  const analyticsProps = {
    bins: binsQuery.data,
    binsFilter: binsQuery.data?.filter,
    colorSteps,
    yearFrom: filters.yearFrom,
    yearTo: filters.yearTo,
    selection,
    selectionLabel: activeSelectionLabel,
    onSelect: setSelection,
  };

  const filterProps = {
    meta,
    health,
    roads,
    filters,
    binsFilter: binsQuery.data?.filter,
    binsLoading: binsQuery.isFetching,
    colorSteps,
    onChange: (patch: Partial<FilterState>) => setFilters((f) => ({ ...f, ...patch })),
  };

  const toggleSheet = (sheet: Exclude<MobileSheet, null>) => {
    setMobileSheet((current) => (current === sheet ? null : sheet));
  };

  return (
    <div className={`app-shell ${isMobile ? "app-shell--mobile" : ""}`}>
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
          mobile={isMobile}
          sheetOpen={mobileSheet !== null}
        />
      </div>

      <TitleBar
        road={filters.road}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        onRotateLeft={() => mapRef.current?.rotateLeft()}
        onRotateRight={() => mapRef.current?.rotateRight()}
        compact={isMobile}
        showViewControls={!isMobile}
      />

      <a
        className="showcase-logo-link"
        href={import.meta.env.VITE_MARKETING_URL ?? "https://datafoundry.ch"}
        target="_blank"
        rel="noopener noreferrer"
      >
        <img className="showcase-logo" src="/datafoundry-logo.png" alt="DataFoundry" />
      </a>

      {isMobile ? (
        <>
          <div className="mobile-map-controls">
            <MapViewControls
              viewMode={viewMode}
              onViewModeChange={setViewMode}
              onRotateLeft={() => mapRef.current?.rotateLeft()}
              onRotateRight={() => mapRef.current?.rotateRight()}
            />
          </div>
          <MobileDock
            active={mobileSheet}
            onAnalyse={() => toggleSheet("analyse")}
            onFilters={() => toggleSheet("filters")}
          />
          <BottomSheet
            open={mobileSheet === "analyse"}
            title="Analyse"
            onClose={() => setMobileSheet(null)}
          >
            <AnalyticsPanel {...analyticsProps} variant="sheet" />
          </BottomSheet>
          <BottomSheet
            open={mobileSheet === "filters"}
            title="Filters"
            onClose={() => setMobileSheet(null)}
          >
            <FilterPanel {...filterProps} variant="sheet" />
          </BottomSheet>
        </>
      ) : (
        <>
          <AnalyticsPanel {...analyticsProps} />
          <FilterPanel {...filterProps} />
        </>
      )}
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
