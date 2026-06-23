import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRoads } from "../api";

interface RoadSearchProps {
  value: string;
  onChange: (road: string) => void;
}

export function RoadSearch({ value, onChange }: RoadSearchProps) {
  const [query, setQuery] = useState(value);
  const { data: roads } = useQuery({
    queryKey: ["roads", query],
    queryFn: () => fetchRoads(query || undefined),
  });

  return (
    <div className="road-search">
      <label className="field">
        <span>Weg</span>
        <input
          type="text"
          value={query}
          placeholder="A2"
          onChange={(e) => {
            setQuery(e.target.value.toUpperCase());
            if (e.target.value.toUpperCase() === "A2") onChange("A2");
          }}
          onBlur={() => {
            if (query !== "A2") setQuery("A2");
            onChange("A2");
          }}
        />
      </label>
      {roads && roads.length > 1 && (
        <ul className="road-list">
          {roads.map((r) => (
            <li key={r.road_number} className={r.status === "implemented" ? "ok" : "disabled"}>
              <strong>{r.road_number}</strong>
              {r.status === "implemented" ? (
                <span> — {r.accident_count.toLocaleString("nl-NL")} ongevallen</span>
              ) : (
                <span className="badge">Nog niet geïmplementeerd</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
