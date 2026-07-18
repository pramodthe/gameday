import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { DAILY_PLAN, DEMO_QUESTIONS, DEMO_WORKOUT, INITIAL_METRICS, MEMORY_TEXT } from './demoScenario';
import type { AgentStage, LiveMirrorEvent, MirrorMetric, TranscriptMessage, WorkoutSession } from './types';

const API_BASE = (import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE_URL ?? '')).replace(/\/$/, '');

const wait = (duration: number) => new Promise((resolve) => window.setTimeout(resolve, duration));

function createMessage(speaker: TranscriptMessage['speaker'], text: string): TranscriptMessage {
  return {
    id: `${speaker}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    speaker,
    text,
  };
}

export function useMirrorSession() {
  const [stage, setStage] = useState<AgentStage>('idle');
  const [questionIndex, setQuestionIndex] = useState(0);
  const [metrics, setMetrics] = useState<MirrorMetric[]>(INITIAL_METRICS);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [memoryVisible, setMemoryVisible] = useState(false);
  const [memoryText, setMemoryText] = useState<string | null>(null);
  const [planVisible, setPlanVisible] = useState(false);
  const [plan, setPlan] = useState(DAILY_PLAN);
  const [planSource, setPlanSource] = useState<string | null>(null);
  const [streak, setStreak] = useState(5);
  const [totalSteps, setTotalSteps] = useState(DEMO_QUESTIONS.length);
  const [workout, setWorkout] = useState<WorkoutSession | null>(null);
  const [workoutVisible, setWorkoutVisible] = useState(false);
  const [workoutLoading, setWorkoutLoading] = useState(false);
  const runIdRef = useRef(0);
  const metricsRef = useRef(metrics);

  useEffect(() => {
    metricsRef.current = metrics;
  }, [metrics]);

  const currentQuestion = DEMO_QUESTIONS[questionIndex] ?? null;
  const progress = stage === 'complete' ? totalSteps : Math.min(questionIndex, totalSteps);

  const buildWorkout = useCallback(async (recoveryStatus: string, goal = '', roomName = '') => {
    setWorkoutVisible(true);
    setWorkoutLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/mirror/workout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recovery_status: recoveryStatus, goal, room_name: roomName }),
      });
      if (!response.ok) throw new Error('workout request failed');
      const body = await response.json() as { workout: WorkoutSession };
      setWorkout(body.workout);
    } catch {
      setWorkout(DEMO_WORKOUT);
    } finally {
      setWorkoutLoading(false);
    }
  }, []);

  const say = useCallback(async (text: string, runId: number) => {
    setStage('speaking');
    setMessages((current) => [...current, createMessage('agent', text)]);
    await wait(700);
    if (runIdRef.current === runId) setStage('listening');
  }, []);

  const start = useCallback(async () => {
    const runId = runIdRef.current + 1;
    runIdRef.current = runId;
    setStage('connecting');
    setMessages([]);
    setQuestionIndex(0);
    setMetrics(INITIAL_METRICS);
    setMemoryVisible(false);
    setMemoryText(null);
    setTotalSteps(DEMO_QUESTIONS.length);
    setPlanVisible(false);
    setPlan(DAILY_PLAN);
    setPlanSource(null);
    setStreak(5);
    setWorkout(null);
    setWorkoutVisible(false);
    setWorkoutLoading(false);
    await wait(650);
    if (runIdRef.current !== runId) return;
    await say(
      `Good morning, Jordan. You have team practice tonight. Let’s build today’s game plan. ${DEMO_QUESTIONS[0].prompt}`,
      runId,
    );
  }, [say]);

  const submitAnswer = useCallback(
    async (answer: string) => {
      const normalized = answer.trim();
      if (!normalized || stage !== 'listening' || !currentQuestion) return;
      const runId = runIdRef.current;
      const activeIndex = questionIndex;
      setMessages((current) => [...current, createMessage('athlete', normalized)]);
      setStage('thinking');
      await wait(780);
      if (runIdRef.current !== runId) return;

      setMetrics((current) =>
        current.map((metric) => {
          const update = currentQuestion.updates[metric.key];
          return update ? { ...metric, ...update } : metric;
        }),
      );

      const nextIndex = activeIndex + 1;
      if (nextIndex < DEMO_QUESTIONS.length) {
        setQuestionIndex(nextIndex);
        await say(`${currentQuestion.acknowledgement} ${DEMO_QUESTIONS[nextIndex].prompt}`, runId);
        return;
      }

      setStage('speaking');
      setMessages((current) => [...current, createMessage('agent', currentQuestion.acknowledgement)]);
      await wait(700);
      if (runIdRef.current !== runId) return;
      setMemoryVisible(true);
      setMemoryText(MEMORY_TEXT);
      setMessages((current) => [...current, createMessage('agent', MEMORY_TEXT)]);
      await wait(900);
      if (runIdRef.current !== runId) return;
      setStage('thinking');
      await wait(900);
      if (runIdRef.current !== runId) return;
      setPlanVisible(true);
      setStage('complete');
      setStreak(6);
      setWorkout(DEMO_WORKOUT);
      setWorkoutVisible(true);
    },
    [currentQuestion, questionIndex, say, stage],
  );

  const reset = useCallback(() => {
    runIdRef.current += 1;
    setStage('idle');
    setQuestionIndex(0);
    setMetrics(INITIAL_METRICS);
    setMessages([]);
    setMemoryVisible(false);
    setMemoryText(null);
    setTotalSteps(DEMO_QUESTIONS.length);
    setPlanVisible(false);
    setPlan(DAILY_PLAN);
    setPlanSource(null);
    setStreak(5);
    setWorkout(null);
    setWorkoutVisible(false);
    setWorkoutLoading(false);
  }, []);

  const beginLive = useCallback(() => {
    runIdRef.current += 1;
    setStage('connecting');
    setQuestionIndex(0);
    setMetrics(INITIAL_METRICS);
    setMessages([]);
    setMemoryVisible(false);
    setMemoryText(null);
    setTotalSteps(DEMO_QUESTIONS.length);
    setPlanVisible(false);
    setPlan(DAILY_PLAN);
    setPlanSource(null);
    setStreak(5);
    setWorkout(null);
    setWorkoutVisible(false);
    setWorkoutLoading(false);
  }, []);

  const applyLiveEvent = useCallback(
    (event: LiveMirrorEvent) => {
      if (event.type === 'agent_state_changed' && event.state) {
        setStage(event.state);
        return;
      }
      if (event.type === 'recoverable_error') {
        setStage('listening');
        const message = event.message;
        if (message) setMessages((current) => [...current, createMessage('agent', message)]);
        return;
      }
      if (event.type === 'metric_updated' && event.metric_key && event.display_value && event.status) {
        setMetrics((current) => current.map((metric) => (
          metric.key === event.metric_key
            ? { ...metric, value: event.display_value!, detail: event.detail ?? metric.detail, tone: event.status! }
            : metric
        )));
        return;
      }
      if (event.type === 'checkin_progressed' && event.completed_step !== undefined) {
        const total = event.total_steps ?? DEMO_QUESTIONS.length;
        setTotalSteps(total);
        setQuestionIndex(Math.min(event.completed_step, total));
        return;
      }
      if (event.type === 'memory_used') {
        setMemoryVisible(true);
        const message = event.message;
        if (message) {
          setMemoryText(message);
          setMessages((current) => [...current, createMessage('agent', message)]);
        }
        return;
      }
      if (event.type === 'plan_ready' && event.actions?.length) {
        setPlan(event.actions);
        setPlanSource(event.plan_source ?? null);
        setPlanVisible(true);
        return;
      }
      if (event.type === 'checkin_completed') {
        if (event.streak !== undefined) setStreak(event.streak);
        setStage('complete');
        const recovery = metricsRef.current.find((metric) => metric.key === 'recovery');
        void buildWorkout(recovery?.tone ?? '', '', event.session_id ?? '');
        return;
      }
      if (event.type !== 'transcript_finalized' || !event.speaker || !event.text) return;

      const speaker = event.speaker;
      const text = event.text;
      setMessages((current) => [...current, createMessage(speaker, text)]);
      if (speaker === 'athlete') setStage('thinking');
    },
    [buildWorkout],
  );

  return useMemo(
    () => ({
      stage,
      questionIndex,
      currentQuestion,
      metrics,
      messages,
      memoryVisible,
      memoryText,
      planVisible,
      plan,
      planSource,
      progress,
      totalSteps,
      streak,
      workout,
      workoutVisible,
      workoutLoading,
      start,
      submitAnswer,
      beginLive,
      applyLiveEvent,
      buildWorkout,
      reset,
    }),
    [applyLiveEvent, beginLive, buildWorkout, currentQuestion, memoryText, memoryVisible, messages, metrics, plan, planSource, planVisible, progress, questionIndex, reset, stage, start, streak, submitAnswer, totalSteps, workout, workoutLoading, workoutVisible],
  );
}
