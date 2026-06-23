import type { Map } from "maplibre-gl";

const BEARING_PER_PIXEL = 0.8;
const PITCH_PER_PIXEL = -0.5;
const MAX_PITCH = 85;

export interface OrbitControlOptions {
  /** Pitch (degrees) above which left-drag orbits instead of panning. */
  pitchThreshold?: number;
  /** When false, standard flat-map panning only. */
  is3d?: () => boolean;
}

/**
 * Desktop-friendly 3D navigation:
 * - pitched view: left-drag orbits (bearing + pitch)
 * - any pitch: Shift+left-drag orbits
 * - flat view: left-drag pans (MapLibre default)
 * Right-drag and Ctrl+left-drag still use MapLibre's built-in handlers.
 */
export function installOrbitControls(
  map: Map,
  { pitchThreshold = 25, is3d = () => false }: OrbitControlOptions = {},
): () => void {
  const canvas = map.getCanvas();

  const preventContextMenu = (e: Event) => e.preventDefault();
  canvas.addEventListener("contextmenu", preventContextMenu);

  let orbiting = false;
  let panning = false;
  let lastX = 0;
  let lastY = 0;

  const syncPanMode = () => {
    if (orbiting || panning) return;
    if (!is3d()) {
      map.dragPan.enable();
      return;
    }
    if (map.getPitch() >= pitchThreshold) map.dragPan.disable();
    else map.dragPan.enable();
  };

  const shouldOrbit = (e: MouseEvent) =>
    is3d() &&
    e.button === 0 &&
    !e.altKey &&
    (e.shiftKey || map.getPitch() >= pitchThreshold);

  const shouldPan = (e: MouseEvent) =>
    is3d() &&
    (e.button === 1 || (e.button === 0 && e.altKey)) &&
    map.getPitch() >= pitchThreshold;

  const onMouseDown = (e: MouseEvent) => {
    if (shouldPan(e)) {
      panning = true;
      lastX = e.clientX;
      lastY = e.clientY;
      map.dragPan.disable();
      canvas.style.cursor = "move";
      e.preventDefault();
      return;
    }
    if (!shouldOrbit(e)) return;
    orbiting = true;
    lastX = e.clientX;
    lastY = e.clientY;
    map.dragPan.disable();
    canvas.style.cursor = "grab";
    e.preventDefault();
  };

  const onMouseMove = (e: MouseEvent) => {
    if (panning) {
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      map.panBy([-dx, -dy], { animate: false });
      lastX = e.clientX;
      lastY = e.clientY;
      e.preventDefault();
      return;
    }
    if (!orbiting) return;
    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    if (dx !== 0) map.setBearing(map.getBearing() + dx * BEARING_PER_PIXEL);
    if (dy !== 0) {
      map.setPitch(
        Math.max(0, Math.min(MAX_PITCH, map.getPitch() + dy * PITCH_PER_PIXEL)),
      );
    }
    lastX = e.clientX;
    lastY = e.clientY;
    e.preventDefault();
  };

  const endOrbit = () => {
    if (!orbiting && !panning) return;
    orbiting = false;
    panning = false;
    canvas.style.cursor = "";
    syncPanMode();
  };

  map.on("pitch", syncPanMode);
  syncPanMode();

  canvas.addEventListener("mousedown", onMouseDown);
  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mouseup", endOrbit);
  window.addEventListener("blur", endOrbit);

  return () => {
    canvas.removeEventListener("contextmenu", preventContextMenu);
    map.off("pitch", syncPanMode);
    canvas.removeEventListener("mousedown", onMouseDown);
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", endOrbit);
    window.removeEventListener("blur", endOrbit);
    endOrbit();
    map.dragPan.enable();
  };
}

export function rotateBearing(map: Map, deltaDegrees: number) {
  map.easeTo({ bearing: map.getBearing() + deltaDegrees, duration: 300 });
}
