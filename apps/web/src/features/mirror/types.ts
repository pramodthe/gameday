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

/** The exercises the camera coach can track live (the Core-5 library). */
export type TrackedMovement = 'squat' | 'pushup' | 'lunge' | 'plank' | 'glute_bridge';

export interface ExercisePoseMetrics {
  reps: number;
  primary_angle: number;
  min_primary_angle: number;
  max_primary_angle: number;
  symmetry_gap: number;
  alignment_deviation: number;
  visibility: number;
  hold_seconds?: number;
}

export interface ExerciseAnalysis {
  score: number;
  headline: string;
  summary: string;
  cues: string[];
  confidence: number;
  source: string;
}

export type ExerciseMotionPattern =
  | 'squat'
  | 'lunge'
  | 'hinge'
  | 'push'
  | 'pull'
  | 'plank'
  | 'rotation'
  | 'jump'
  | 'stretch'
  | 'generic';

export interface ExerciseLessonStep {
  title: string;
  instruction: string;
  phase: 'setup' | 'move' | 'finish';
}

export interface ExerciseLesson {
  exercise_name: string;
  category: 'strength' | 'mobility' | 'cardio' | 'balance' | 'recovery';
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  summary: string;
  equipment: string[];
  primary_muscles: string[];
  steps: ExerciseLessonStep[];
  form_cues: string[];
  avoid: string[];
  prescription: string;
  tempo: string;
  safety_note: string;
  motion_pattern: ExerciseMotionPattern;
  camera_support: TrackedMovement | 'none';
  source: string;
}

export interface WorkoutExercise {
  name: string;
  motion_pattern: TrackedMovement;
  sets: number;
  reps: number;
  hold_seconds: number;
  rest_seconds: number;
  coaching_cue: string;
}

export interface WorkoutSession {
  title: string;
  focus: string;
  intensity: 'recovery' | 'moderate' | 'hard';
  estimated_minutes: number;
  summary: string;
  exercises: WorkoutExercise[];
  source?: string;
  decision_trace?: string[];
  orchestration?: LyzrOrchestration;
}

export interface LyzrOrchestration {
  provider: string;
  role: string;
  status: string;
  session_id: string;
  memory_used: boolean;
  specialist_agent_id?: string;
  specialist_session_id?: string;
  manager?: {
    agent_id: string;
    status: string;
    route: string;
    session_id?: string;
  };
}

export interface ExerciseAdaptation {
  action: 'continue' | 'reduce_reps' | 'increase_rest' | 'replace_exercise' | 'finish';
  message: string;
  reason: string;
  next_reps?: number | null;
  next_hold_seconds?: number | null;
  next_rest_seconds?: number | null;
  replacement_movement?: TrackedMovement | null;
  source: string;
  decision_trace?: string[];
  orchestration?: LyzrOrchestration;
}

export type ExerciseSharedMode = 'idle' | 'lesson' | 'camera';
export type ExerciseSharedStatus =
  | 'idle'
  | 'requested'
  | 'loading'
  | 'waiting'
  | 'ready'
  | 'active'
  | 'completed'
  | 'failed'
  | 'closed';

export interface ExerciseSharedState {
  mode: ExerciseSharedMode;
  status: ExerciseSharedStatus;
  requestId: string | null;
  name: string | null;
  targetReps: number | null;
  reps: number;
  bodyVisible: boolean | null;
  cue: string | null;
  lesson: ExerciseLesson | null;
  analysis: ExerciseAnalysis | null;
  adaptation: ExerciseAdaptation | null;
  error: string | null;
}

export interface MirrorSharedState {
  version: 1;
  revision: number;
  sessionId: string;
  exercise: ExerciseSharedState;
}

export interface AgUiStateSnapshotEvent {
  type: 'STATE_SNAPSHOT';
  timestamp?: number;
  snapshot: MirrorSharedState;
}

export interface AgUiToolCallEvent {
  type: 'TOOL_CALL_START' | 'TOOL_CALL_ARGS' | 'TOOL_CALL_END' | 'TOOL_CALL_RESULT';
  timestamp?: number;
  toolCallId: string;
  toolCallName?: string;
  delta?: string;
  messageId?: string;
  content?: string;
  role?: 'tool';
}

export interface AgUiCustomEvent {
  type: 'CUSTOM';
  timestamp?: number;
  name: 'gameday.exercise.telemetry' | 'gameday.state.request';
  value: unknown;
}

export interface ExerciseLessonTelemetryEvent {
  type:
    | 'exercise_lesson_loading'
    | 'exercise_lesson_ready'
    | 'exercise_lesson_failed'
    | 'exercise_lesson_closed';
  exercise_name: string;
  timestamp: string;
  request_id?: string;
  summary?: string;
  form_cues?: string[];
  source?: string;
  message?: string;
  lesson?: ExerciseLesson;
}

export interface ExerciseTelemetryEvent {
  type:
    | 'exercise_opened'
    | 'exercise_waiting'
    | 'exercise_ready'
    | 'exercise_started'
    | 'exercise_progress'
    | 'exercise_reset'
    | 'exercise_completed'
    | 'exercise_closed';
  exercise: TrackedMovement;
  target_reps: number;
  timestamp: string;
  request_id?: string;
  trigger?: 'agent' | 'manual';
  reps?: number;
  body_visible?: boolean;
  cue?: string;
  pose_metrics?: ExercisePoseMetrics;
  analysis?: ExerciseAnalysis;
  adaptation?: ExerciseAdaptation;
}

export type ExerciseEventPublisher = (event: ExerciseTelemetryEvent | ExerciseLessonTelemetryEvent) => Promise<void>;

export interface LiveMirrorEvent {
  type:
    | 'agent_state_changed'
    | 'transcript_finalized'
    | 'metric_updated'
    | 'checkin_progressed'
    | 'memory_used'
    | 'plan_ready'
    | 'checkin_completed'
    | 'exercise_requested'
    | 'exercise_lesson_requested'
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
  exercise?: TrackedMovement;
  target_reps?: number;
  request_id?: string;
  exercise_name?: string;
}

export type LiveMirrorPayload = LiveMirrorEvent | AgUiStateSnapshotEvent | AgUiToolCallEvent;
