import type { NormalizedLandmark, PoseLandmarker } from '@mediapipe/tasks-vision';
import { AnimatePresence, motion } from 'motion/react';
import { Check, LoaderCircle, RotateCcw, ScanLine, Sparkles, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

const API_BASE = (import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE_URL ?? '')).replace(/\/$/, '');
const WASM_ROOT = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm';
const MODEL_PATH = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task';

interface PoseMetrics {
  reps: number;
  current_knee_angle: number;
  min_knee_angle: number;
  symmetry_gap: number;
  torso_lean: number;
  visibility: number;
}

interface MovementAnalysis {
  score: number;
  headline: string;
  summary: string;
  cues: string[];
  confidence: number;
  source: string;
}

interface MovementCoachProps {
  active: boolean;
  videoElement: HTMLVideoElement | null;
  roomName?: string;
  onClose: () => void;
}

const initialMetrics: PoseMetrics = {
  reps: 0,
  current_knee_angle: 180,
  min_knee_angle: 180,
  symmetry_gap: 0,
  torso_lean: 0,
  visibility: 0,
};

function angle(first: NormalizedLandmark, middle: NormalizedLandmark, last: NormalizedLandmark) {
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

function speakFeedback(analysis: MovementAnalysis) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(`${analysis.headline}. ${analysis.cues[0] ?? analysis.summary}`);
  utterance.rate = 1.02;
  utterance.pitch = 0.94;
  window.speechSynthesis.speak(utterance);
}

