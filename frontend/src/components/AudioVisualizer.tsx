import { useEffect, useRef, useState } from "react";

// Multiband bar visualizer in the LiveKit Agents UI aesthetic, driven by a simple
// animated model (taller/livelier when `active`). No LiveKit room required.
export function AudioVisualizer({ active, bars = 28 }: { active: boolean; bars?: number }) {
  const [heights, setHeights] = useState<number[]>(() => Array(bars).fill(0.14));
  const raf = useRef(0);
  const t = useRef(0);

  useEffect(() => {
    const loop = () => {
      t.current += 0.09;
      const amp = active ? 0.5 : 0.08;
      setHeights(
        Array.from({ length: bars }, (_, i) => {
          const wave = Math.sin(t.current + i * 0.5) * 0.6 + Math.sin(t.current * 1.7 + i) * 0.4;
          return Math.min(1, 0.12 + amp * Math.abs(wave));
        }),
      );
      raf.current = requestAnimationFrame(loop);
    };
    raf.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf.current);
  }, [active, bars]);

  return (
    <div className={`viz ${active ? "viz--active" : ""}`}>
      {heights.map((h, i) => (
        <span key={i} className="viz__bar" style={{ height: `${Math.round(h * 100)}%` }} />
      ))}
    </div>
  );
}
