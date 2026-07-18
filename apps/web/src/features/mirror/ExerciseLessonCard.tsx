import { motion } from 'motion/react';
import { ChevronRight, Dumbbell, LoaderCircle, Play, ShieldCheck, Sparkles, Timer, TriangleAlert, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  ExerciseEventPublisher,
  ExerciseLesson,
  ExerciseLessonTelemetryEvent,
  ExerciseMotionPattern,
  TrackedMovement,
} from './types';

const API_BASE = (import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE_URL ?? '')).replace(/\/$/, '');

interface LessonRequest {
  requestId: string;
  exerciseName: string;
  lesson?: ExerciseLesson;
}

interface ExerciseLessonCardProps {
  request: LessonRequest;
  onClose: () => void;
  onPractice: (movement: TrackedMovement) => void;
  onEvent?: (event: Parameters<ExerciseEventPublisher>[0]) => void;
}

type JointName =
  | 'head'
  | 'neck'
  | 'leftShoulder'
  | 'rightShoulder'
  | 'leftElbow'
  | 'rightElbow'
  | 'leftWrist'
  | 'rightWrist'
  | 'leftHip'
  | 'rightHip'
  | 'leftKnee'
  | 'rightKnee'
  | 'leftAnkle'
  | 'rightAnkle';

type Pose = Record<JointName, [number, number]>;

const standingPose: Pose = {
  head: [120, 34], neck: [120, 57],
  leftShoulder: [100, 68], rightShoulder: [140, 68],
  leftElbow: [91, 101], rightElbow: [149, 101],
  leftWrist: [88, 130], rightWrist: [152, 130],
  leftHip: [108, 122], rightHip: [132, 122],
  leftKnee: [106, 165], rightKnee: [134, 165],
  leftAnkle: [104, 211], rightAnkle: [136, 211],
};

