import { MapViewControls, type MapViewMode } from "./MapViewControls";
import { APP_TITLE } from "../constants";

const MARKETING_URL = import.meta.env.VITE_MARKETING_URL as string | undefined;

interface TitleBarProps {
  road: string;
  viewMode: MapViewMode;
  onViewModeChange: (mode: MapViewMode) => void;
  onRotateLeft?: () => void;
  onRotateRight?: () => void;
}

export function TitleBar({
  road,
  viewMode,
  onViewModeChange,
  onRotateLeft,
  onRotateRight,
}: TitleBarProps) {
  return (
    <div className="title-bar">
      <div className="float-title glass-panel">
        {MARKETING_URL ? (
          <a className="showcase-home-link" href={MARKETING_URL}>
            ← DataFoundry
          </a>
        ) : null}
        <h1>{APP_TITLE} {road}</h1>
        <p className="float-title-sub">NWB hectometer-km · hoofdrijbaan</p>
      </div>
      <MapViewControls
        viewMode={viewMode}
        onViewModeChange={onViewModeChange}
        onRotateLeft={onRotateLeft}
        onRotateRight={onRotateRight}
      />
    </div>
  );
}

/** @deprecated use TitleBar */
export { TitleBar as TitleBanner };
