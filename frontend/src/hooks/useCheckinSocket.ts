import { useCallback, useReducer, useRef } from "react";
import { createSession } from "../api";
import { WS_BASE } from "../config";
import { initialState, reduce } from "../checkinReducer";

function playB64(b64: string, mime = "audio/mpeg") {
  try {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
    const audio = new Audio(url);
    audio.play().catch(() => {});
    audio.onended = () => URL.revokeObjectURL(url);
  } catch {
    /* ignore playback errors */
  }
}

export function useCheckinSocket() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const wsRef = useRef<WebSocket | null>(null);

  const start = useCallback(async (athleteId: string, demo = false) => {
    wsRef.current?.close();
    dispatch({ type: "__reset" });
    const { session_id } = await createSession(athleteId, demo);
    const ws = new WebSocket(`${WS_BASE}/ws/checkin/${session_id}`);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => {
      dispatch({ type: "__open" });
      if (demo) ws.send(JSON.stringify({ type: "demo_run" }));
    };
    ws.onmessage = (e) => {
      if (typeof e.data !== "string") return;
      const ev = JSON.parse(e.data);
      dispatch(ev);
      if (ev.audio_b64) playB64(ev.audio_b64, ev.audio_mime);
    };
    ws.onclose = () => dispatch({ type: "__closed" });
    wsRef.current = ws;
  }, []);

  const sendText = useCallback((text: string) => {
    wsRef.current?.send(JSON.stringify({ type: "text_answer", text }));
  }, []);

  const sendAudio = useCallback((buf: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(buf);
  }, []);

  const complete = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "complete" }));
  }, []);

  return { state, start, sendText, sendAudio, complete };
}
