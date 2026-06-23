export type MapViewMode = "2d" | "3d";

interface MapViewControlsProps {
  viewMode: MapViewMode;
  onViewModeChange: (mode: MapViewMode) => void;
  onRotateLeft?: () => void;
  onRotateRight?: () => void;
}

export function MapViewControls({
  viewMode,
  onViewModeChange,
  onRotateLeft,
  onRotateRight,
}: MapViewControlsProps) {
  return (
    <div className="map-view-controls map-view-controls--centered glass-panel">
      <button
        type="button"
        className={viewMode === "2d" ? "active" : ""}
        onClick={() => onViewModeChange("2d")}
      >
        2D
      </button>
      <button
        type="button"
        className={viewMode === "3d" ? "active" : ""}
        onClick={() => onViewModeChange("3d")}
      >
        3D
      </button>
      {viewMode === "3d" && (
        <>
          <button
            type="button"
            title="Draai links"
            onClick={onRotateLeft}
            aria-label="Draai links"
          >
            ↺
          </button>
          <button
            type="button"
            title="Draai rechts"
            onClick={onRotateRight}
            aria-label="Draai rechts"
          >
            ↻
          </button>
        </>
      )}
    </div>
  );
}
