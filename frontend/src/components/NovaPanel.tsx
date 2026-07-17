import { useEffect, useRef } from "react";
import type { LogEntry, Question } from "../types";

export function NovaPanel({ log, question }: { log: LogEntry[]; question: Question | null }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [log]);

  return (
    <div className="panel nova">
      <div className="panel__title">
        <span className="nova__mic" /> Nova Check-in
        {question ? <span className="nova__count">{question.index}/{question.total}</span> : null}
      </div>
      <div className="nova__log" ref={scrollRef}>
        {log.length === 0 && <div className="nova__empty">Nova is ready when you are.</div>}
        {log.map((entry, i) => (
          <div key={i} className={`bubble ${entry.who}`}>
            {entry.who === "nova" && <span className="bubble__who">Nova</span>}
            {entry.text}
          </div>
        ))}
      </div>
    </div>
  );
}
