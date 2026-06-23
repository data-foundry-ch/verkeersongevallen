import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import maplibregl, { Map, Popup } from "maplibre-gl";
import type { MapViewMode } from "../components/MapViewControls";
import type { GeoJSONFeatureCollection, MapSelection, SelectedBin } from "../types";
import type { ColorStep } from "./colorScale";
import { binsToExtrusionPolygons } from "./bins3d";
import {
  BIN_EXTRUSION_LAYER_ID,
  BIN_EXTRUSION_SOURCE_ID,
  BIN_HIGHLIGHT_LAYER_ID,
  BIN_HIGHLIGHT_SOURCE_ID,
  BIN_LAYER_ID,
  BIN_SOURCE_ID,
  binExtrusionColorPaint,
  binExtrusionLayerPaint,
  binHighlightLayerPaint,
  binLayerPaint,
} from "./layers";
import { EXTRUSION_METERS_PER_DENSITY } from "./colorScale";
import { formatDensityPerKmYear } from "./density";
import { installOrbitControls, rotateBearing } from "./mapOrbit";
import { MAP_STYLE } from "./mapStyle";
import { boundsFromFeatures, highlightFeatures, selectionBinIds } from "./selection";

export interface AccidentMapHandle {
  rotateLeft: () => void;
  rotateRight: () => void;
}

/** MapLibre only accepts standard GeoJSON — strip API metadata like `filter`. */
function toMapGeoJson(fc: GeoJSONFeatureCollection): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: fc.features };
}

const PITCH_LOD_THRESHOLD = 25;
const VIEW_3D_PITCH = 60;
const VIEW_3D_BEARING = -25;

function interactiveLayerIds(mode: MapViewMode): string[] {
  return mode === "3d"
    ? [BIN_EXTRUSION_LAYER_ID, BIN_HIGHLIGHT_LAYER_ID, BIN_LAYER_ID]
    : [BIN_HIGHLIGHT_LAYER_ID, BIN_LAYER_ID];
}

function applyViewModeSettings(map: Map, mode: MapViewMode, colorSteps: ColorStep[]) {
  const is3d = mode === "3d";

  if (map.getLayer(BIN_EXTRUSION_LAYER_ID)) {
    map.setLayoutProperty(BIN_EXTRUSION_LAYER_ID, "visibility", is3d ? "visible" : "none");
  }

  if (map.getLayer(BIN_LAYER_ID)) {
    const paint = binLayerPaint(colorSteps, is3d ? 0.35 : 0.92);
    map.setPaintProperty(BIN_LAYER_ID, "line-opacity", paint["line-opacity"]);
  }

  if (is3d) {
    map.setMaxPitch(85);
    map.touchPitch.enable();
    map.dragRotate.enable();
  } else {
    map.setMaxPitch(0);
    map.touchPitch.disable();
    map.dragRotate.disable();
    map.dragPan.enable();
  }
}

function animateToViewMode(map: Map, mode: MapViewMode) {
  if (mode === "3d") {
    map.easeTo({ pitch: VIEW_3D_PITCH, bearing: VIEW_3D_BEARING, duration: 800 });
  } else {
    map.easeTo({ pitch: 0, bearing: 0, duration: 800 });
  }
}

interface AccidentMapProps {
  bins: GeoJSONFeatureCollection | undefined;
  colorSteps: ColorStep[];
  selection: MapSelection;
  viewMode: MapViewMode;
  bbox: [number, number, number, number] | null | undefined;
  loading: boolean;
  onSelect: (selection: MapSelection) => void;
}

