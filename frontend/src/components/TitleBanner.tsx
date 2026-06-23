import { MapViewControls, type MapViewMode } from "./MapViewControls";
import { APP_TITLE } from "../constants";

interface TitleBarProps {
  road: string;
  viewMode: MapViewMode;
  onViewModeChange: (mode: MapViewMode) => void;
  onRotateLeft?: () => void;
  onRotateRight?: () => void;
  compact?: boolean;
  showViewControls?: boolean;
}

export function TitleBar({
  road,
  viewMode,
  onViewModeChange,
  onRotateLeft,
  onRotateRight,
  compact = false,
  showViewControls = true,
}: TitleBarProps) {
  return (
    <div className={`title-bar ${compact ? "title-bar--compact" : ""}`}>
      <div className="float-title glass-panel">
        <h1>{APP_TITLE} {road}</h1>
        {!compact && <p className="float-title-sub">NWB hectometer-km · hoofdrijbaan</p>}
      </div>
      {showViewControls && (
        <MapViewControls
          viewMode={viewMode}
          onViewModeChange={onViewModeChange}
          onRotateLeft={onRotateLeft}
          onRotateRight={onRotateRight}
        />
      )}
    </div>
  );
}

/** @deprecated use TitleBar */
export { TitleBar as TitleBanner };