const posePairs: Record<ExerciseMotionPattern, [Pose, Pose]> = {
  squat: [standingPose, {
    head: [120, 70], neck: [120, 91],
    leftShoulder: [99, 99], rightShoulder: [141, 99],
    leftElbow: [82, 118], rightElbow: [158, 118],
    leftWrist: [69, 137], rightWrist: [171, 137],
    leftHip: [104, 145], rightHip: [136, 145],
    leftKnee: [81, 173], rightKnee: [159, 173],
    leftAnkle: [73, 211], rightAnkle: [167, 211],
  }],
  lunge: [standingPose, {
    head: [116, 49], neck: [116, 71],
    leftShoulder: [96, 80], rightShoulder: [136, 80],
    leftElbow: [89, 111], rightElbow: [143, 111],
    leftWrist: [95, 135], rightWrist: [137, 135],
    leftHip: [105, 133], rightHip: [129, 133],
    leftKnee: [77, 168], rightKnee: [159, 173],
    leftAnkle: [60, 210], rightAnkle: [184, 210],
  }],
  hinge: [standingPose, {
    head: [77, 74], neck: [91, 90],
    leftShoulder: [79, 101], rightShoulder: [104, 82],
    leftElbow: [102, 120], rightElbow: [123, 106],
    leftWrist: [125, 139], rightWrist: [143, 127],
    leftHip: [126, 132], rightHip: [143, 126],
    leftKnee: [120, 168], rightKnee: [148, 166],
    leftAnkle: [114, 211], rightAnkle: [151, 211],
  }],
  push: [{
    head: [62, 108], neck: [82, 112],
    leftShoulder: [93, 104], rightShoulder: [96, 121],
    leftElbow: [103, 151], rightElbow: [121, 147],
    leftWrist: [118, 193], rightWrist: [139, 193],
    leftHip: [146, 122], rightHip: [149, 137],
    leftKnee: [178, 139], rightKnee: [182, 151],
    leftAnkle: [214, 154], rightAnkle: [217, 166],
  }, {
    head: [66, 151], neck: [87, 151],
    leftShoulder: [98, 143], rightShoulder: [100, 158],
    leftElbow: [86, 171], rightElbow: [110, 180],
    leftWrist: [118, 193], rightWrist: [139, 193],
    leftHip: [151, 151], rightHip: [153, 164],
    leftKnee: [182, 156], rightKnee: [186, 169],
    leftAnkle: [216, 161], rightAnkle: [218, 174],
  }],
  plank: [{
    head: [56, 122], neck: [78, 126],
    leftShoulder: [90, 118], rightShoulder: [91, 135],
    leftElbow: [96, 158], rightElbow: [115, 158],
    leftWrist: [127, 159], rightWrist: [142, 159],
    leftHip: [145, 138], rightHip: [147, 151],
    leftKnee: [179, 147], rightKnee: [181, 159],
    leftAnkle: [216, 153], rightAnkle: [218, 165],
  }, {
    head: [56, 114], neck: [78, 120],
    leftShoulder: [90, 114], rightShoulder: [91, 131],
    leftElbow: [98, 156], rightElbow: [115, 157],
    leftWrist: [128, 158], rightWrist: [143, 159],
    leftHip: [145, 132], rightHip: [147, 145],
    leftKnee: [180, 142], rightKnee: [182, 154],
    leftAnkle: [216, 151], rightAnkle: [218, 163],
  }],
  jump: [standingPose, {
    head: [120, 23], neck: [120, 45],
    leftShoulder: [99, 57], rightShoulder: [141, 57],
    leftElbow: [78, 34], rightElbow: [162, 34],
    leftWrist: [61, 14], rightWrist: [179, 14],
    leftHip: [108, 109], rightHip: [132, 109],
    leftKnee: [87, 150], rightKnee: [153, 150],
    leftAnkle: [68, 190], rightAnkle: [172, 190],
  }],
  stretch: [standingPose, {
    head: [98, 46], neck: [102, 66],
    leftShoulder: [83, 72], rightShoulder: [121, 78],
    leftElbow: [69, 48], rightElbow: [139, 101],
    leftWrist: [58, 24], rightWrist: [151, 127],
    leftHip: [108, 124], rightHip: [132, 126],
    leftKnee: [106, 166], rightKnee: [135, 167],
    leftAnkle: [104, 211], rightAnkle: [137, 211],
  }],
  rotation: [standingPose, {
    ...standingPose,
    leftShoulder: [91, 75], rightShoulder: [135, 61],
    leftElbow: [72, 96], rightElbow: [157, 81],
    leftWrist: [57, 116], rightWrist: [174, 96],
    leftHip: [111, 126], rightHip: [130, 118],
  }],
  pull: [standingPose, {
    ...standingPose,
    leftElbow: [75, 83], rightElbow: [165, 83],
    leftWrist: [99, 76], rightWrist: [141, 76],
  }],
  generic: [standingPose, {
    ...standingPose,
    leftElbow: [78, 86], rightElbow: [162, 86],
    leftWrist: [65, 60], rightWrist: [175, 60],
    leftKnee: [96, 161], rightKnee: [144, 161],
  }],
};

const connectors: Array<[JointName, JointName]> = [
  ['neck', 'leftShoulder'], ['neck', 'rightShoulder'],
  ['leftShoulder', 'leftElbow'], ['leftElbow', 'leftWrist'],
  ['rightShoulder', 'rightElbow'], ['rightElbow', 'rightWrist'],
  ['leftShoulder', 'leftHip'], ['rightShoulder', 'rightHip'],
  ['leftHip', 'rightHip'], ['leftShoulder', 'rightShoulder'],
  ['leftHip', 'leftKnee'], ['leftKnee', 'leftAnkle'],
  ['rightHip', 'rightKnee'], ['rightKnee', 'rightAnkle'],
];

