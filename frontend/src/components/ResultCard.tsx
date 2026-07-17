import type { Result } from "../types";

const REC_STYLE: Record<string, { label: string; cls: string }> = {
  PUSH: { label: "PUSH", cls: "rec--push" },
  MAINTAIN: { label: "MAINTAIN", cls: "rec--maintain" },
  RECOVER: { label: "RECOVER", cls: "rec--recover" },
};

export function ResultCard({ result, onRestart }: { result: Result; onRestart: () => void }) {
  const rec = REC_STYLE[result.recommendation] ?? REC_STYLE.MAINTAIN;
  return (
    <div className="result">
      <div className="result__card">
        <div className="result__top">
          <div className="result__score-wrap">
            <div className="result__score">{result.readiness}</div>
            <div className="result__band">{result.band} READINESS</div>
          </div>
          <div className={`rec ${rec.cls}`}>{rec.label}</div>
        </div>

        <p className="result__coach">{result.coaching_text}</p>

        <div className="result__chips">
          {result.acwr != null && (
            <span className={`chip ${result.flags.includes("HIGH_INJURY_RISK") ? "chip--risk" : ""}`}>
              ACWR {result.acwr}
              {result.acwr_provisional ? " (prov.)" : ""}
            </span>
          )}
          {result.flags.map((f) => (
            <span key={f} className="chip chip--risk">
              {f.replace(/_/g, " ")}
            </span>
          ))}
          <span className="chip chip--streak">🔥 {result.streak}-day streak</span>
        </div>

        <button className="btn btn--ghost" onClick={onRestart}>
          New check-in
        </button>
      </div>
    </div>
  );
}
