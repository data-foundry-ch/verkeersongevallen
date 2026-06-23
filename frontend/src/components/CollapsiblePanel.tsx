import { useState, type ReactNode } from "react";

interface CollapsiblePanelProps {
  title: string;
  side: "left" | "right";
  children: ReactNode;
  defaultOpen?: boolean;
}

export function CollapsiblePanel({
  title,
  side,
  children,
  defaultOpen = true,
}: CollapsiblePanelProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <aside
      className={`float-panel float-panel-${side} glass-panel ${open ? "" : "collapsed"}`}
    >
      <button
        type="button"
        className="panel-header"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <h2 className="panel-heading">{title}</h2>
        <span className="panel-chevron" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && <div className="panel-body">{children}</div>}
    </aside>
  );
}