export function MovementCoach({ active, videoElement, roomName, onClose }: MovementCoachProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const landmarkerRef = useRef<PoseLandmarker | null>(null);
  const visionModuleRef = useRef<typeof import('@mediapipe/tasks-vision') | null>(null);
  const animationRef = useRef<number | null>(null);
  const lastVideoTimeRef = useRef(-1);
  const phaseRef = useRef<'standing' | 'bottom'>('standing');
  const samplesRef = useRef({ count: 0, symmetry: 0, torso: 0, minKnee: 180, reps: 0 });
  const roomRef = useRef(`movement-${crypto.randomUUID()}`);
  const [metrics, setMetrics] = useState<PoseMetrics>(initialMetrics);
  const [modelState, setModelState] = useState<'idle' | 'loading' | 'tracking' | 'error'>('idle');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<MovementAnalysis | null>(null);
  const [persisted, setPersisted] = useState(false);

  const reset = useCallback(() => {
    samplesRef.current = { count: 0, symmetry: 0, torso: 0, minKnee: 180, reps: 0 };
    phaseRef.current = 'standing';
    setMetrics(initialMetrics);
    setAnalysis(null);
    setPersisted(false);
  }, []);

  useEffect(() => {
    if (!active) return;
    reset();
  }, [active, reset]);

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
                const drawing = new visionModuleRef.current.DrawingUtils(context);
                drawing.drawConnectors(landmarks, visionModuleRef.current.PoseLandmarker.POSE_CONNECTIONS, {
                  color: '#c9ff3d',
                  lineWidth: 4,
                });
                drawing.drawLandmarks(landmarks, {
                  color: '#f6f5ef',
                  fillColor: '#101510',
                  lineWidth: 2,
                  radius: 4,
                });

                const leftKnee = angle(landmarks[23], landmarks[25], landmarks[27]);
                const rightKnee = angle(landmarks[24], landmarks[26], landmarks[28]);
                const kneeAngle = (leftKnee + rightKnee) / 2;
                const symmetry = Math.abs(leftKnee - rightKnee);
                const shoulders = midpoint(landmarks[11], landmarks[12]);
                const hips = midpoint(landmarks[23], landmarks[24]);
                const torsoLean = Math.atan2(Math.abs(shoulders.x - hips.x), Math.abs(shoulders.y - hips.y)) * (180 / Math.PI);
                const visibility = [11, 12, 23, 24, 25, 26, 27, 28]
                  .reduce((total, index) => total + (landmarks[index].visibility ?? 0), 0) / 8;
                const samples = samplesRef.current;
                samples.count += 1;
                samples.symmetry += symmetry;
                samples.torso += torsoLean;
                samples.minKnee = Math.min(samples.minKnee, kneeAngle);
                if (kneeAngle < 118 && phaseRef.current === 'standing') phaseRef.current = 'bottom';
                if (kneeAngle > 154 && phaseRef.current === 'bottom') {
                  phaseRef.current = 'standing';
                  samples.reps += 1;
                }
                if (samples.count % 4 === 0) {
                  setMetrics({
                    reps: samples.reps,
                    current_knee_angle: Math.round(kneeAngle),
                    min_knee_angle: Math.round(samples.minKnee),
                    symmetry_gap: Math.round((samples.symmetry / samples.count) * 10) / 10,
                    torso_lean: Math.round((samples.torso / samples.count) * 10) / 10,
                    visibility: Math.round(visibility * 100) / 100,
                  });
                }
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
  }, [active, videoElement]);

  const analyze = useCallback(async () => {
    if (!videoElement || videoElement.readyState < 2 || analyzing) return;
    setAnalyzing(true);
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
          movement: 'squat',
          image_data_url: frame.toDataURL('image/jpeg', 0.72),
          pose_metrics: metrics,
        }),
      });
      if (!response.ok) throw new Error('Movement analysis failed');
      const body = await response.json() as { analysis: MovementAnalysis; persisted: boolean };
      setAnalysis(body.analysis);
      setPersisted(body.persisted);
      speakFeedback(body.analysis);
    } catch {
      setAnalysis({
        score: 0,
        headline: 'Analysis unavailable',
        summary: 'Keep the camera on and make sure your full body is visible before trying again.',
        cues: ['Step back until your shoulders, hips, knees, and ankles are visible.'],
        confidence: 0,
        source: 'error',
      });
    } finally {
      setAnalyzing(false);
    }
  }, [analyzing, metrics, roomName, videoElement]);

  if (!active) return null;

  return (
    <div className="mirror-movement-layer">
      <canvas ref={canvasRef} className="mirror-pose-canvas" aria-hidden="true" />
      <motion.div className="mirror-scan-line" initial={{ opacity: 0 }} animate={{ opacity: 1 }} />
      <motion.section
        className="mirror-movement-hud"
        initial={{ opacity: 0, y: -14 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="mirror-movement-hud__topline">
          <span><ScanLine size={15} /> AI movement screen</span>
          <button type="button" onClick={onClose} aria-label="Close movement screen"><X size={15} /></button>
        </div>
        <div className="mirror-movement-hud__status" data-state={modelState}>
          {modelState === 'loading' && <><LoaderCircle size={14} className="mirror-spin" /> Loading pose model</>}
          {modelState === 'tracking' && <><i /> {metrics.visibility > 0.55 ? 'Body locked' : 'Step back into frame'}</>}
          {modelState === 'error' && <>Pose model unavailable</>}
        </div>
        <div className="mirror-movement-grid">
          <span><small>Reps</small><strong>{metrics.reps}<em>/3</em></strong></span>
          <span><small>Knee angle</small><strong>{metrics.current_knee_angle}°</strong></span>
          <span><small>Symmetry</small><strong>{Math.max(0, Math.round(100 - metrics.symmetry_gap * 3))}</strong></span>
        </div>
        <p>Perform three controlled squats with your full body visible.</p>
        <div className="mirror-movement-actions">
          <button type="button" className="mirror-movement-reset" onClick={reset}><RotateCcw size={14} /> Reset</button>
          <button
            type="button"
            className="mirror-movement-analyze"
            disabled={modelState !== 'tracking' || metrics.visibility < 0.45 || analyzing}
            onClick={() => void analyze()}
          >
            {analyzing ? <LoaderCircle size={15} className="mirror-spin" /> : <Sparkles size={15} />}
            {analyzing ? 'Reading movement' : metrics.reps >= 3 ? 'Analyze three reps' : 'Analyze snapshot'}
          </button>
        </div>
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
              <span>{persisted && <Check size={13} />} {analysis.source.includes('realtime') ? 'GPT Realtime vision' : 'Pose analysis'}</span>
              <h2>{analysis.headline}</h2>
              <p>{analysis.summary}</p>
              <ul>{analysis.cues.map((cue) => <li key={cue}>{cue}</li>)}</ul>
            </div>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  );
}
