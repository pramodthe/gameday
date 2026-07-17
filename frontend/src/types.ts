export type Status = "IDLE" | "CONNECTING" | "LIVE" | "LISTENING" | "SAVING" | "COMPLETE";
export type MetricStatus = "ok" | "caution" | "risk" | "idle";

export interface Question {
  type: "question";
  index: number;
  total: number;
  field: string;
  text: string;
}

export interface Result {
  type: "result";
  readiness: number;
  band: string;
  recommendation: "PUSH" | "MAINTAIN" | "RECOVER";
  acwr: number | null;
  acwr_provisional?: boolean;
  flags: string[];
  components?: Record<string, number>;
  coaching_text: string;
  streak: number;
}

export interface LogEntry {
  who: "nova" | "you";
  text: string;
}

export interface CheckinState {
  status: Status;
  connected: boolean;
  question: Question | null;
  metrics: Record<string, unknown>;
  statuses: Record<string, MetricStatus>;
  log: LogEntry[];
  result: Result | null;
  error: string | null;
}

export interface BoardRow {
  athlete_id: string;
  name: string;
  sport: string;
  checked_in_today: boolean;
  readiness: number | null;
  band: string | null;
  recommendation: string | null;
  flags: string[];
  acwr: number | null;
}