export const AccidentMap = forwardRef<AccidentMapHandle, AccidentMapProps>(function AccidentMap(
  {
    bins,
    colorSteps,
    selection,
    viewMode,
    bbox,
    loading,
    onSelect,
  },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const viewModeRef = useRef<MapViewMode>(viewMode);
  const prevViewModeRef = useRef<MapViewMode | null>(null);
  const hasFittedBboxRef = useRef(false);
  const [mapReady, setMapReady] = useState(false);

  viewModeRef.current = viewMode;

  useImperativeHandle(ref, () => ({
    rotateLeft: () => {
      const map = mapRef.current;
      if (map) rotateBearing(map, -20);
    },
    rotateRight: () => {
      const map = mapRef.current;
      if (map) rotateBearing(map, 20);
    },
  }));

  const extrusionBins = useMemo(
    () => (bins ? binsToExtrusionPolygons(bins) : undefined),
    [bins],
  );

  const highlightGeoJson = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: highlightFeatures(bins, selection),
    }),
    [bins, selection],
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [5.5, 52.1],
      zoom: 7,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
      touchPitch: false,
      dragRotate: false,
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.on("load", () => {
      map.resize();
      setMapReady(true);
    });
    map.on("error", (e) => {
      console.error("MapLibre error:", e.error?.message ?? e);
    });

    const container = containerRef.current;
    const resizeObserver =
      container &&
      new ResizeObserver(() => {
        map.resize();
      });
    resizeObserver?.observe(container);
    const onWindowResize = () => map.resize();
    window.addEventListener("resize", onWindowResize);

    const removeOrbitControls = installOrbitControls(map, {
      pitchThreshold: PITCH_LOD_THRESHOLD,
      is3d: () => viewModeRef.current === "3d",
    });
    mapRef.current = map;
    popupRef.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false });

    return () => {
      resizeObserver?.disconnect();
      window.removeEventListener("resize", onWindowResize);
      removeOrbitControls();
      map.remove();
      mapRef.current = null;
      setMapReady(false);
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    applyViewModeSettings(map, viewMode, colorSteps);

    if (prevViewModeRef.current !== viewMode) {
      animateToViewMode(map, viewMode);
      prevViewModeRef.current = viewMode;
    }
  }, [viewMode, mapReady, colorSteps]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const upsertSource = (
      id: string,
      data: GeoJSON.FeatureCollection,
      promoteId?: string,
    ) => {
      const src = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
      if (src) src.setData(data);
      else map.addSource(id, { type: "geojson", data, promoteId });
    };

    if (bins) {
      upsertSource(BIN_SOURCE_ID, toMapGeoJson(bins), "bin_id");

      if (!map.getLayer(BIN_LAYER_ID)) {
        map.addLayer({
          id: BIN_LAYER_ID,
          type: "line",
          source: BIN_SOURCE_ID,
          paint: binLayerPaint(colorSteps, viewMode === "3d" ? 0.35 : 0.92),
        });
      }
    }

    if (extrusionBins) {
      // No promoteId — bins can produce multiple extrusion polygons per bin_id.
      upsertSource(BIN_EXTRUSION_SOURCE_ID, extrusionBins);

      if (!map.getLayer(BIN_EXTRUSION_LAYER_ID) && map.getLayer(BIN_LAYER_ID)) {
        map.addLayer(
          {
            id: BIN_EXTRUSION_LAYER_ID,
            type: "fill-extrusion",
            source: BIN_EXTRUSION_SOURCE_ID,
            layout: { visibility: viewMode === "3d" ? "visible" : "none" },
            paint: binExtrusionLayerPaint(colorSteps),
          },
          BIN_LAYER_ID,
        );
      }
    }

    upsertSource(BIN_HIGHLIGHT_SOURCE_ID, highlightGeoJson);
    if (!map.getLayer(BIN_HIGHLIGHT_LAYER_ID) && map.getSource(BIN_HIGHLIGHT_SOURCE_ID)) {
      map.addLayer({
        id: BIN_HIGHLIGHT_LAYER_ID,
        type: "line",
        source: BIN_HIGHLIGHT_SOURCE_ID,
        paint: binHighlightLayerPaint(),
      });
    }

    applyViewModeSettings(map, viewMode, colorSteps);
    map.resize();
  }, [bins, colorSteps, extrusionBins, mapReady, viewMode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const baseOpacity = viewMode === "3d" ? 0.35 : 0.92;
    if (map.getLayer(BIN_LAYER_ID)) {
      const paint = binLayerPaint(colorSteps, baseOpacity);
      map.setPaintProperty(BIN_LAYER_ID, "line-color", paint["line-color"]);
      map.setPaintProperty(BIN_LAYER_ID, "line-width", paint["line-width"]);
      map.setPaintProperty(BIN_LAYER_ID, "line-opacity", paint["line-opacity"]);
    }
    if (map.getLayer(BIN_EXTRUSION_LAYER_ID)) {
      map.setPaintProperty(
        BIN_EXTRUSION_LAYER_ID,
        "fill-extrusion-color",
        binExtrusionColorPaint(colorSteps),
      );
      map.setPaintProperty(
        BIN_EXTRUSION_LAYER_ID,
        "fill-extrusion-height",
        binExtrusionLayerPaint(colorSteps)["fill-extrusion-height"],
      );
    }
  }, [colorSteps, mapReady, viewMode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !bins) return;

    const selectedIds = new Set(selectionBinIds(bins, selection));
    for (const feature of bins.features) {
      const id = feature.properties.bin_id;
      map.removeFeatureState({ source: BIN_SOURCE_ID, id });
    }

    if (selectedIds.size > 0) {
      for (const feature of bins.features) {
        const id = feature.properties.bin_id;
        const isSelected = selectedIds.has(id);
        const state = isSelected ? { selected: true } : { dimmed: true };
        map.setFeatureState({ source: BIN_SOURCE_ID, id }, state);
      }
    }

    const src = map.getSource(BIN_HIGHLIGHT_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    src?.setData(highlightGeoJson);

    if (selection) {
      const bounds = boundsFromFeatures(highlightGeoJson.features);
      if (bounds) {
        map.fitBounds(bounds, { padding: 120, duration: 900, maxZoom: 11 });
      }
    }
  }, [bins, selection, highlightGeoJson, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !bbox || hasFittedBboxRef.current) return;
    map.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: 60, duration: 800 },
    );
    hasFittedBboxRef.current = true;
  }, [bbox, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const layers = interactiveLayerIds(viewMode).filter((id) => Boolean(map.getLayer(id)));

    const onMove = (e: maplibregl.MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point, { layers });
      const popup = popupRef.current;
      if (!features.length || !popup) {
        popup?.remove();
        map.getCanvas().style.cursor = "";
        return;
      }
      map.getCanvas().style.cursor = "pointer";
      const p = features[0].properties as Record<string, string | number>;
      popup
        .setLngLat(e.lngLat)
        .setHTML(
          `<strong>${p.road_number}</strong> · km ${(Number(p.bin_start_m) / 1000).toFixed(1)}–${(Number(p.bin_end_m) / 1000).toFixed(1)}<br/>
           Ongevallen: <strong>${p.accident_count}</strong> · ${formatDensityPerKmYear(p)}<br/>
           <em>${p.geometry_quality}</em>`,
        )
        .addTo(map);
    };

    const onClick = (e: maplibregl.MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point, { layers });
      if (!features.length) {
        onSelect(null);
        return;
      }
      const p = features[0].properties as unknown as SelectedBin;
      const nextSelection: MapSelection =
        selection?.type === "bin" && selection.binId === p.bin_id
          ? null
          : { type: "bin", binId: p.bin_id };
      onSelect(nextSelection);
    };

    map.on("mousemove", onMove);
    map.on("click", onClick);
    return () => {
      map.off("mousemove", onMove);
      map.off("click", onClick);
    };
  }, [mapReady, onSelect, selection, viewMode]);

  return (
    <div className="map-wrap">
      {loading && <div className="map-loading">Kaart laden…</div>}
      {!loading && bins && bins.features.length === 0 && (
        <div className="map-empty">Geen bins gevonden voor deze filters.</div>
      )}
      {viewMode === "3d" && (
        <div className="map-nav-hint">
          Sleep om te draaien · middenklik of Alt+sleep om te verschuiven · hoogte ={" "}
          {EXTRUSION_METERS_PER_DENSITY} m per ongeval/km/jaar
        </div>
      )}
      <div ref={containerRef} className="map-container" />
    </div>
  );
});
