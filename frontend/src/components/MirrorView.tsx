import { useEffect, useRef, useState } from "react";
import { getStreak } from "../api";
import { DEFAULT_ATHLETE } from "../config";
import { useCheckinSocket } from "../hooks/useCheckinSocket";
import { ControlBar } from "./ControlBar";
import { NovaPanel } from "./NovaPanel";
import { ReadinessRing } from "./ReadinessRing";
import { ResultCard } from "./ResultCard";
import { TodayPanel } from "./TodayPanel";

export function MirrorView() {
  const { state, start, sendText, sendAudio } = useCheckinSocket();
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const [camOk, setCamOk] = useState(false);
  const [micOk, setMicOk] = useState(false);
  const [recording, setRecording] = useState(false);
  const [streak, setStreak] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    navigator.mediaDevices
      ?.getUserMedia({ video: true, audio: true })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        setMicOk(stream.getAudioTracks().length > 0);
        if (videoRef.current && stream.getVideoTracks().length > 0) {
          videoRef.current.srcObject = stream;
          setCamOk(true);
        }
      })
      .catch(() => setCamOk(false));
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  useEffect(() => {
    getStreak(DEFAULT_ATHLETE)
      .then((s) => setStreak(s.current))
      .catch(() => {});
  }, []);

  const startRec = () => {
    const stream = streamRef.current;
    if (!stream) return;
    try {
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
      const chunks: BlobPart[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = async () => {
        const buf = await new Blob(chunks, { type: "audio/webm" }).arrayBuffer();
        sendAudio(buf);
      };
      rec.start();
      recRef.current = rec;
      setRecording(true);
    } catch {
      /* recording unsupported */
    }
  };

  const stopRec = () => {
    recRef.current?.stop();
    setRecording(false);
  };

  const active = recording || state.status === "LISTENING" || state.status === "SAVING";
  const displayStreak = state.result?.streak ?? streak;

  return (
    <div className="mirror">
      <video ref={videoRef} autoPlay muted playsInline className={`mirror__video ${camOk ? "" : "hidden"}`} />
      {!camOk && <div className="mirror__fallback" />}
      <div className="mirror__scrim" />

      <div className="mirror__brand">
        <span className="mirror__brand-badge" />
        <div>
          Wellness Mirror
          <em>Powered by Nova · ReadyRoom</em>
        </div>
      </div>

      <div className="mirror__left">
        <TodayPanel metrics={state.metrics} statuses={state.statuses} />
        <ReadinessRing score={state.result?.readiness ?? null} band={state.result?.band ?? null} />
        {displayStreak != null && <div className="streak">🔥 {displayStreak}-day streak</div>}
      </div>

      <div className="mirror__right">
        <NovaPanel log={state.log} question={state.question} />
      </div>

      {state.status === "IDLE" ? (
        <div className="mirror__start">
          <h1>Good morning.</h1>
          <p>60-second readiness check-in with Nova.</p>
          <div className="mirror__start-actions">
            <button className="btn btn--primary" onClick={() => start(DEFAULT_ATHLETE, false)}>
              Start check-in
            </button>
            <button className="btn btn--demo" onClick={() => start(DEFAULT_ATHLETE, true)}>
              ▶ Demo Mode
            </button>
          </div>
        </div>
      ) : (
        <ControlBar
          status={state.status}
          active={active}
          canVoice={micOk}
          recording={recording}
          onRecStart={startRec}
          onRecStop={stopRec}
          onText={sendText}
        />
      )}

      {state.result && <ResultCard result={state.result} onRestart={() => start(DEFAULT_ATHLETE, false)} />}
    </div>
  );
}
