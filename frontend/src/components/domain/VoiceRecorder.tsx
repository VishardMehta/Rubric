import { Button } from "../primitives";
import { AudioLevelMeter } from "./AudioLevelMeter";
import { MicrophoneBlocked } from "./MicrophoneBlocked";
import { useAudioRecorder } from "../../hooks/useAudioRecorder";
import type { AudioRecording } from "../../hooks/useAudioRecorder";
import {
  NO_INPUT_WARNING_MS,
  SHORT_RECORDING_SECONDS,
} from "../../lib/heuristics";
import "./domain.css";

interface VoiceRecorderProps {
  /** Fires whenever the take changes, including back to null on re-record,
   *  so the parent's submit button can track whether a recording exists. */
  onChange: (recording: AudioRecording | null) => void;
  disabled?: boolean;
}

/**
 * The application screen's recorder. screens.md section 6, "Recorder
 * states": idle, permission pending, permission denied, recording,
 * recorded.
 *
 * The interview does not use this component. It drives the same
 * `useAudioRecorder` hook directly, because its recorder has no idle state
 * at all - recording starts on its own and the only control is `Done
 * answering`. Sharing the engine and not the interface keeps both honest.
 */
export function VoiceRecorder({ onChange, disabled = false }: VoiceRecorderProps) {
  const recorder = useAudioRecorder();

  async function handleStart() {
    onChange(null);
    await recorder.start();
  }

  async function handleStop() {
    const take = await recorder.stop();
    onChange(take);
  }

  function handleReRecord() {
    recorder.reset();
    onChange(null);
  }

  if (recorder.status === "denied") return <MicrophoneBlocked />;

  if (recorder.status === "unsupported") {
    return (
      <div className="rb-recorder">
        <p className="rb-recorder__caption">
          This browser cannot record audio. Open this page in Chrome, Safari or
          Edge and it will work.
        </p>
      </div>
    );
  }

  if (recorder.status === "recording") {
    const noInput = !recorder.heardSound && recorder.silentMs >= NO_INPUT_WARNING_MS;
    return (
      <div className="rb-recorder">
        <div className="rb-recorder__row">
          <span className="rb-live-dot rb-live-dot--on" aria-hidden="true" />
          <span className="text-mono rb-recorder__timer">
            {formatElapsed(recorder.elapsedSeconds)}
          </span>
          <AudioLevelMeter analyser={recorder.analyser} active width={200} />
        </div>
        <p
          className={`rb-recorder__caption${
            noInput ? " rb-recorder__caption--caution" : ""
          }`}
          aria-live="polite"
        >
          {noInput ? "We are not picking up any sound" : "Recording"}
        </p>
        <Button level="primary" onClick={handleStop}>
          Stop recording
        </Button>
      </div>
    );
  }

  if (recorder.status === "recorded" && recorder.recording) {
    const seconds = recorder.recording.seconds;
    return (
      <div className="rb-recorder">
        {/* A real audio element, not a custom play button with no keyboard
            support (design-system.md section 19). */}
        <audio
          className="rb-recorder__player"
          src={recorder.recording.url}
          controls
          preload="metadata"
        />
        <p className="rb-recorder__caption">
          {seconds < SHORT_RECORDING_SECONDS
            ? "That is quite short. Longer introductions score more reliably."
            : `Recorded ${formatElapsed(seconds)}`}
        </p>
        <Button onClick={handleReRecord} disabled={disabled}>
          Record again
        </Button>
      </div>
    );
  }

  // Idle, and permission-pending, which is the same layout with the
  // control disabled and the caption changed.
  const pending = recorder.status === "requesting";
  return (
    <div className="rb-recorder">
      <Button
        level="primary"
        size="large"
        onClick={handleStart}
        disabled={disabled || pending}
        loading={pending}
      >
        Record
      </Button>
      <p className="rb-recorder__caption" aria-live="polite">
        {pending
          ? "Waiting for microphone access"
          : "Your browser will ask for microphone access."}
      </p>
    </div>
  );
}

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}
