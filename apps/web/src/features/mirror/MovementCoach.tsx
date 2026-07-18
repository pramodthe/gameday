import type { NormalizedLandmark, PoseLandmarker } from '@mediapipe/tasks-vision';
import { AnimatePresence, motion } from 'motion/react';
import { Check, ChevronRight, Eye, Flag, LoaderCircle, Play, RotateCcw, ScanLine, Sparkles, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ExerciseAdaptation, ExerciseAnalysis, ExercisePoseMetrics, ExerciseTelemetryEvent, TrackedMovement } from './types';

const API_BASE = (import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE_URL ?? '')).replace(/\/$/, '');
const WASM_ROOT = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm';
const MODEL_PATH = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task';

// MediaPipe landmark triplets forming a joint angle: [end, vertex, end].
type Triplet = [number, number, number];

interface RepFormSpec {
  kind: 'rep';
  primary: Triplet[];                 // angle averaged (or min) across these joints
  aggregate: 'avg' | 'min';           // min = single working limb (e.g. lunge front leg)
  direction: 'flexion' | 'extension'; // flexion: rep bottoms out LOW; extension: tops out HIGH
  enterAngle: number;                 // cross into the working phase
  exitAngle: number;                  // return past this to count a rep
  alignment: 'torso' | 'bodyline' | 'hips_level';
  symmetry?: [Triplet, Triplet];      // left/right joints compared for balance
  tracked: number[];                  // landmarks that must be visible
  targetReps: number;
  title: string;
  subtitle: string;
  tempo: string;
  primaryLabel: string;
  depthLabel: (achieved: number) => string;
  startCue: string;
  cues: {
    deep: string; ascend: string; descend: string; symmetry: string; align: string;
    symMax: number; alignMax: number;
  };
}

interface HoldFormSpec {
  kind: 'hold';
  alignment: 'torso' | 'bodyline' | 'hips_level';
  tracked: number[];
  holdSeconds: number;
  alignGood: number;
  title: string;
  subtitle: string;
  tempo: string;
  startCue: string;
  cues: { align: string; hold: string; alignMax: number };
}

type FormSpec = RepFormSpec | HoldFormSpec;

