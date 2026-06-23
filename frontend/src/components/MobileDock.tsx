export type MobileSheet = "analyse" | "filters" | null;

interface MobileDockProps {
  active: MobileSheet;
  onAnalyse: () => void;
  onFilters: () => void;
}

export function MobileDock({ active, onAnalyse, onFilters }: MobileDockProps) {
  return (
    <nav className="mobile-dock glass-panel" aria-label="Paneelnavigatie">
      <button
        type="button"
        className={`mobile-dock-btn ${active === "analyse" ? "active" : ""}`}
        onClick={onAnalyse}
        aria-pressed={active === "analyse"}
      >
        Analyse
      </button>
      <button
        type="button"
        className={`mobile-dock-btn ${active === "filters" ? "active" : ""}`}
        onClick={onFilters}
        aria-pressed={active === "filters"}
      >
        Filters
      </button>
    </nav>
  );
}
