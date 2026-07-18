import {
  LiveKitRoom,
  RoomAudioRenderer,
  TrackToggle,
  VideoTrack,
  useRoomContext,
  useTracks,
} from '@livekit/components-react';
import { Camera, LogOut, Mic } from 'lucide-react';
import { ConnectionState, RoomEvent, Track } from 'livekit-client';
import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import type { AgUiCustomEvent, ExerciseEventPublisher, LiveMirrorConfig, LiveMirrorPayload } from './types';

interface LiveKitCameraBackdropProps {
  config: LiveMirrorConfig;
  onConnected: () => void;
  onDisconnected: () => void;
  onEvent: (event: LiveMirrorPayload) => void;
  controlsHidden?: boolean;
  onExercisePublisherChange?: (publisher: ExerciseEventPublisher | null) => void;
  onVideoElementChange?: (video: HTMLVideoElement | null) => void;
}

function LocalCamera({ onVideoElementChange }: { onVideoElementChange?: (video: HTMLVideoElement | null) => void }) {
  const tracks = useTracks([Track.Source.Camera], { onlySubscribed: false });
  const localCamera = tracks.find((track) => track.participant.isLocal);

  if (!localCamera) return <div className="mirror-camera mirror-camera--waiting" />;
  return <VideoTrack ref={onVideoElementChange} trackRef={localCamera} className="mirror-livekit-video" />;
}

function MirrorDataReceiver({ onEvent }: { onEvent: (event: LiveMirrorPayload) => void }) {
  const room = useRoomContext();

  useEffect(() => {
    const handleData = (payload: Uint8Array, _participant: unknown, _kind: unknown, topic?: string) => {
      if (topic !== 'mirror-events') return;
      try {
        onEvent(JSON.parse(new TextDecoder().decode(payload)) as LiveMirrorPayload);
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

function ExerciseDataPublisher({ onPublisherChange }: { onPublisherChange?: (publisher: ExerciseEventPublisher | null) => void }) {
  const room = useRoomContext();

  useEffect(() => {
    if (!onPublisherChange) return;
    const publish: ExerciseEventPublisher = async (event) => {
      const payload: AgUiCustomEvent = {
        type: 'CUSTOM',
        timestamp: Date.now(),
        name: 'gameday.exercise.telemetry',
        value: event,
      };
      await room.localParticipant.publishData(
        new TextEncoder().encode(JSON.stringify(payload)),
        { reliable: true, topic: 'exercise-events' },
      );
    };
    onPublisherChange(publish);
    const stateRequest: AgUiCustomEvent = {
      type: 'CUSTOM',
      timestamp: Date.now(),
      name: 'gameday.state.request',
      value: { reason: 'client_connected' },
    };
    let disposed = false;
    const requestState = () => {
      if (disposed) return;
      void room.localParticipant.publishData(
        new TextEncoder().encode(JSON.stringify(stateRequest)),
        { reliable: true, topic: 'exercise-events' },
      );
    };
    if (room.state === ConnectionState.Connected) requestState();
    else room.once(RoomEvent.Connected, requestState);
    return () => {
      disposed = true;
      room.off(RoomEvent.Connected, requestState);
      onPublisherChange(null);
    };
  }, [onPublisherChange, room]);

  return null;
}

function LiveControls({ hidden }: { hidden: boolean }) {
  const room = useRoomContext();

  return createPortal(
    <div className="mirror-live-controls" data-hidden={hidden} aria-label="Live session controls">
      <TrackToggle source={Track.Source.Microphone} showIcon={false} aria-label="Toggle microphone">
        <Mic size={17} />
      </TrackToggle>
      <TrackToggle source={Track.Source.Camera} showIcon={false} aria-label="Toggle camera">
        <Camera size={17} />
      </TrackToggle>
      <button type="button" onClick={() => void room.disconnect(true)} aria-label="Leave check-in">
        <LogOut size={17} />
      </button>
    </div>,
    document.body,
  );
}

export function LiveKitCameraBackdrop({
  config,
  onConnected,
  onDisconnected,
  onEvent,
  controlsHidden = false,
  onExercisePublisherChange,
  onVideoElementChange,
}: LiveKitCameraBackdropProps) {
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
      <ExerciseDataPublisher onPublisherChange={onExercisePublisherChange} />
      <LiveControls hidden={controlsHidden} />
    </LiveKitRoom>
  );
}
