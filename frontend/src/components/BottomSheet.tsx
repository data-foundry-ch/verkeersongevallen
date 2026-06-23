import { useEffect, type ReactNode } from "react";

interface BottomSheetProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function BottomSheet({ open, title, onClose, children }: BottomSheetProps) {
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="bottom-sheet-root" role="presentation">
      <button type="button" className="bottom-sheet-backdrop" aria-label="Sluit paneel" onClick={onClose} />
      <div className="bottom-sheet glass-panel" role="dialog" aria-modal="true" aria-label={title}>
        <div className="bottom-sheet-handle" aria-hidden />
        <div className="bottom-sheet-header">
          <h2 className="panel-heading">{title}</h2>
          <button type="button" className="bottom-sheet-close" onClick={onClose} aria-label="Sluiten">
            ✕
          </button>
        </div>
        <div className="bottom-sheet-body">{children}</div>
      </div>
    </div>
  );
}
