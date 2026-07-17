import type { CheckinState } from "./types";

export const initialState: CheckinState = {
  status: "IDLE",
  connected: false,
  question: null,
  metrics: {},
  statuses: {},
  log: [],
  result: null,
  error: null,
};

// Reduces both server events (by `type`) and a few internal actions (prefixed `__`).
export function reduce(s: CheckinState, ev: any): CheckinState {
  switch (ev.type) {
    case "__reset":
      return { ...initialState, status: "CONNECTING" };
    case "__open":
      return { ...s, connected: true, status: "LIVE" };
    case "__closed":
      return { ...s, connected: false };
    case "state": {
      // READY_TO_COMPLETE is internal; don't surface it as a status.
      const status = ev.value === "READY_TO_COMPLETE" ? s.status : ev.value;
      return { ...s, status };
    }
    case "question":
      return {
        ...s,
        question: ev,
        status: "LISTENING",
        log: [...s.log, { who: "nova", text: ev.text }],
      };
    case "transcript":
      return { ...s, log: [...s.log, { who: "you", text: ev.text }] };
    case "metric.update":
      return {
        ...s,
        metrics: { ...s.metrics, [ev.field]: ev.value },
        statuses: { ...s.statuses, [ev.field]: ev.status },
      };
    case "coach.log":
      return { ...s, log: [...s.log, { who: "nova", text: ev.text }] };
    case "result":
      return { ...s, result: ev, status: "COMPLETE" };
    case "error":
      return { ...s, error: ev.code };
    default:
      return s;
  }
}
