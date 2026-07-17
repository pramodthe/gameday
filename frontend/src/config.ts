export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8091";
export const WS_BASE = (import.meta.env.VITE_WS_BASE ?? API_BASE).replace(/^http/, "ws");
export const DEFAULT_ATHLETE = "a-alex";
export const DEFAULT_COACH = "coach-1";