function PoseFigure({ pose, className }: { pose: Pose; className: string }) {
  return (
    <g className={className}>
      {connectors.map(([from, to]) => (
        <line key={`${from}-${to}`} x1={pose[from][0]} y1={pose[from][1]} x2={pose[to][0]} y2={pose[to][1]} />
      ))}
      <line x1={pose.head[0]} y1={pose.head[1] + 10} x2={pose.neck[0]} y2={pose.neck[1]} />
      <circle cx={pose.head[0]} cy={pose.head[1]} r="11" />
      {Object.entries(pose).filter(([name]) => name !== 'head').map(([name, point]) => (
        <circle key={name} cx={point[0]} cy={point[1]} r="3.2" />
      ))}
    </g>
  );
}

function MotionGraphic({ pattern, name }: { pattern: ExerciseMotionPattern; name: string }) {
  const [start, finish] = posePairs[pattern] ?? posePairs.generic;
  return (
    <div className="lesson-motion" data-pattern={pattern}>
      <div className="lesson-motion__labels"><span>01 · Set</span><span>02 · Move</span></div>
      <svg viewBox="0 0 240 235" role="img" aria-label={`Animated movement guide for ${name}`}>
        <defs>
          <linearGradient id="lesson-floor" x1="0" x2="1"><stop stopColor="#c9ff3d" stopOpacity="0" /><stop offset="0.5" stopColor="#c9ff3d" /><stop offset="1" stopColor="#c9ff3d" stopOpacity="0" /></linearGradient>
          <radialGradient id="lesson-glow"><stop stopColor="#c9ff3d" stopOpacity="0.25" /><stop offset="1" stopColor="#c9ff3d" stopOpacity="0" /></radialGradient>
        </defs>
        <ellipse cx="120" cy="120" rx="92" ry="102" fill="url(#lesson-glow)" />
        <path className="lesson-motion__orbit" d="M36 130C54 50 176 29 211 105" />
        <path className="lesson-motion__arrow" d="m207 96 5 10-11 2" />
        <PoseFigure pose={start} className="lesson-pose lesson-pose--start" />
        <PoseFigure pose={finish} className="lesson-pose lesson-pose--finish" />
        <line className="lesson-motion__floor" x1="30" y1="214" x2="210" y2="214" />
      </svg>
      <span className="lesson-motion__pattern">Motion map · {pattern}</span>
    </div>
  );
}

