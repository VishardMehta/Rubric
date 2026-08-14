import { useCallback, useEffect, useRef, useState } from "react";
import {
  ANALYSER_FFT_SIZE,
  LEVEL_SAMPLE_INTERVAL_MS,
  MAX_RECORDING_SECONDS,
  METER_GAIN,
  SILENCE_RMS_THRESHOLD,
} from "../lib/heuristics";

/*
 * Microphone capture for both candidate surfaces.
 *
 * One `getUserMedia` stream is acquired and held. The interview keeps the
 * microphone open for its whole duration (screens.md section 7 tells the
 * candidate exactly that), so re-requesting per question would churn the
 * device and, in some browsers, re-prompt.
 *
 * The same stream feeds two consumers:
 *   - MediaRecorder, which produces the blob that gets uploaded
 *   - an AnalyserNode, which drives the level meter
 *
 * The meter reads the AnalyserNode directly every animation frame. This
 * hook samples it far more slowly, only to decide whether the caption
 * should say anything about silence - see design-system.md section 18: the
 * meter is instrumentation, not decoration, and nothing here simulates a
 * waveform.
 */

export type RecorderStatus =
  | "idle" // no permission requested yet
  | "requesting" // browser prompt is open
  | "denied" // permission refused, or no device
  | "unsupported" // browser has no MediaRecorder
  | "ready" // permission granted, not recording
  | "recording"
  | "recorded"; // a take exists

export interface AudioRecording {
  blob: Blob;
  url: string;
  seconds: number;
}

/**
 * Chrome records webm/opus, Safari records mp4. Both are sent straight
 * through to transcription, which infers the container from the extension,
 * so the only job here is to pick something the browser will actually
 * produce. Returning undefined lets the browser choose its own default,
 * which is the correct fallback rather than forcing an unsupported type.
 */
function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return candidates.find((type) => MediaRecorder.isTypeSupported?.(type));
}

export function useAudioRecorder() {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [recording, setRecording] = useState<AudioRecording | null>(null);

  /** Milliseconds of continuous silence. Reset by any sound above the
   *  threshold; -1 while not recording. */
  const [silentMs, setSilentMs] = useState(-1);
  /** Whether this take has heard speech at all. Distinguishes "your mic is
   *  not working" from "you paused to think". */
  const [heardSound, setHeardSound] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const objectUrlRef = useRef<string | null>(null);

  /** Resolves with the finished take, so a caller can `await stop()`. */
  const stopResolveRef = useRef<((take: AudioRecording | null) => void) | null>(null);

  const releaseObjectUrl = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  /** Opens the microphone. Safe to call repeatedly; the stream is reused. */
  const requestPermission = useCallback(async (): Promise<boolean> => {
    if (streamRef.current) return true;
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setStatus("unsupported");
      return false;
    }

    setStatus("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          // The browser's own cleanup is better than anything done after
          // the fact, and a cleaner signal transcribes more accurately.
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const context = new AudioContext();
      const analyser = context.createAnalyser();
      analyser.fftSize = ANALYSER_FFT_SIZE;
      // Smoothing is for the drawn bars, not the silence maths. A little
      // makes the meter read as a level rather than as noise.
      analyser.smoothingTimeConstant = 0.75;
      context.createMediaStreamSource(stream).connect(analyser);
      // Deliberately not connected to context.destination: routing the
      // microphone to the speakers would feed back into it.

      audioContextRef.current = context;
      analyserRef.current = analyser;
      setStatus("ready");
      return true;
    } catch {
      // Refused, dismissed, or no input device. All three leave the
      // candidate in the same place and get the same recovery block.
      setStatus("denied");
      return false;
    }
  }, []);

  const start = useCallback(async (): Promise<boolean> => {
    const ok = await requestPermission();
    if (!ok || !streamRef.current) return false;

    // An AudioContext created before a user gesture starts suspended, and
    // a suspended context reports a flat zero level forever.
    if (audioContextRef.current?.state === "suspended") {
      await audioContextRef.current.resume();
    }

    releaseObjectUrl();
    setRecording(null);
    chunksRef.current = [];
    setHeardSound(false);
    setSilentMs(0);
    setElapsedSeconds(0);

    const mimeType = pickMimeType();
    const recorder = new MediaRecorder(
      streamRef.current,
      mimeType ? { mimeType } : undefined,
    );

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };

    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, {
        type: recorder.mimeType || mimeType || "audio/webm",
      });
      const seconds = Math.round((Date.now() - startedAtRef.current) / 1000);
      const take: AudioRecording =
        blob.size > 0
          ? { blob, url: URL.createObjectURL(blob), seconds }
          : { blob, url: "", seconds };
      if (take.url) objectUrlRef.current = take.url;

      setRecording(take);
      setStatus("recorded");
      setSilentMs(-1);
      stopResolveRef.current?.(take);
      stopResolveRef.current = null;
    };

    recorderRef.current = recorder;
    startedAtRef.current = Date.now();
    recorder.start();
    setStatus("recording");
    return true;
  }, [requestPermission, releaseObjectUrl]);

  const stop = useCallback((): Promise<AudioRecording | null> => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") return Promise.resolve(null);
    return new Promise((resolve) => {
      stopResolveRef.current = resolve;
      recorder.stop();
    });
  }, []);

  /** Discards the current take so the same slot can be recorded again. */
  const reset = useCallback(() => {
    releaseObjectUrl();
    setRecording(null);
    setElapsedSeconds(0);
    setSilentMs(-1);
    setHeardSound(false);
    setStatus(streamRef.current ? "ready" : "idle");
  }, [releaseObjectUrl]);

  // Elapsed time and silence tracking. Both only run while recording, and
  // both read the same analyser the meter draws from - there is one source
  // of truth for "is there sound right now".
  useEffect(() => {
    if (status !== "recording") return;

    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAtRef.current) / 1000));

      const analyser = analyserRef.current;
      if (!analyser) return;
      const samples = new Float32Array(analyser.fftSize);
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (const sample of samples) sum += sample * sample;
      const rms = Math.sqrt(sum / samples.length);

      if (rms > SILENCE_RMS_THRESHOLD) {
        setHeardSound(true);
        setSilentMs(0);
      } else {
        setSilentMs((current) => (current < 0 ? 0 : current + LEVEL_SAMPLE_INTERVAL_MS));
      }
    }, LEVEL_SAMPLE_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [status]);

  // A take that runs past the ceiling is stopped rather than left to grow
  // into a file the backend will reject.
  useEffect(() => {
    if (status === "recording" && elapsedSeconds >= MAX_RECORDING_SECONDS) void stop();
  }, [status, elapsedSeconds, stop]);

  // Release the device on unmount. Without this the browser keeps showing
  // a recording indicator after the candidate has left the page.
  useEffect(
    () => () => {
      if (recorderRef.current?.state === "recording") recorderRef.current.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      void audioContextRef.current?.close();
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    },
    [],
  );

  return {
    status,
    elapsedSeconds,
    recording,
    silentMs,
    heardSound,
    analyser: analyserRef,
    requestPermission,
    start,
    stop,
    reset,
  };
}

/** Normalised 0 to 1 level for a single analyser read. Shared by the meter
 *  so the drawn height and the silence logic agree on what "loud" means. */
export function readLevel(analyser: AnalyserNode): number {
  const samples = new Float32Array(analyser.fftSize);
  analyser.getFloatTimeDomainData(samples);
  let sum = 0;
  for (const sample of samples) sum += sample * sample;
  const rms = Math.sqrt(sum / samples.length);
  return Math.min(1, rms * METER_GAIN);
}
