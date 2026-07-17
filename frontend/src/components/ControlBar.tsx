import { useState } from "react";
import type { Status } from "../types";
import { AudioVisualizer } from "./AudioVisualizer";

const STATUS_LABEL: Record<Status, string> = {
  IDLE: "Idle",
  CONNECTING: "Connecting…",
  LIVE: "Live",
  LISTENING: "Listening…",
  SAVING: "Saving…",
  COMPLETE: "Done",
};

export function ControlBar({
  status,
  active,
  canVoice,
  recording,
  onRecStart,
  onRecStop,
  onText,
}: {
  status: Status;
  active: boolean;
  canVoice: boolean;
  recording: boolean;
  onRecStart: () => void;
  onRecStop: () => void;
  onText: (t: string) => void;
}) {
  const [text, setText] = useState("");

  return (
    <div className="controlbar">
      <div className={`pill pill--${status.toLowerCase()}`}>
        <span className="pill__dot" />
        {STATUS_LABEL[status]}
      </div>

      <AudioVisualizer active={active} />

      {canVoice && (
        <button
          className={`micbtn ${recording ? "micbtn--rec" : ""}`}
          onMouseDown={onRecStart}
          onMouseUp={onRecStop}
          onMouseLeave={() => recording && onRecStop()}
          title="Hold to talk"
        >
          🎙
        </button>
      )}

      <form
        className="answerbar"
        onSubmit={(e) => {
          e.preventDefault();
          const t = text.trim();
          if (t) {
            onText(t);
            setText("");
          }
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type your answer…"
          disabled={status === "COMPLETE"}
        />
        <button type="submit" disabled={status === "COMPLETE"}>
          Send
        </button>
      </form>
    </div>
  );
}
