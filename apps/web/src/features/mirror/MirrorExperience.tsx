import { AnimatePresence, motion } from 'motion/react';
import {
  Activity,
  Brain,
  Camera,
  CameraOff,
  ChevronRight,
  CircleDollarSign,
  Dumbbell,
  Flame,
  Gauge,
  Mic,
  MicOff,
  MoonStar,
  Radio,
  RotateCcw,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Utensils,
  WalletCards,
} from 'lucide-react';
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { CameraBackdrop } from './CameraBackdrop';
import { ExerciseLessonCard } from './ExerciseLessonCard';
import { LiveKitCameraBackdrop } from './LiveKitCameraBackdrop';
import { MovementCoach } from './MovementCoach';
import { WorkoutSessionCard } from './WorkoutSessionCard';
import { useMirrorSession } from './useMirrorSession';
import type { AgUiToolCallEvent, ExerciseEventPublisher, ExerciseLesson, LiveMirrorConfig, LiveMirrorPayload, MetricKey, MirrorMetric, TrackedMovement, WorkoutExercise } from './types';
import './mirror.css';

const API_BASE = (import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE_URL ?? '')).replace(/\/$/, '');

const metricIcons: Record<MetricKey, typeof MoonStar> = {
  sleep: MoonStar,
  recovery: Gauge,
  training: Dumbbell,
  fuel: Utensils,
  mindset: Brain,
  spending: CircleDollarSign,
};

const stageLabels = {
  idle: 'Ready when you are',
  connecting: 'Opening the mirror',
  speaking: 'Nova is speaking',
  listening: 'Listening',
  thinking: 'Building context',
  complete: 'Check-in complete',
};

function isAgUiToolCallEvent(event: LiveMirrorPayload): event is AgUiToolCallEvent {
  return event.type === 'TOOL_CALL_START'
    || event.type === 'TOOL_CALL_ARGS'
    || event.type === 'TOOL_CALL_END'
    || event.type === 'TOOL_CALL_RESULT';
}

function isTrackedMovement(value: string | null): value is TrackedMovement {
  return value === 'squat'
    || value === 'pushup'
    || value === 'lunge'
    || value === 'plank'
    || value === 'glute_bridge';
}

function MetricRow({ metric, active }: { metric: MirrorMetric; active: boolean }) {
  const Icon = metricIcons[metric.key];
  return (
    <motion.div
      layout
      className="mirror-metric"
      data-tone={metric.tone}
      data-active={active}
      transition={{ type: 'spring', stiffness: 280, damping: 26 }}
    >
      <span className="mirror-metric__icon"><Icon size={17} strokeWidth={1.8} /></span>
      <span className="mirror-metric__copy">
        <span>{metric.label}</span>
        <small>{metric.detail}</small>
      </span>
      <motion.strong key={metric.value} initial={{ opacity: 0, y: 7 }} animate={{ opacity: 1, y: 0 }}>
        {metric.value}
      </motion.strong>
    </motion.div>
  );
}

function AudioAura({ active }: { active: boolean }) {
  return (
    <span className="mirror-aura" data-active={active} aria-hidden="true">
      {Array.from({ length: 12 }, (_, index) => (
        <i key={index} style={{ '--bar-index': index } as CSSProperties} />
      ))}
    </span>
  );
}

