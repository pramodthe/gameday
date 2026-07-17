import { useEffect, useRef, useState } from 'react';
import { CameraOff } from 'lucide-react';

interface CameraBackdropProps {
  enabled: boolean;
  onAvailabilityChange?: (available: boolean) => void;
  onVideoElementChange?: (video: HTMLVideoElement | null) => void;
}

export function CameraBackdrop({ enabled, onAvailabilityChange, onVideoElementChange }: CameraBackdropProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    onVideoElementChange?.(videoRef.current);
    return () => onVideoElementChange?.(null);
  }, [onVideoElementChange]);

  useEffect(() => {
    let active = true;
    let stream: MediaStream | null = null;

    async function connectCamera() {
      if (!enabled) {
        setAvailable(false);
        onAvailabilityChange?.(false);
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
          audio: false,
        });
        if (!active) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setAvailable(true);
        onAvailabilityChange?.(true);
      } catch {
        if (!active) return;
        setAvailable(false);
        onAvailabilityChange?.(false);
      }
    }

    void connectCamera();
    return () => {
      active = false;
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [enabled, onAvailabilityChange]);

  return (
    <div className="mirror-camera" data-camera-ready={available}>
      <video ref={videoRef} autoPlay muted playsInline aria-label="Live mirror camera" />
      {!available && (
        <div className="mirror-camera-fallback">
          <div className="mirror-camera-fallback__halo" />
          <CameraOff size={24} />
          <span>Camera unavailable</span>
          <small>The check-in still works without video.</small>
        </div>
      )}
    </div>
  );
}
