export type AgentStage =
  | 'idle'
  | 'connecting'
  | 'speaking'
  | 'listening'
  | 'thinking'
  | 'complete';

export type MetricTone = 'neutral' | 'good' | 'attention' | 'risk';

export type MetricKey =
  | 'sleep'
  | 'recovery'
  | 'training'
  | 'fuel'
  | 'mindset'
  | 'spending';

export interface MirrorMetric {
  key: MetricKey;
  label: string;
  value: string;
  detail: string;
  tone: MetricTone;
}

export interface TranscriptMessage {
  id: string;
  speaker: 'agent' | 'athlete';
  text: string;
}

export interface PlanAction {
  id: string;
  eyebrow: string;
  title: string;
  detail: string;
}

export interface DemoQuestion {
  id: MetricKey;
  prompt: string;
  demoAnswer: string;
  acknowledgement: string;
  updates: Partial<Record<MetricKey, Omit<MirrorMetric, 'key' | 'label'>>>;
}

export interface LiveMirrorConfig {
  configured: boolean;
  serverUrl?: string;
  token?: string;
  roomName?: string;
  sessionId?: string;
  sponsors?: Record<string, boolean>;
  memory?: Record<string, unknown> | null;
}

export interface LiveMirrorEvent {
  type:
    | 'agent_state_changed'
    | 'transcript_finalized'
    | 'metric_updated'
    | 'checkin_progressed'
    | 'memory_used'
    | 'plan_ready'
    | 'checkin_completed'
    | 'recoverable_error';
  session_id?: string;
  event_id?: string;
  timestamp?: string;
  state?: AgentStage;
  speaker?: TranscriptMessage['speaker'];
  text?: string;
  message?: string;
  metric_key?: MetricKey;
  display_value?: string;
  detail?: string;
  status?: MetricTone;
  confidence?: number;
  completed_step?: number;
  total_steps?: number;
  actions?: PlanAction[];
  safety_status?: string;
  plan_source?: string;
  streak?: number;
}