const FORM_SPECS: Record<TrackedMovement, FormSpec> = {
  squat: {
    kind: 'rep',
    primary: [[23, 25, 27], [24, 26, 28]],
    aggregate: 'avg',
    direction: 'flexion',
    enterAngle: 118,
    exitAngle: 154,
    alignment: 'torso',
    symmetry: [[23, 25, 27], [24, 26, 28]],
    tracked: [11, 12, 23, 24, 25, 26, 27, 28],
    targetReps: 5,
    title: 'Squat control set',
    subtitle: 'Movement · Lower body',
    tempo: '5 reps · bodyweight · about 30 seconds',
    primaryLabel: 'Depth',
    depthLabel: (a) => (a < 110 ? 'Full' : a < 125 ? 'Close' : 'High'),
    startCue: 'Stand tall, then lower with control.',
    cues: {
      deep: 'Good depth. Drive through both feet and stand tall.',
      ascend: 'Drive up and finish the rep standing tall.',
      descend: 'Lower with control. Keep your knees tracking evenly.',
      symmetry: 'Balance both knees and keep pressure even through your feet.',
      align: 'Brace your trunk and keep your chest stacked over your hips.',
      symMax: 14, alignMax: 28,
    },
  },
  pushup: {
    kind: 'rep',
    primary: [[11, 13, 15], [12, 14, 16]],
    aggregate: 'avg',
    direction: 'flexion',
    enterAngle: 100,
    exitAngle: 150,
    alignment: 'bodyline',
    symmetry: [[11, 13, 15], [12, 14, 16]],
    tracked: [11, 12, 13, 14, 23, 24, 27, 28],
    targetReps: 8,
    title: 'Push-up set',
    subtitle: 'Movement · Upper body',
    tempo: '8 reps · bodyweight',
    primaryLabel: 'Depth',
    depthLabel: (a) => (a < 95 ? 'Full' : a < 115 ? 'Close' : 'High'),
    startCue: 'Set your plank, then lower your chest with control.',
    cues: {
      deep: 'Chest low. Now press the floor away.',
      ascend: 'Press up and lock out your elbows.',
      descend: 'Lower under control with elbows tucked.',
      symmetry: 'Press evenly through both hands so your shoulders stay square.',
      align: 'Keep a straight line from shoulders to heels — no sagging or piking.',
      symMax: 14, alignMax: 16,
    },
  },
  lunge: {
    kind: 'rep',
    primary: [[23, 25, 27], [24, 26, 28]],
    aggregate: 'min',
    direction: 'flexion',
    enterAngle: 110,
    exitAngle: 150,
    alignment: 'torso',
    tracked: [11, 12, 23, 24, 25, 26, 27, 28],
    targetReps: 6,
    title: 'Lunge set',
    subtitle: 'Movement · Lower body',
    tempo: '6 reps · alternating',
    primaryLabel: 'Depth',
    depthLabel: (a) => (a < 100 ? 'Full' : a < 120 ? 'Close' : 'High'),
    startCue: 'Step forward and lower your back knee toward the floor.',
    cues: {
      deep: 'Great depth. Push through your front heel to stand.',
      ascend: 'Drive up through your front heel and stand tall.',
      descend: 'Lower straight down, front shin vertical.',
      symmetry: 'Keep your front knee tracking over your toes.',
      align: 'Stay tall through your torso instead of leaning forward.',
      symMax: 999, alignMax: 26,
    },
  },
  glute_bridge: {
    kind: 'rep',
    primary: [[11, 23, 25], [12, 24, 26]],
    aggregate: 'avg',
    direction: 'extension',
    enterAngle: 150,
    exitAngle: 120,
    alignment: 'hips_level',
    symmetry: [[11, 23, 25], [12, 24, 26]],
    tracked: [11, 12, 23, 24, 25, 26],
    targetReps: 10,
    title: 'Glute bridge set',
    subtitle: 'Movement · Posterior chain',
    tempo: '10 reps · bodyweight',
    primaryLabel: 'Lift',
    depthLabel: (a) => (a > 165 ? 'Full' : a > 150 ? 'Close' : 'Low'),
    startCue: 'Lie back with feet planted, then drive your hips up.',
    cues: {
      deep: 'Full extension — squeeze your glutes at the top.',
      ascend: 'Lift your hips to a straight line.',
      descend: 'Lower with control, don’t drop your hips.',
      symmetry: 'Keep both hips rising together.',
      align: 'Keep your hips level as you lift.',
      symMax: 12, alignMax: 25,
    },
  },
  plank: {
    kind: 'hold',
    alignment: 'bodyline',
    tracked: [11, 12, 23, 24, 27, 28],
    holdSeconds: 30,
    alignGood: 12,
    title: 'Plank hold',
    subtitle: 'Movement · Core',
    tempo: 'Hold ~30 seconds',
    startCue: 'Set your forearms and hold a straight line.',
    cues: {
      align: 'Level your hips — one straight line from shoulders to heels.',
      hold: 'Hold steady and keep breathing.',
      alignMax: 14,
    },
  },
};

interface MovementCoachProps {
  active: boolean;
  videoElement: HTMLVideoElement | null;
  roomName?: string;
  exercise?: TrackedMovement;
  autoStartRequestId?: string;
  onExerciseEvent?: (event: ExerciseTelemetryEvent) => void;
  onClose: () => void;
}

type ExerciseState = 'setup' | 'countdown' | 'active' | 'analyzing' | 'complete';

const initialMetrics: ExercisePoseMetrics = {
  reps: 0,
  primary_angle: 180,
  min_primary_angle: 180,
  max_primary_angle: 0,
  symmetry_gap: 0,
  alignment_deviation: 0,
  visibility: 0,
  hold_seconds: 0,
};

type Point = { x: number; y: number };

function angle(first: Point, middle: Point, last: Point) {
  const firstVector = { x: first.x - middle.x, y: first.y - middle.y };
  const lastVector = { x: last.x - middle.x, y: last.y - middle.y };
  const dot = firstVector.x * lastVector.x + firstVector.y * lastVector.y;
  const firstLength = Math.hypot(firstVector.x, firstVector.y);
  const lastLength = Math.hypot(lastVector.x, lastVector.y);
  const cosine = Math.max(-1, Math.min(1, dot / Math.max(firstLength * lastLength, 0.0001)));
  return Math.acos(cosine) * (180 / Math.PI);
}

