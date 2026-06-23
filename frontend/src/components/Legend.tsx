import type { ColorStep } from "../map/colorScale";

interface LegendProps {
  steps: ColorStep[];
}

export function Legend({ steps }: LegendProps) {
  return (
    <div className="legend">
      <h3>Ongevallen per km per jaar</h3>
      <ul>
        {steps.map((step) => (
          <li key={step.label}>
            <span className="swatch" style={{ background: step.color }} />
            {step.label} /km/jaar
          </li>
        ))}
      </ul>
    </div>
  );
}