export function ExerciseLessonCard({ request, onClose, onPractice, onEvent }: ExerciseLessonCardProps) {
  const onEventRef = useRef(onEvent);
  const [lesson, setLesson] = useState<ExerciseLesson | null>(request.lesson ?? null);
  const [loading, setLoading] = useState(!request.lesson);
  const [error, setError] = useState('');

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const emitLessonEvent = useCallback((event: Omit<ExerciseLessonTelemetryEvent, 'timestamp' | 'exercise_name' | 'request_id'>) => {
    onEventRef.current?.({
      timestamp: new Date().toISOString(),
      exercise_name: request.exerciseName,
      request_id: request.requestId,
      ...event,
    });
  }, [request.exerciseName, request.requestId]);

  useEffect(() => {
    if (request.lesson) {
      setLesson(request.lesson);
      setLoading(false);
      setError('');
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setLesson(null);
    setError('');
    emitLessonEvent({ type: 'exercise_lesson_loading' });
    fetch(`${API_BASE}/api/mirror/exercise/lesson`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercise_name: request.exerciseName }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Lesson generation failed');
        return response.json() as Promise<{ lesson: ExerciseLesson }>;
      })
      .then(({ lesson: generatedLesson }) => {
        setLesson(generatedLesson);
        emitLessonEvent({
          type: 'exercise_lesson_ready',
          summary: generatedLesson.summary,
          form_cues: generatedLesson.form_cues,
          source: generatedLesson.source,
          lesson: generatedLesson,
        });
      })
      .catch((lessonError: unknown) => {
        if (controller.signal.aborted) return;
        const message = lessonError instanceof Error ? lessonError.message : 'Lesson generation failed';
        setError(message);
        emitLessonEvent({ type: 'exercise_lesson_failed', message });
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [emitLessonEvent, request.exerciseName, request.lesson]);

  const closeLesson = () => {
    emitLessonEvent({ type: 'exercise_lesson_closed' });
    onClose();
  };

  const practiceWithCamera = () => {
    if (!lesson || lesson.camera_support === 'none') return;
    emitLessonEvent({ type: 'exercise_lesson_closed' });
    onPractice(lesson.camera_support);
  };

  return (
    <motion.aside
      className="exercise-lesson-layer"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.section
        className="exercise-lesson-card"
        initial={{ opacity: 0, y: 26, scale: 0.975 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: 'spring', stiffness: 230, damping: 25 }}
        aria-live="polite"
      >
        <header className="exercise-lesson-card__header">
          <span><Sparkles size={15} /> Generative movement lesson</span>
          <button type="button" onClick={closeLesson} aria-label="Close exercise lesson"><X size={17} /></button>
        </header>

        {loading && (
          <div className="exercise-lesson-loading">
            <div><LoaderCircle size={30} className="mirror-spin" /><i /></div>
            <span>Nova is building your visual guide</span>
            <strong>{request.exerciseName}</strong>
          </div>
        )}

        {!loading && error && (
          <div className="exercise-lesson-error">
            <TriangleAlert size={28} />
            <strong>Couldn’t build this lesson</strong>
            <span>{error}</span>
            <button type="button" onClick={closeLesson}>Close</button>
          </div>
        )}

        {lesson && (
          <div className="exercise-lesson-content">
            <div className="exercise-lesson-hero">
              <div className="exercise-lesson-copy">
                <span>{lesson.category} · {lesson.difficulty}</span>
                <h1>{lesson.exercise_name}</h1>
                <p>{lesson.summary}</p>
                <div className="exercise-lesson-chips">
                  {lesson.primary_muscles.map((muscle) => <span key={muscle}>{muscle}</span>)}
                </div>
              </div>
              <MotionGraphic pattern={lesson.motion_pattern} name={lesson.exercise_name} />
            </div>

            <div className="exercise-lesson-prescription">
              <span><Dumbbell size={16} /><small>Prescription</small><strong>{lesson.prescription}</strong></span>
              <span><Timer size={16} /><small>Tempo</small><strong>{lesson.tempo}</strong></span>
            </div>

            <div className="exercise-lesson-grid">
              <section className="exercise-lesson-steps">
                <div className="exercise-lesson-section-title"><span>How to move</span><small>3 steps</small></div>
                {lesson.steps.map((step, index) => (
                  <article key={`${step.phase}-${step.title}`}>
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <div><strong>{step.title}</strong><p>{step.instruction}</p></div>
                  </article>
                ))}
              </section>

              <section className="exercise-lesson-coaching">
                <div className="exercise-lesson-section-title"><span>Coach cues</span><small>Live checklist</small></div>
                <ul>{lesson.form_cues.map((cue) => <li key={cue}><ChevronRight size={13} />{cue}</li>)}</ul>
                <div className="exercise-lesson-avoid">
                  <strong><TriangleAlert size={14} /> Avoid</strong>
                  <span>{lesson.avoid.join(' · ')}</span>
                </div>
                <div className="exercise-lesson-safety"><ShieldCheck size={15} /><span>{lesson.safety_note}</span></div>
              </section>
            </div>

            <footer className="exercise-lesson-footer">
              <span><i /> Generated by {lesson.source.includes('gpt') ? 'OpenAI' : 'GameDay fallback'}</span>
              {lesson.camera_support !== 'none' && (
                <button type="button" onClick={practiceWithCamera}><Play size={15} fill="currentColor" /> Practice with camera</button>
              )}
            </footer>
          </div>
        )}
      </motion.section>
    </motion.aside>
  );
}
