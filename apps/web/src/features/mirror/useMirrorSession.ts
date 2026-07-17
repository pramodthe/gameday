import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { DAILY_PLAN, DEMO_QUESTIONS, INITIAL_METRICS, MEMORY_TEXT } from './demoScenario';
import type { AgentStage, LiveMirrorEvent, MirrorMetric, TranscriptMessage } from './types';

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
  const [streak, setStreak] = useState(5);
  const [totalSteps, setTotalSteps] = useState(DEMO_QUESTIONS.length);
  const runIdRef = useRef(0);

  const currentQuestion = DEMO_QUESTIONS[questionIndex] ?? null;
  const progress = stage === 'complete' ? totalSteps : Math.min(questionIndex, totalSteps);

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
    setStreak(5);
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
    setStreak(5);
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
    setStreak(5);
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
        setPlanVisible(true);
        return;
      }
      if (event.type === 'checkin_completed') {
        if (event.streak !== undefined) setStreak(event.streak);
        setStage('complete');
        return;
      }
      if (event.type !== 'transcript_finalized' || !event.speaker || !event.text) return;

      const speaker = event.speaker;
      const text = event.text;
      setMessages((current) => [...current, createMessage(speaker, text)]);
      if (speaker === 'agent') {
        setStage('speaking');
        return;
      }

      const activeQuestion = DEMO_QUESTIONS[questionIndex];
      if (!activeQuestion) return;
      setStage('thinking');
      setMetrics((current) =>
        current.map((metric) => {
          const update = activeQuestion.updates[metric.key];
          return update ? { ...metric, ...update } : metric;
        }),
      );
      const nextIndex = questionIndex + 1;
      setQuestionIndex(nextIndex);
    },
    [questionIndex],
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
      progress,
      totalSteps,
      streak,
      start,
      submitAnswer,
      beginLive,
      applyLiveEvent,
      reset,
    }),
    [applyLiveEvent, beginLive, currentQuestion, memoryText, memoryVisible, messages, metrics, plan, planVisible, progress, questionIndex, reset, stage, start, streak, submitAnswer, totalSteps],
  );
}
