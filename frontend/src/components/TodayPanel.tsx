import type { MetricStatus } from "../types";

type Row = { key: string; label: string; fmt: (v: any) => string };

const ROWS: Row[] = [
  { key: "sleep_hours", label: "Sleep", fmt: (v) => (v != null ? `${v} hrs` : "—") },
  {
    key: "training",
    label: "Load",
    fmt: (v) => (v ? `${v.minutes ?? "—"} min · RPE ${v.rpe ?? "—"}` : "—"),
  },
  {
    key: "soreness",
    label: "Soreness",
    fmt: (v) => (Array.isArray(v) ? (v.length ? v.join(", ") : "None") : "—"),
  },
  { key: "nutrition", label: "Fuel", fmt: (v) => (v === true ? "Fueled" : v === false ? "Skipped" : "—") },
  { key: "mood", label: "Mood", fmt: (v) => (v != null ? `${v} / 5` : "—") },
];

export function TodayPanel({
  metrics,
  statuses,
}: {
  metrics: Record<string, unknown>;
  statuses: Record<string, MetricStatus>;
}) {
  return (
    <div className="panel today">
      <div className="panel__title">
        <span className="panel__dot" /> TODAY
      </div>
      {ROWS.map((row) => {
        const status = statuses[row.key] ?? "idle";
        return (
          <div className="metric" key={row.key}>
            <span className="metric__label">{row.label}</span>
            <span className={`metric__val ${status}`}>{row.fmt(metrics[row.key])}</span>
          </div>
        );
      })}
    </div>
  );
}
