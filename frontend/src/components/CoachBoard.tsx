import { useEffect, useState } from "react";
import { getBoard } from "../api";
import { DEFAULT_COACH } from "../config";
import type { BoardRow } from "../types";

const BAND_CLASS: Record<string, string> = { HIGH: "hi", MODERATE: "mid", LOW: "lo" };

export function CoachBoard() {
  const [rows, setRows] = useState<BoardRow[]>([]);
  const [date, setDate] = useState("");

  useEffect(() => {
    const load = () =>
      getBoard(DEFAULT_COACH)
        .then((b) => {
          setRows(b.athletes);
          setDate(b.date);
        })
        .catch(() => {});
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, []);

  const flaggedCount = rows.filter(
    (r) => r.recommendation === "RECOVER" || r.flags.includes("HIGH_INJURY_RISK"),
  ).length;

  return (
    <div className="board">
      <div className="board__head">
        <div>
          <h2>Coach Board</h2>
          <span className="board__sub">{date} · {rows.length} athletes</span>
        </div>
        <div className="board__alert">{flaggedCount} flagged today</div>
      </div>

      <div className="board__grid">
        {rows.map((r) => {
          const flagged = r.recommendation === "RECOVER" || r.flags.includes("HIGH_INJURY_RISK");
          return (
            <div className={`athlete ${flagged ? "athlete--flag" : ""}`} key={r.athlete_id}>
              <div className="athlete__top">
                <div>
                  <div className="athlete__name">{r.name}</div>
                  <div className="athlete__sport">{r.sport}</div>
                </div>
                <div className={`score score--${r.band ? BAND_CLASS[r.band] : "none"}`}>
                  {r.readiness ?? "—"}
                </div>
              </div>
              <div className="athlete__bottom">
                {r.recommendation ? (
                  <span className={`tag tag--${r.recommendation.toLowerCase()}`}>{r.recommendation}</span>
                ) : (
                  <span className="tag tag--none">No check-in</span>
                )}
                {r.flags.includes("HIGH_INJURY_RISK") && <span className="tag tag--risk">⚠ Injury risk</span>}
                {r.acwr != null && <span className="athlete__acwr">ACWR {r.acwr}</span>}
                {!r.checked_in_today && r.recommendation && <span className="athlete__stale">· stale</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
