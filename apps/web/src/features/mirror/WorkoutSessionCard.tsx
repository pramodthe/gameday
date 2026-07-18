import { AnimatePresence, motion } from 'motion/react';
import { Brain, Check, Dumbbell, LoaderCircle, Play, RefreshCw, ScanLine, Timer } from 'lucide-react';
import { useState } from 'react';
import type { WorkoutExercise, WorkoutSession } from './types';

interface WorkoutSessionCardProps {
  workout: WorkoutSession | null;
  visible: boolean;
  loading: boolean;
  onStartExercise: (exercise: WorkoutExercise) => void;
  onRebuild: () => void;
}

const intensityLabel: Record<WorkoutSession['intensity'], string> = {
  recovery: 'Recovery',
  moderate: 'Moderate',
  hard: 'Hard',
};

function dose(exercise: WorkoutExercise): string {
  if (exercise.hold_seconds > 0) return `${exercise.sets} × ${exercise.hold_seconds}s hold`;
  return `${exercise.sets} × ${exercise.reps} reps`;
}

export function WorkoutSessionCard({ workout, visible, loading, onStartExercise, onRebuild }: WorkoutSessionCardProps) {
  const [done, setDone] = useState<Record<string, boolean>>({});

  return (
    <AnimatePresence>
      {visible && (
        <motion.section
          className="mirror-workout"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="mirror-workout__head">
            <span className="mirror-workout__eyebrow"><Dumbbell size={15} /> Today’s workout</span>
            <button type="button" className="mirror-workout__rebuild" onClick={onRebuild} disabled={loading}>
              <RefreshCw size={13} className={loading ? 'mirror-spin' : undefined} /> Rebuild
            </button>
          </div>

          {loading && !workout ? (
            <div className="mirror-workout__building">
              <LoaderCircle size={26} className="mirror-spin" />
              <strong>Programming your session…</strong>
              <span>Building a workout tuned to today’s recovery.</span>
            </div>
          ) : workout ? (
            <>
              <div className="mirror-workout__title">
                <h2>{workout.title}</h2>
                <p>{workout.summary}</p>
                <div className="mirror-workout__meta">
                  <span data-intensity={workout.intensity}>{intensityLabel[workout.intensity]}</span>
                  <span><Timer size={13} /> ~{workout.estimated_minutes} min</span>
                  <span>{workout.focus}</span>
                </div>
                <div className="mirror-workout__trace" data-source={workout.source}>
                  <span><Brain size={13} /> {workout.source === 'lyzr' ? 'Lyzr agent workflow' : 'Resilient workflow'}</span>
                  {(workout.decision_trace ?? []).map((step) => <small key={step}>{step}</small>)}
                </div>
              </div>

              <ol className="mirror-workout__list">
                {workout.exercises.map((exercise, index) => (
                  <li key={`${exercise.name}-${index}`} data-done={done[`${exercise.name}-${index}`] ? 'true' : 'false'}>
                    <span className="mirror-workout__index">{String(index + 1).padStart(2, '0')}</span>
                    <div className="mirror-workout__body">
                      <div className="mirror-workout__row">
                        <strong>{exercise.name}</strong>
                        <span className="mirror-workout__camera"><ScanLine size={12} /> camera</span>
                      </div>
                      <span className="mirror-workout__dose">{dose(exercise)} · {exercise.rest_seconds}s rest</span>
                      <span className="mirror-workout__cue">{exercise.coaching_cue}</span>
                    </div>
                    <div className="mirror-workout__actions">
                      <button
                        type="button"
                        className="mirror-workout__start"
                        onClick={() => onStartExercise(exercise)}
                      >
                        <Play size={13} fill="currentColor" /> Start
                      </button>
                      <button
                        type="button"
                        className="mirror-workout__check"
                        aria-label={`Mark ${exercise.name} done`}
                        data-done={done[`${exercise.name}-${index}`] ? 'true' : 'false'}
                        onClick={() => setDone((current) => ({ ...current, [`${exercise.name}-${index}`]: !current[`${exercise.name}-${index}`] }))}
                      >
                        <Check size={14} />
                      </button>
                    </div>
                  </li>
                ))}
              </ol>
            </>
          ) : null}
        </motion.section>
      )}
    </AnimatePresence>
  );
}