function midpoint(first: NormalizedLandmark, second: NormalizedLandmark) {
  return { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
}

function tripletAngle(landmarks: NormalizedLandmark[], [a, b, c]: Triplet) {
  return angle(landmarks[a], landmarks[b], landmarks[c]);
}

function primaryAngle(landmarks: NormalizedLandmark[], spec: FormSpec): number {
  if (spec.kind !== 'rep') return 180;
  const values = spec.primary.map((triplet) => tripletAngle(landmarks, triplet));
  return spec.aggregate === 'min' ? Math.min(...values) : values.reduce((sum, v) => sum + v, 0) / values.length;
}

function alignmentDeviation(landmarks: NormalizedLandmark[], kind: FormSpec['alignment']): number {
  if (kind === 'hips_level') {
    return Math.abs(landmarks[23].y - landmarks[24].y) * 100;
  }
  const shoulders = midpoint(landmarks[11], landmarks[12]);
  const hips = midpoint(landmarks[23], landmarks[24]);
  if (kind === 'bodyline') {
    const ankles = midpoint(landmarks[27], landmarks[28]);
    const line = angle(shoulders, hips, ankles);
    return Math.abs(180 - line);
  }
  return Math.atan2(Math.abs(shoulders.x - hips.x), Math.abs(shoulders.y - hips.y)) * (180 / Math.PI);
}

export function MovementCoach({
  active,
  videoElement,
  roomName,
  exercise = 'squat',
  autoStartRequestId,
  onExerciseEvent,
  onClose,
}: MovementCoachProps) {
  const spec = FORM_SPECS[exercise];
  const goal = spec.kind === 'hold' ? spec.holdSeconds : spec.targetReps;

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const landmarkerRef = useRef<PoseLandmarker | null>(null);
  const visionModuleRef = useRef<typeof import('@mediapipe/tasks-vision') | null>(null);
  const animationRef = useRef<number | null>(null);
  const lastVideoTimeRef = useRef(-1);
  const phaseRef = useRef<'up' | 'down'>('up');
  const previousPrimaryRef = useRef(180);
  const holdTickRef = useRef<number | null>(null);
  const exerciseStateRef = useRef<ExerciseState>('setup');
  const specRef = useRef<FormSpec>(spec);
  const onExerciseEventRef = useRef(onExerciseEvent);
  const autoStartedRequestRef = useRef<string | undefined>(undefined);
  const lastBodyLockedRef = useRef<boolean | undefined>(undefined);
  const samplesRef = useRef({ count: 0, symmetry: 0, align: 0, minPrimary: 180, maxPrimary: 0, reps: 0, hold: 0 });
  const roomRef = useRef(`movement-${crypto.randomUUID()}`);
  const [metrics, setMetrics] = useState<ExercisePoseMetrics>(initialMetrics);
  const [modelState, setModelState] = useState<'idle' | 'loading' | 'tracking' | 'error'>('idle');
  const [exerciseState, setExerciseState] = useState<ExerciseState>('setup');
  const [countdown, setCountdown] = useState(3);
  const [liveCue, setLiveCue] = useState('Step back until your full body is visible.');
  const [cueTone, setCueTone] = useState<'neutral' | 'good' | 'attention'>('neutral');
  const [repPulse, setRepPulse] = useState(0);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<ExerciseAnalysis | null>(null);
  const [adaptation, setAdaptation] = useState<ExerciseAdaptation | null>(null);
  const [persisted, setPersisted] = useState(false);

  useEffect(() => {
    specRef.current = spec;
  }, [spec]);

  const emitExerciseEvent = useCallback((event: Omit<ExerciseTelemetryEvent, 'exercise' | 'target_reps' | 'timestamp'>) => {
    onExerciseEventRef.current?.({
      exercise,
      target_reps: goal,
      timestamp: new Date().toISOString(),
      request_id: autoStartRequestId,
      ...event,
    });
  }, [autoStartRequestId, exercise, goal]);

  const bodyLocked = modelState === 'tracking' && metrics.visibility >= 0.55;
  const progress = spec.kind === 'hold' ? Math.floor(metrics.hold_seconds ?? 0) : metrics.reps;

  const clearMeasurements = useCallback(() => {
    samplesRef.current = { count: 0, symmetry: 0, align: 0, minPrimary: 180, maxPrimary: 0, reps: 0, hold: 0 };
    phaseRef.current = specRef.current.kind === 'rep' && specRef.current.direction === 'extension' ? 'down' : 'up';
    previousPrimaryRef.current = 180;
    holdTickRef.current = null;
    setMetrics(initialMetrics);
    setRepPulse(0);
  }, []);

  const reset = useCallback(() => {
    clearMeasurements();
    setExerciseState('setup');
    setCountdown(3);
    setLiveCue('Step back until your full body is visible.');
    setCueTone('neutral');
    setAnalysis(null);
    setAdaptation(null);
    setPersisted(false);
    setAnalyzing(false);
  }, [clearMeasurements]);

  useEffect(() => {
    onExerciseEventRef.current = onExerciseEvent;
  }, [onExerciseEvent]);

  useEffect(() => {
    exerciseStateRef.current = exerciseState;
  }, [exerciseState]);

  useEffect(() => {
    if (!active) return;
    reset();
    autoStartedRequestRef.current = undefined;
    lastBodyLockedRef.current = undefined;
    emitExerciseEvent({
      type: 'exercise_opened',
      trigger: autoStartRequestId && !autoStartRequestId.startsWith('manual-') && !autoStartRequestId.startsWith('workout-')
        ? 'agent'
        : 'manual',
      body_visible: false,
      cue: 'Waiting for a full-body camera lock.',
    });
  }, [active, autoStartRequestId, emitExerciseEvent, reset]);

  useEffect(() => {
    if (!active || bodyLocked === lastBodyLockedRef.current) return;
    lastBodyLockedRef.current = bodyLocked;
    emitExerciseEvent({
      type: bodyLocked ? 'exercise_ready' : 'exercise_waiting',
      body_visible: bodyLocked,
      reps: metrics.reps,
      cue: bodyLocked
        ? 'Full body detected. The exercise can begin.'
        : 'Step back until your working joints are visible.',
    });
  }, [active, bodyLocked, emitExerciseEvent, metrics.reps]);

  useEffect(() => {
    if (exerciseState !== 'countdown') return;
    const timer = window.setTimeout(() => {
      if (countdown > 1) {
        setCountdown((value) => value - 1);
        return;
      }
      clearMeasurements();
      setExerciseState('active');
      setLiveCue(specRef.current.startCue);
      setCueTone('good');
      emitExerciseEvent({
        type: 'exercise_started',
        body_visible: true,
        reps: 0,
        cue: `${specRef.current.title} started.`,
      });
    }, countdown > 1 ? 850 : 700);
    return () => window.clearTimeout(timer);
  }, [clearMeasurements, countdown, emitExerciseEvent, exerciseState]);

  useEffect(() => {
    if (!active || !videoElement) return;
    const video = videoElement;
    let disposed = false;

    async function loadAndTrack() {
      setModelState('loading');
      try {
        if (!landmarkerRef.current) {
          const visionTasks = await import('@mediapipe/tasks-vision');
          visionModuleRef.current = visionTasks;
          const vision = await visionTasks.FilesetResolver.forVisionTasks(WASM_ROOT);
          landmarkerRef.current = await visionTasks.PoseLandmarker.createFromOptions(vision, {
            baseOptions: { modelAssetPath: MODEL_PATH, delegate: 'GPU' },
            runningMode: 'VIDEO',
            numPoses: 1,
            minPoseDetectionConfidence: 0.55,
            minPosePresenceConfidence: 0.55,
            minTrackingConfidence: 0.55,
          });
        }
        if (disposed) return;
        setModelState('tracking');

        const track = () => {
          if (disposed || !landmarkerRef.current || !visionModuleRef.current || !canvasRef.current) return;
          if (video.readyState >= 2 && video.currentTime !== lastVideoTimeRef.current) {
            lastVideoTimeRef.current = video.currentTime;
            const result = landmarkerRef.current.detectForVideo(video, performance.now());
            const canvas = canvasRef.current;
            const context = canvas.getContext('2d');
            if (context) {
              canvas.width = video.videoWidth || 1280;
              canvas.height = video.videoHeight || 720;
              context.clearRect(0, 0, canvas.width, canvas.height);
              const landmarks = result.landmarks[0];
              if (landmarks) {
                const activeSpec = specRef.current;
                const primary = primaryAngle(landmarks, activeSpec);
                const alignment = alignmentDeviation(landmarks, activeSpec.alignment);
                const symmetry = activeSpec.kind === 'rep' && activeSpec.symmetry
                  ? Math.abs(tripletAngle(landmarks, activeSpec.symmetry[0]) - tripletAngle(landmarks, activeSpec.symmetry[1]))
                  : 0;
                const trackedJoints = activeSpec.tracked.map((index) => landmarks[index]);
                const jointsInsideFrame = trackedJoints.every((landmark) => (
                  landmark.x >= 0.02 && landmark.x <= 0.98 && landmark.y >= 0.02 && landmark.y <= 0.98
                ));
                const visibility = jointsInsideFrame
                  ? Math.min(...trackedJoints.map((landmark) => landmark.visibility ?? 0))
                  : 0;
                const alignMax = activeSpec.kind === 'rep' ? activeSpec.cues.alignMax : activeSpec.cues.alignMax;
                const symMax = activeSpec.kind === 'rep' ? activeSpec.cues.symMax : 999;
                const trackingColor = symmetry > symMax || alignment > alignMax ? '#ffbf5b' : '#c9ff3d';
                const drawing = new visionModuleRef.current.DrawingUtils(context);
                drawing.drawConnectors(landmarks, visionModuleRef.current.PoseLandmarker.POSE_CONNECTIONS, {
                  color: trackingColor,
                  lineWidth: 4,
                });
                drawing.drawLandmarks(landmarks, {
                  color: '#f6f5ef',
                  fillColor: '#101510',
                  lineWidth: 2,
                  radius: 4,
                });

                const samples = samplesRef.current;
                samples.count += 1;
                samples.symmetry += symmetry;
                samples.align += alignment;
                samples.minPrimary = Math.min(samples.minPrimary, primary);
                samples.maxPrimary = Math.max(samples.maxPrimary, primary);

                let completedRep = false;
                const isActive = exerciseStateRef.current === 'active' && visibility >= 0.55;

                if (isActive && activeSpec.kind === 'rep') {
                  if (activeSpec.direction === 'flexion') {
                    if (primary < activeSpec.enterAngle && phaseRef.current === 'up') phaseRef.current = 'down';
                    if (primary > activeSpec.exitAngle && phaseRef.current === 'down') {
                      phaseRef.current = 'up';
                      samples.reps += 1;
                      completedRep = true;
                    }
                  } else {
                    if (primary > activeSpec.enterAngle && phaseRef.current === 'down') phaseRef.current = 'up';
                    if (primary < activeSpec.exitAngle && phaseRef.current === 'up') {
                      phaseRef.current = 'down';
                      samples.reps += 1;
                      completedRep = true;
                    }
                  }
                  if (completedRep) {
                    setRepPulse(samples.reps);
                    const completedCount = samples.reps;
                    window.setTimeout(() => setRepPulse((current) => (current === completedCount ? 0 : current)), 650);
                  }
                }

                if (isActive && activeSpec.kind === 'hold') {
                  const now = performance.now();
                  const delta = holdTickRef.current === null ? 0 : (now - holdTickRef.current) / 1000;
                  holdTickRef.current = now;
                  if (alignment <= activeSpec.alignGood) samples.hold += delta;
                } else {
                  holdTickRef.current = null;
                }

                if (samples.count % 4 === 0 || completedRep) {
                  const nextMetrics: ExercisePoseMetrics = {
                    reps: samples.reps,
                    primary_angle: Math.round(primary),
                    min_primary_angle: Math.round(samples.minPrimary),
                    max_primary_angle: Math.round(samples.maxPrimary),
                    symmetry_gap: Math.round((samples.symmetry / samples.count) * 10) / 10,
                    alignment_deviation: Math.round((samples.align / samples.count) * 10) / 10,
                    visibility: Math.round(visibility * 100) / 100,
                    hold_seconds: Math.round(samples.hold * 10) / 10,
                  };
                  setMetrics(nextMetrics);

                  if (completedRep) {
                    emitExerciseEvent({
                      type: 'exercise_progress',
                      body_visible: true,
                      reps: nextMetrics.reps,
                      pose_metrics: nextMetrics,
                      cue: `Completed ${activeSpec.title} rep ${nextMetrics.reps} of ${activeSpec.kind === 'rep' ? activeSpec.targetReps : goal}.`,
                    });
                  }

                  if (visibility < 0.55) {
                    setLiveCue('Step back so your working joints stay visible.');
                    setCueTone('attention');
                  } else if (exerciseStateRef.current === 'setup') {
                    setLiveCue('Body locked. The skeleton will track your form.');
                    setCueTone('good');
                  } else if (exerciseStateRef.current === 'active') {
                    if (activeSpec.kind === 'hold') {
                      if (alignment > activeSpec.cues.alignMax) {
                        setLiveCue(activeSpec.cues.align);
                        setCueTone('attention');
                      } else {
                        setLiveCue(activeSpec.cues.hold);
                        setCueTone('good');
                      }
                    } else {
                      const direction = primary < previousPrimaryRef.current - 1.5
                        ? 'down'
                        : primary > previousPrimaryRef.current + 1.5 ? 'up' : 'hold';
                      if (symmetry > activeSpec.cues.symMax) {
                        setLiveCue(activeSpec.cues.symmetry);
                        setCueTone('attention');
                      } else if (alignment > activeSpec.cues.alignMax) {
                        setLiveCue(activeSpec.cues.align);
                        setCueTone('attention');
                      } else if (phaseRef.current === 'down') {
                        setLiveCue(activeSpec.cues.deep);
                        setCueTone('good');
                      } else if (direction === 'down') {
                        setLiveCue(activeSpec.cues.descend);
                        setCueTone('good');
                      } else if (direction === 'up') {
                        setLiveCue(activeSpec.cues.ascend);
                        setCueTone('good');
                      } else {
                        setLiveCue('Reset to your start position for the next rep.');
                        setCueTone('neutral');
                      }
                    }
                  }
                }
                previousPrimaryRef.current = primary;
              } else {
                setLiveCue('Move into view so the skeleton can find your joints.');
                setCueTone('attention');
              }
            }
          }
          animationRef.current = requestAnimationFrame(track);
        };
        track();
      } catch {
        if (!disposed) setModelState('error');
      }
    }

    void loadAndTrack();
    return () => {
      disposed = true;
      if (animationRef.current !== null) cancelAnimationFrame(animationRef.current);
    };
  }, [active, emitExerciseEvent, goal, videoElement]);

  const analyze = useCallback(async () => {
    if (!videoElement || videoElement.readyState < 2 || analyzing) return;
    setAnalyzing(true);
    setExerciseState('analyzing');
    setAnalysis(null);
    try {
      const frame = document.createElement('canvas');
      const width = 640;
      const height = Math.round(width * (videoElement.videoHeight / videoElement.videoWidth || 9 / 16));
      frame.width = width;
      frame.height = height;
      frame.getContext('2d')?.drawImage(videoElement, 0, 0, width, height);
      const response = await fetch(`${API_BASE}/api/mirror/movement/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_name: roomName ?? roomRef.current,
          movement: exercise,
          image_data_url: frame.toDataURL('image/jpeg', 0.72),
          pose_metrics: metrics,
        }),
      });
      if (!response.ok) throw new Error('Movement analysis failed');
      const body = await response.json() as {
        analysis: ExerciseAnalysis;
        adaptation?: ExerciseAdaptation;
        persisted: boolean;
      };
      setAnalysis(body.analysis);
      setAdaptation(body.adaptation ?? null);
      setPersisted(body.persisted);
      emitExerciseEvent({
        type: 'exercise_completed',
        body_visible: metrics.visibility >= 0.55,
        reps: metrics.reps,
        pose_metrics: metrics,
        analysis: body.analysis,
        adaptation: body.adaptation,
        cue: body.analysis.cues[0] ?? body.analysis.summary,
      });
    } catch {
      const unavailableAnalysis: ExerciseAnalysis = {
        score: 0,
        headline: 'Analysis unavailable',
        summary: 'Keep the camera on and make sure your full body is visible before trying again.',
        cues: ['Step back until your working joints are visible.'],
        confidence: 0,
        source: 'error',
      };
      setAnalysis(unavailableAnalysis);
      setAdaptation(null);
      emitExerciseEvent({
        type: 'exercise_completed',
        body_visible: false,
        reps: metrics.reps,
        pose_metrics: metrics,
        analysis: unavailableAnalysis,
        cue: unavailableAnalysis.cues[0],
      });
    } finally {
      setAnalyzing(false);
      setExerciseState('complete');
    }
  }, [analyzing, emitExerciseEvent, exercise, metrics, roomName, videoElement]);

  useEffect(() => {
    if (exerciseState !== 'active' || progress < goal || analyzing || analysis) return;
    exerciseStateRef.current = 'analyzing';
    setLiveCue('Set complete. Building your movement score.');
    setCueTone('good');
    const timer = window.setTimeout(() => void analyze(), 650);
    return () => window.clearTimeout(timer);
  }, [analysis, analyze, analyzing, exerciseState, goal, progress]);

  const beginSession = useCallback((trigger: 'agent' | 'manual' = 'manual') => {
    clearMeasurements();
    setAnalysis(null);
    setAdaptation(null);
    setPersisted(false);
    setCountdown(3);
    setExerciseState('countdown');
    setLiveCue('Get ready. Move into your start position.');
    setCueTone('neutral');
    if (trigger === 'agent') setLiveCue('Nova started your set. Get ready.');
  }, [clearMeasurements]);

  useEffect(() => {
    if (
      !active
      || !autoStartRequestId
      || autoStartedRequestRef.current === autoStartRequestId
      || exerciseState !== 'setup'
      || !bodyLocked
    ) return;
    autoStartedRequestRef.current = autoStartRequestId;
    beginSession('agent');
  }, [active, autoStartRequestId, beginSession, bodyLocked, exerciseState]);

  const restartSession = () => {
    reset();
    emitExerciseEvent({
      type: 'exercise_reset',
      body_visible: bodyLocked,
      reps: 0,
      cue: 'Exercise reset. Waiting to begin again.',
    });
  };

  const closeSession = () => {
    emitExerciseEvent({
      type: 'exercise_closed',
      body_visible: bodyLocked,
      reps: metrics.reps,
      cue: 'Exercise session closed.',
    });
    onClose();
  };

  if (!active) return null;

  const symmetryScore = Math.max(0, Math.round(100 - metrics.symmetry_gap * 3));
  const isHold = spec.kind === 'hold';
  const achievedAngle = spec.kind === 'rep' && spec.direction === 'extension'
    ? metrics.max_primary_angle
    : metrics.min_primary_angle;
  const depthLabel = spec.kind === 'rep' ? spec.depthLabel(achievedAngle) : '—';
  const holdSecondsDisplay = Math.floor(metrics.hold_seconds ?? 0);
  const minReps = isHold ? goal : Math.min(3, goal);

  return (
    <div className="mirror-movement-layer" data-exercise-state={exerciseState}>
      <canvas ref={canvasRef} className="mirror-pose-canvas" aria-hidden="true" />
      <motion.div className="mirror-scan-line" initial={{ opacity: 0 }} animate={{ opacity: 1 }} />

      <AnimatePresence mode="popLayout">
        {exerciseState === 'active' && !isHold && repPulse > 0 && (
          <motion.div
            key={repPulse}
            className="mirror-rep-flash"
            initial={{ opacity: 0, scale: 0.55 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.3 }}
            transition={{ duration: 0.32 }}
          >
            <strong>{repPulse}</strong><span>of {goal}</span>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.section
        className="mirror-movement-hud"
        initial={{ opacity: 0, y: -14 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="mirror-movement-hud__topline">
          <span><ScanLine size={15} /> Guided exercise</span>
          <button type="button" onClick={closeSession} aria-label="Close exercise session"><X size={15} /></button>
        </div>
        <div className="mirror-movement-hud__status" data-state={modelState}>
          {modelState === 'loading' && <><LoaderCircle size={14} className="mirror-spin" /> Loading body tracking</>}
          {modelState === 'tracking' && <><i /> {bodyLocked ? 'Full body tracked' : 'Move your full body into frame'}</>}
          {modelState === 'error' && <>Body tracking unavailable</>}
        </div>

        <div className="mirror-exercise-title">
          <span>{spec.subtitle}</span>
          <h1>{spec.title}</h1>
          <p>{spec.tempo}</p>
        </div>

        {exerciseState === 'setup' && (
          <div className="mirror-exercise-setup">
            <div className="mirror-skeleton-key">
              <Eye size={18} />
              <div><strong>What does the skeleton do?</strong><span>It tracks your joints to {isHold ? 'time your hold and check alignment' : 'count complete reps and measure depth, balance, and control'}.</span></div>
            </div>
            <div className="mirror-live-cue" data-tone={cueTone}>{liveCue}</div>
            <button
              type="button"
              className="mirror-exercise-primary"
              disabled={!bodyLocked}
              onClick={() => beginSession('manual')}
            >
              <Play size={16} fill="currentColor" /> {isHold ? `Start ${goal}s hold` : `Start ${goal}-rep set`}
            </button>
          </div>
        )}

        {exerciseState === 'countdown' && (
          <div className="mirror-exercise-countdown" aria-live="assertive">
            <motion.strong key={countdown} initial={{ scale: 0.45, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>{countdown}</motion.strong>
            <span>Brace your core · move into position</span>
          </div>
        )}

        {exerciseState === 'active' && (
          <div className="mirror-exercise-active">
            <div className="mirror-live-cue" data-tone={cueTone}>{liveCue}</div>
            {isHold ? (
              <div className="mirror-movement-grid">
                <span><small>Hold</small><strong>{holdSecondsDisplay}<em>/{goal}s</em></strong></span>
                <span><small>Alignment</small><strong>{Math.max(0, Math.round(100 - metrics.alignment_deviation * 4))}</strong></span>
                <span><small>Tracking</small><strong>{bodyLocked ? 'Locked' : '—'}</strong></span>
              </div>
            ) : (
              <>
                <div className="mirror-rep-progress" aria-label={`${metrics.reps} of ${goal} repetitions complete`}>
                  {Array.from({ length: goal }, (_, index) => <i key={index} data-complete={index < metrics.reps} />)}
                </div>
                <div className="mirror-movement-grid">
                  <span><small>Reps</small><strong>{metrics.reps}<em>/{goal}</em></strong></span>
                  <span><small>{spec.primaryLabel}</small><strong>{depthLabel}</strong></span>
                  <span><small>Balance</small><strong>{symmetryScore}</strong></span>
                </div>
              </>
            )}
            <div className="mirror-exercise-actions">
              <button type="button" className="mirror-movement-reset" onClick={restartSession}><RotateCcw size={14} /> Restart</button>
              <button
                type="button"
                className="mirror-movement-analyze"
                disabled={progress < minReps || analyzing}
                onClick={() => void analyze()}
              >
                <Flag size={14} /> Finish {isHold ? 'hold' : 'early'}
              </button>
            </div>
          </div>
        )}

        {exerciseState === 'analyzing' && (
          <div className="mirror-exercise-analyzing">
            <LoaderCircle size={28} className="mirror-spin" />
            <strong>Set complete</strong>
            <span>Comparing your form against the coaching rubric…</span>
          </div>
        )}

        {exerciseState === 'complete' && (
          <div className="mirror-exercise-complete">
            <Check size={20} />
            <div className="mirror-exercise-complete__copy"><strong>Exercise complete</strong><span>Your movement result is ready.</span></div>
            <div className="mirror-exercise-complete__actions">
              <button type="button" onClick={restartSession}><RotateCcw size={14} /> Try again</button>
              <button type="button" onClick={closeSession}>Back to workout <ChevronRight size={14} /></button>
            </div>
          </div>
        )}
      </motion.section>

      <AnimatePresence>
        {analysis && (
          <motion.section
            className="mirror-movement-result"
            initial={{ opacity: 0, x: 18, scale: 0.96 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 18 }}
          >
            <div className="mirror-movement-score"><strong>{analysis.score}</strong><small>/100</small></div>
            <div>
              <span>{persisted && <Check size={13} />} {analysis.source.includes('realtime') || analysis.source.includes('gpt') ? 'GPT Realtime vision' : 'Pose analysis'}</span>
              <h2>{analysis.headline}</h2>
              <p>{analysis.summary}</p>
              <ul>{analysis.cues.map((cue) => <li key={cue}>{cue}</li>)}</ul>
              {adaptation && (
                <div className="mirror-movement-adaptation" data-source={adaptation.source}>
                  <span><Sparkles size={13} /> {adaptation.source === 'lyzr' ? 'Lyzr next move' : 'Safe next move'}</span>
                  <strong>{adaptation.message}</strong>
                  <small>{adaptation.reason}</small>
                </div>
              )}
            </div>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  );
}