export function MirrorExperience() {
  const session = useMirrorSession();
  const [cameraEnabled, setCameraEnabled] = useState(true);
  const [cameraAvailable, setCameraAvailable] = useState(false);
  const [draft, setDraft] = useState('');
  const [speechSupported, setSpeechSupported] = useState(false);
  const [browserListening, setBrowserListening] = useState(false);
  const [liveConfig, setLiveConfig] = useState<LiveMirrorConfig>({ configured: false });
  const [liveMode, setLiveMode] = useState(false);
  const [movementMode, setMovementMode] = useState(false);
  const [movementExercise, setMovementExercise] = useState<TrackedMovement>('squat');
  const [exerciseRequestId, setExerciseRequestId] = useState<string>();
  const [lessonRequest, setLessonRequest] = useState<{ requestId: string; exerciseName: string; lesson?: ExerciseLesson } | null>(null);
  const [cameraVideo, setCameraVideo] = useState<HTMLVideoElement | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const exercisePublisherRef = useRef<ExerciseEventPublisher | null>(null);
  const sharedStateRevisionRef = useRef(-1);

  const activeMetric = session.currentQuestion?.id;
  const bodyMetrics = session.metrics.slice(0, 3);
  const lifeMetrics = session.metrics.slice(3);
  const visibleMessages = session.messages.slice(-3);

  useEffect(() => {
    const SpeechRecognitionConstructor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    setSpeechSupported(Boolean(SpeechRecognitionConstructor));
    if (!SpeechRecognitionConstructor) return;
    const recognition = new SpeechRecognitionConstructor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    recognition.onresult = (event) => {
      let transcript = '';
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
      }
      setDraft(transcript.trim());
    };
    recognition.onend = () => setBrowserListening(false);
    recognition.onerror = () => setBrowserListening(false);
    recognitionRef.current = recognition;
    return () => recognition.abort();
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/api/mirror/config`)
      .then(async (response) => (response.ok ? response.json() : Promise.reject()))
      .then((config: LiveMirrorConfig) => setLiveConfig(config))
      .catch(() => setLiveConfig({ configured: false }));
  }, []);

  const requestLiveSession = useCallback(async () => {
    sharedStateRevisionRef.current = -1;
    session.beginLive();
    try {
      const response = await fetch(`${API_BASE}/api/mirror/token`, { method: 'POST' });
      if (!response.ok) throw new Error('Live session unavailable');
      const config = (await response.json()) as LiveMirrorConfig;
      setLiveConfig(config);
      setLiveMode(true);
    } catch {
      setLiveMode(false);
      session.reset();
    }
  }, [session]);

  const handleLiveEvent = useCallback((event: LiveMirrorPayload) => {
    if (event.type === 'STATE_SNAPSHOT') {
      const sharedState = event.snapshot;
      if (sharedState.revision <= sharedStateRevisionRef.current) return;
      sharedStateRevisionRef.current = sharedState.revision;
      const exercise = sharedState.exercise;
      if (exercise.mode === 'idle') {
        setLessonRequest(null);
        setExerciseRequestId(undefined);
        setMovementMode(false);
        return;
      }
      if (exercise.mode === 'lesson') {
        setMovementMode(false);
        setExerciseRequestId(undefined);
        if (exercise.status === 'closed') {
          setLessonRequest(null);
          return;
        }
        if (exercise.requestId && exercise.name) {
          setLessonRequest({
            requestId: exercise.requestId,
            exerciseName: exercise.name,
            lesson: exercise.lesson ?? undefined,
          });
        }
        return;
      }
      setLessonRequest(null);
      if (exercise.status === 'closed') {
        setMovementMode(false);
        setExerciseRequestId(undefined);
        return;
      }
      if (exercise.requestId) {
        if (isTrackedMovement(exercise.name)) setMovementExercise(exercise.name);
        setExerciseRequestId(exercise.requestId);
        setMovementMode(true);
      }
      return;
    }
    if (isAgUiToolCallEvent(event)) return;
    if (event.type === 'exercise_requested' && event.exercise && isTrackedMovement(event.exercise)) {
      setLessonRequest(null);
      setMovementExercise(event.exercise);
      setExerciseRequestId(event.request_id ?? crypto.randomUUID());
      setMovementMode(true);
    }
    if (event.type === 'exercise_lesson_requested' && event.exercise_name) {
      setMovementMode(false);
      setExerciseRequestId(undefined);
      setLessonRequest({
        requestId: event.request_id ?? crypto.randomUUID(),
        exerciseName: event.exercise_name,
      });
    }
    session.applyLiveEvent(event);
  }, [session]);

  const handleExercisePublisherChange = useCallback((publisher: ExerciseEventPublisher | null) => {
    exercisePublisherRef.current = publisher;
  }, []);

  const publishExerciseEvent = useCallback((event: Parameters<ExerciseEventPublisher>[0]) => {
    if (exercisePublisherRef.current) void exercisePublisherRef.current(event);
  }, []);

  const closeExercise = useCallback(() => {
    setMovementMode(false);
    setExerciseRequestId(undefined);
  }, []);

  const submitDraft = useCallback(() => {
    const answer = draft.trim();
    if (!answer) return;
    setDraft('');
    void session.submitAnswer(answer);
  }, [draft, session]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    submitDraft();
  };

  const toggleBrowserListening = () => {
    if (!recognitionRef.current || session.stage !== 'listening') return;
    if (browserListening) {
      recognitionRef.current.stop();
      setBrowserListening(false);
      return;
    }
    setDraft('');
    setBrowserListening(true);
    recognitionRef.current.start();
  };

  const progressDots = useMemo(
    () => Array.from({ length: session.totalSteps }, (_, index) => index < session.progress),
    [session.progress, session.totalSteps],
  );

  return (
    <main className="mirror-shell" data-movement={movementMode} data-lesson={Boolean(lessonRequest)}>
      <div className="mirror-media">
        {liveMode && liveConfig.token ? (
          <LiveKitCameraBackdrop
            config={liveConfig}
            onConnected={() => session.applyLiveEvent({ type: 'agent_state_changed', state: 'listening' })}
            onDisconnected={() => setLiveMode(false)}
            onEvent={handleLiveEvent}
            controlsHidden={Boolean(lessonRequest)}
            onExercisePublisherChange={handleExercisePublisherChange}
            onVideoElementChange={setCameraVideo}
          />
        ) : (
          <CameraBackdrop
            enabled={cameraEnabled}
            onAvailabilityChange={setCameraAvailable}
            onVideoElementChange={setCameraVideo}
          />
        )}
      </div>
      <MovementCoach
        active={movementMode}
        videoElement={cameraVideo}
        roomName={liveConfig.roomName}
        exercise={movementExercise}
        autoStartRequestId={exerciseRequestId}
        onExerciseEvent={publishExerciseEvent}
        onClose={closeExercise}
      />
      <AnimatePresence>
        {lessonRequest && (
          <ExerciseLessonCard
            key={lessonRequest.requestId}
            request={lessonRequest}
            onEvent={publishExerciseEvent}
            onClose={() => setLessonRequest(null)}
            onPractice={(movement) => {
              setMovementExercise(movement);
              setLessonRequest(null);
              setExerciseRequestId(`manual-${crypto.randomUUID()}`);
              setMovementMode(true);
            }}
          />
        )}
      </AnimatePresence>
      <div className="mirror-grade" />
      <div className="mirror-grain" />

      <header className="mirror-header">
        <div className="mirror-brand">
          <span className="mirror-brand__mark"><Activity size={18} /></span>
          <span><strong>GAMEDAY</strong><small>mirror</small></span>
        </div>
        <div className="mirror-session-pill">
          <span className="mirror-live-dot" data-live={session.stage !== 'idle'} />
          {stageLabels[session.stage]}
        </div>
        <div className="mirror-header__actions">
          <button
            type="button"
            className="mirror-mode-pill mirror-vision-pill"
            data-active={movementMode}
            disabled={!cameraEnabled || !cameraVideo}
            onClick={() => {
              setLessonRequest(null);
              setMovementExercise('squat');
              setMovementMode((current) => {
                setExerciseRequestId(current ? undefined : `manual-${crypto.randomUUID()}`);
                return !current;
              });
            }}
            title="Start a guided camera exercise"
          >
            <ScanLine size={14} /> {movementMode ? 'Exercise active' : 'Start exercise'}
          </button>
          <button
            type="button"
            className="mirror-mode-pill"
            data-active={liveMode}
            onClick={liveConfig.configured ? requestLiveSession : undefined}
            title={liveConfig.configured ? 'Connect LiveKit and ElevenLabs' : 'Add LiveKit credentials to enable live mode'}
          >
            <Radio size={14} /> {liveMode ? 'Live agent' : 'Demo mode'}
          </button>
          <button
            type="button"
            className="mirror-icon-button"
            onClick={() => setCameraEnabled((current) => !current)}
            aria-label={cameraEnabled ? 'Turn camera off' : 'Turn camera on'}
          >
            {cameraEnabled && cameraAvailable ? <Camera size={17} /> : <CameraOff size={17} />}
          </button>
        </div>
      </header>

      <section className="mirror-stage">
        <motion.aside
          className="mirror-card mirror-card--metrics"
          initial={{ opacity: 0, x: -22 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="mirror-card__heading">
            <span><ShieldCheck size={17} /> Body today</span>
            <small>Live profile</small>
          </div>
          <div className="mirror-metric-list">
            {bodyMetrics.map((metric) => (
              <MetricRow key={metric.key} metric={metric} active={metric.key === activeMetric} />
            ))}
          </div>
          <div className="mirror-card__divider" />
          <div className="mirror-card__heading mirror-card__heading--secondary">
            <span><WalletCards size={17} /> Life today</span>
            <small>Off-field</small>
          </div>
          <div className="mirror-metric-list">
            {lifeMetrics.map((metric) => (
              <MetricRow key={metric.key} metric={metric} active={metric.key === activeMetric} />
            ))}
          </div>
          <div className="mirror-streak">
            <span><Flame size={20} /> {session.streak}-day rhythm</span>
            <span className="mirror-streak__bars">
              {Array.from({ length: 7 }, (_, index) => <i key={index} data-filled={index < session.streak} />)}
            </span>
          </div>
        </motion.aside>

        <motion.section
          className="mirror-card mirror-card--conversation"
          initial={{ opacity: 0, x: 22 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="mirror-card__heading">
            <span><Sparkles size={17} /> Nova check-in</span>
            <small>{Math.min(session.progress + (session.stage === 'listening' ? 1 : 0), session.totalSteps)}/{session.totalSteps}</small>
          </div>
          <div className="mirror-progress" aria-label={`${session.progress} of ${session.totalSteps} questions complete`}>
            {progressDots.map((filled, index) => <i key={index} data-filled={filled} />)}
          </div>

          <div className="mirror-transcript" aria-live="polite">
            <AnimatePresence mode="popLayout">
              {visibleMessages.length === 0 ? (
                <motion.div className="mirror-empty-copy" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <span>90 seconds</span>
                  <strong>One honest conversation.<br />A better day.</strong>
                  <p>Recovery, training, focus, and everyday accountability—connected.</p>
                </motion.div>
              ) : (
                visibleMessages.map((message) => (
                  <motion.div
                    layout
                    key={message.id}
                    className="mirror-message"
                    data-speaker={message.speaker}
                    initial={{ opacity: 0, y: 12, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8 }}
                  >
                    <small>{message.speaker === 'agent' ? 'Nova' : 'You'}</small>
                    <p>{message.text}</p>
                  </motion.div>
                ))
              )}
            </AnimatePresence>
          </div>

          <AnimatePresence>
            {session.memoryVisible && (
              <motion.div className="mirror-memory" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                <span><Brain size={15} /> Memory used</span>
                <small>{session.memoryText ?? 'Recalling your last check-in…'}</small>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.section>
      </section>

      <footer className="mirror-controls">
        {session.stage === 'idle' ? (
          <motion.button
            type="button"
            className="mirror-start-button"
            onClick={liveConfig.configured ? requestLiveSession : session.start}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <span><Mic size={20} /></span>
            Start daily check-in
            <ChevronRight size={19} />
          </motion.button>
        ) : session.stage === 'complete' ? (
          <button type="button" className="mirror-reset-button" onClick={session.reset}>
            <RotateCcw size={17} /> Run demo again
          </button>
        ) : liveMode ? (
          <div className="mirror-live-prompt">
            <AudioAura active={session.stage === 'listening' || session.stage === 'speaking'} />
            <Mic size={18} />
            <span><small>Live with Nova</small>{stageLabels[session.stage]}</span>
          </div>
        ) : (
          <form className="mirror-answer" onSubmit={handleSubmit}>
            <button
              type="button"
              className="mirror-mic-button"
              data-active={browserListening || session.stage === 'speaking'}
              disabled={session.stage !== 'listening' || !speechSupported}
              onClick={toggleBrowserListening}
              aria-label={browserListening ? 'Stop listening' : 'Answer with voice'}
            >
              <AudioAura active={browserListening || session.stage === 'speaking'} />
              {browserListening ? <MicOff size={23} /> : <Mic size={23} />}
            </button>
            <label className="mirror-answer__field">
              <span>{session.stage === 'listening' ? 'Your answer' : stageLabels[session.stage]}</span>
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={session.stage === 'listening' ? 'Speak or type naturally…' : 'Nova is working…'}
                disabled={session.stage !== 'listening'}
              />
            </label>
            <button type="submit" className="mirror-send-button" disabled={!draft.trim() || session.stage !== 'listening'}>
              Send <ChevronRight size={16} />
            </button>
            <button
              type="button"
              className="mirror-demo-answer"
              disabled={session.stage !== 'listening'}
              onClick={() => session.currentQuestion && session.submitAnswer(session.currentQuestion.demoAnswer)}
            >
              Use demo answer
            </button>
          </form>
        )}
      </footer>

      <AnimatePresence>
        {session.planVisible && !movementMode && !lessonRequest && (
          <motion.section className="mirror-plan" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.div
              className="mirror-plan__panel"
              initial={{ opacity: 0, y: 36, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ type: 'spring', stiffness: 220, damping: 24 }}
            >
              <div className="mirror-plan__eyebrow">
                <Sparkles size={15} /> {session.planSource === 'lyzr' ? 'Lyzr Performance Director · today + memory' : 'Built from today + yesterday'}
              </div>
              <h1>Jordan’s game plan</h1>
              <p>Three moves. Zero noise. Protect tonight’s practice without ignoring the rest of your life.</p>
              <div className="mirror-plan__actions">
                {session.plan.map((action, index) => (
                  <motion.article
                    key={action.id}
                    initial={{ opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.18 + index * 0.1 }}
                  >
                    <span>0{index + 1}</span>
                    <small>{action.eyebrow}</small>
                    <h2>{action.title}</h2>
                    <p>{action.detail}</p>
                  </motion.article>
                ))}
              </div>
              <WorkoutSessionCard
                workout={session.workout}
                visible={session.workoutVisible}
                loading={session.workoutLoading}
                onStartExercise={(exercise: WorkoutExercise) => {
                  setLessonRequest(null);
                  setMovementExercise(exercise.motion_pattern);
                  setExerciseRequestId(`workout-${crypto.randomUUID()}`);
                  setMovementMode(true);
                }}
                onRebuild={() => {
                  const recovery = session.metrics.find((metric) => metric.key === 'recovery');
                  void session.buildWorkout(recovery?.tone ?? '', '', liveConfig.roomName ?? '');
                }}
              />
              <div className="mirror-plan__footer">
                <span><Flame size={18} /> 6-day rhythm locked</span>
                <button type="button" onClick={session.reset}>Done for today <ChevronRight size={17} /></button>
              </div>
            </motion.div>
          </motion.section>
        )}
      </AnimatePresence>
    </main>
  );
}
