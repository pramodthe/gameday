const BAND_COLOR: Record<string, string> = {
  HIGH: "#34d399",
  MODERATE: "#fbbf24",
  LOW: "#f87171",
};

export function ReadinessRing({ score, band }: { score: number | null; band: string | null }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const pct = score ?? 0;
  const offset = score == null ? c : c * (1 - pct / 100);
  const color = (band && BAND_COLOR[band]) || "#64748b";

  return (
    <div className="ring">
      <svg viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={r} className="ring__track" />
        <circle
          cx="60"
          cy="60"
          r={r}
          className="ring__val"
          style={{ stroke: color, strokeDasharray: c, strokeDashoffset: offset }}
        />
      </svg>
      <div className="ring__label">
        <div className="ring__score" style={{ color }}>
          {score ?? "—"}
        </div>
        <div className="ring__cap">READINESS</div>
      </div>
    </div>
  );
}
