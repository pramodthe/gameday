import {
  DisconnectButton,
  LiveKitRoom,
  RoomAudioRenderer,
  TrackToggle,
  VideoTrack,
  useRoomContext,
  useTracks,
} from '@livekit/components-react';
import { Camera, LogOut, Mic } from 'lucide-react';
import { RoomEvent, Track } from 'livekit-client';
import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import type { LiveMirrorConfig, LiveMirrorEvent } from './types';

interface LiveKitCameraBackdropProps {
  config: LiveMirrorConfig;
  onConnected: () => void;
  onDisconnected: () => void;
  onEvent: (event: LiveMirrorEvent) => void;
  onVideoElementChange?: (video: HTMLVideoElement | null) => void;
}

function LocalCamera({ onVideoElementChange }: { onVideoElementChange?: (video: HTMLVideoElement | null) => void }) {
  const tracks = useTracks([Track.Source.Camera], { onlySubscribed: false });
  const localCamera = tracks.find((track) => track.participant.isLocal);

  if (!localCamera) return <div className="mirror-camera mirror-camera--waiting" />;
  return <VideoTrack ref={onVideoElementChange} trackRef={localCamera} className="mirror-livekit-video" />;
}

function MirrorDataReceiver({ onEvent }: { onEvent: (event: LiveMirrorEvent) => void }) {
  const room = useRoomContext();

  useEffect(() => {
    const handleData = (payload: Uint8Array, _participant: unknown, _kind: unknown, topic?: string) => {
      if (topic !== 'mirror-events') return;
      try {
        onEvent(JSON.parse(new TextDecoder().decode(payload)) as LiveMirrorEvent);
      } catch {
        onEvent({ type: 'recoverable_error', message: 'A live update could not be read.' });
      }
    };
    room.on(RoomEvent.DataReceived, handleData);
    return () => {
      room.off(RoomEvent.DataReceived, handleData);
    };
  }, [onEvent, room]);

  return null;
}

function LiveControls() {
  return createPortal(
    <div className="mirror-live-controls" aria-label="Live session controls">
      <TrackToggle source={Track.Source.Microphone} showIcon={false} aria-label="Toggle microphone">
        <Mic size={17} />
      </TrackToggle>
      <TrackToggle source={Track.Source.Camera} showIcon={false} aria-label="Toggle camera">
        <Camera size={17} />
      </TrackToggle>
      <DisconnectButton stopTracks aria-label="Leave check-in">
        <LogOut size={17} />
      </DisconnectButton>
    </div>,
    document.body,
  );
}

export function LiveKitCameraBackdrop({ config, onConnected, onDisconnected, onEvent, onVideoElementChange }: LiveKitCameraBackdropProps) {
  if (!config.token || !config.serverUrl) return null;

  return (
    <LiveKitRoom
      token={config.token}
      serverUrl={config.serverUrl}
      connect
      audio
      video
      onConnected={onConnected}
      onDisconnected={onDisconnected}
      className="mirror-livekit-room"
    >
      <LocalCamera onVideoElementChange={onVideoElementChange} />
      <RoomAudioRenderer />
      <MirrorDataReceiver onEvent={onEvent} />
      <LiveControls />
    </LiveKitRoom>
  );
}
