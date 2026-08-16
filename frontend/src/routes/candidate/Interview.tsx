import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "../../components/primitives";
import { ErrorState } from "../../components/feedback";
import { AudioLevelMeter, CameraPreview, MicrophoneBlocked, VoiceOrb } from "../../components/domain";
import type { CameraState } from "../../components/domain";
import type { OrbState } from "../../components/domain";
import { api, ApiError, submitAnswerStreaming } from "../../api/client";
import type { InterviewSession, TurnStage } from "../../api/client";
import { useAudioRecorder } from "../../hooks/useAudioRecorder";
import { speak, speechSupported, stopSpeaking } from "../../lib/speech";
import {
  AUTO_RECORD_DELAY_MS,
  NO_INPUT_WARNING_MS,
  QUESTION_TRANSITION_MS,
  STILL_LISTENING_MS,
  TURN_RETRY_ATTEMPTS,
  TURN_RETRY_BACKOFF_MS,
} from "../../lib/heuristics";
import "./interview.css";

/*
 * screens.md section 7. The most important screen in the product.
 *
 * It answers three questions continuously: am I being heard, how far
 * through am I, what happens next. Nothing is clickable except the single
 * control, and there is no navigation, because there is nowhere to go.
 *
 * This screen owns the full viewport rather than using CandidateShell -
 * even the wordmark is removed.
 */

type Phase =
  | "loading"
  | "invalid" // token is unknown or already used up
  | "ready" // stage 1
  | "question" // stage 2
  | "processing" // stage 3
  | "turn-error" // transcription failed, same slot, re-record
  | "complete";

/** Candidate-facing wording for each backend stage. The backend sends
 *  identifiers; the copy lives here with the rest of the candidate voice.
 *  design-system.md section 15: the system is never a person. */
const STAGE_LABELS: Record<TurnStage, string> = {
  transcribing: "Transcribing your answer",
  preparing: "Preparing the next question",
  reviewing: "Reviewing your interview",
};

const UPLOAD_LABEL = "Uploading your answer";

export function InterviewPage() {
  const { token = "" } = useParams();
  const navigate = useNavigate();

  const [phase, setPhase] = useState<Phase>("loading");
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [slot, setSlot] = useState(1);
  const [question, setQuestion] = useState("");
  /** Kept on screen, dimmed, while the next one is being prepared, so the
   *  screen never goes blank mid-turn (screens.md stage 3). */
  const [previousQuestion, setPreviousQuestion] = useState("");
  const [stageLabel, setStageLabel] = useState(UPLOAD_LABEL);
  const [errorMessage, setErrorMessage] = useState("");
  const [loadFailure, setLoadFailure] = useState<ApiError | null>(null);
  const [speaking, setSpeaking] = useState(false);
  /** Drives the 320ms entrance on a new question (stage 4). */
  const [entering, setEntering] = useState(false);

  const [impulse, setImpulse] = useState(0);
  const [cameraSettled, setCameraSettled] = useState(false);
  // Checked once, before the first question. The interview shows a live
  // picture throughout, so a camera that was never going to work should
  // fail here rather than four questions in.
  const [cameraStatus, setCameraStatus] = useState<CameraState>("loading");
  const settleCamera = useCallback(() => setCameraSettled(true), []);
  // The orb is a canvas with a real pixel size, so a CSS media query
  // cannot shrink it without blurring the backing store. It is measured
  // here and re-created at the right resolution instead.
  const [orbSize, setOrbSize] = useState(() =>
    typeof window !== "undefined" && window.innerWidth < 768 ? 160 : 280,
  );
  useEffect(() => {
    const compact = window.matchMedia("(max-width: 767px)");
    const apply = () => setOrbSize(compact.matches ? 160 : 280);
    apply();
    compact.addEventListener("change", apply);
    return () => compact.removeEventListener("change", apply);
  }, []);

  const recorder = useAudioRecorder();
  const answerStartedAt = useRef(0);
  const autoRecordTimer = useRef(0);

  const total = session?.total_questions ?? 0;

  // --- Loading and resume -------------------------------------------------
  // A refresh mid-interview must land on the question the candidate was
  // actually on, not restart them (task 6.10). The backend already returns
  // the unanswered question, so resuming is just trusting it.
  useEffect(() => {
    let cancelled = false;

    api
      .getSession(token)
      .then((loaded) => {
        if (cancelled) return;
        setSession(loaded);

        if (loaded.status === "complete" || loaded.status === "evaluated") {
          navigate(`/interview/${token}/done`, { replace: true });
          return;
        }
        if (loaded.status === "in_progress" && loaded.current_question) {
          setSlot(loaded.current_slot ?? 1);
          setQuestion(loaded.current_question);
          setPhase("question");
          return;
        }
        setPhase("ready");
      })
      .catch((cause) => {
        if (cancelled) return;
        setLoadFailure(cause instanceof ApiError ? cause : null);
        setPhase("invalid");
      });

    return () => {
      cancelled = true;
    };
  }, [token, navigate]);

  useEffect(() => () => stopSpeaking(), []);

  // --- Auto-record --------------------------------------------------------
  // The candidate is never asked to press record (screens.md stage 2).
  // Recording begins once the question has rendered, or once speech
  // synthesis has finished reading it.
  const beginAnswer = useCallback(async () => {
    answerStartedAt.current = Date.now();
    await recorder.start();
  }, [recorder]);

  useEffect(() => {
    if (phase !== "question" || !question) return;

    let cancelled = false;
    setEntering(true);
    setImpulse((n) => n + 1);
    const enterTimer = window.setTimeout(() => setEntering(false), QUESTION_TRANSITION_MS);

    async function announce() {
      if (speechSupported()) {
        setSpeaking(true);
        // The question text is on screen throughout. Text is never
        // replaced by audio (screens.md stage 2).
        await speak(question, { onBoundary: () => setImpulse((n) => n + 1) });
        if (cancelled) return;
        setSpeaking(false);
      }
      autoRecordTimer.current = window.setTimeout(() => {
        if (!cancelled) void beginAnswer();
      }, AUTO_RECORD_DELAY_MS);
    }

    void announce();

    return () => {
      cancelled = true;
      window.clearTimeout(enterTimer);
      window.clearTimeout(autoRecordTimer.current);
      stopSpeaking();
    };
    // beginAnswer is intentionally excluded: it changes identity whenever
    // the recorder does, and re-running this would re-read the question.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, question]);

  // --- Submitting a turn --------------------------------------------------
  const submit = useCallback(
    async (audio: Blob, seconds: number) => {
      setPreviousQuestion(question);
      setPhase("processing");
      setStageLabel(UPLOAD_LABEL);

      for (let attempt = 0; attempt <= TURN_RETRY_ATTEMPTS; attempt += 1) {
        try {
          const advanced = await submitAnswerStreaming(
            token,
            { slot, audio, responseTimeSeconds: seconds },
            (stage) => setStageLabel(STAGE_LABELS[stage]),
          );

          if (advanced.status === "complete") {
            setPhase("complete");
            navigate(`/interview/${token}/done`, { replace: true });
            return;
          }

          recorder.reset();
          setSlot(advanced.next_slot ?? slot + 1);
          setQuestion(advanced.next_question ?? "");
          setPreviousQuestion("");
          setPhase("question");
          return;
        } catch (cause) {
          const isLast = attempt === TURN_RETRY_ATTEMPTS;
          const retryable = cause instanceof ApiError && cause.retryable;

          // A dropped connection is retried in place. Answers are
          // persisted per turn, so nothing is lost while we try again.
          if (retryable && !isLast) {
            setStageLabel("Connection interrupted. Reconnecting.");
            await new Promise((resolve) =>
              window.setTimeout(resolve, TURN_RETRY_BACKOFF_MS * (attempt + 1)),
            );
            continue;
          }

          setErrorMessage(
            cause instanceof ApiError
              ? cause.message
              : "We could not hear that answer clearly. Try recording it again.",
          );
          setPhase("turn-error");
          return;
        }
      }
    },
    [token, slot, question, recorder, navigate],
  );

  const handleDone = useCallback(async () => {
    stopSpeaking();
    setSpeaking(false);
    const take = await recorder.stop();
    if (!take || take.blob.size === 0) {
      setErrorMessage("We could not hear that answer clearly. Try recording it again.");
      setPhase("turn-error");
      return;
    }
    const seconds = Math.max(1, Math.round((Date.now() - answerStartedAt.current) / 1000));
    await submit(take.blob, seconds);
  }, [recorder, submit]);

  const handleStart = useCallback(async () => {
    // Belt and braces. The control is disabled until the camera is up, so
    // this only fires if something re-enabled it.
    if (cameraStatus !== "ready") return;
    setPhase("processing");
    setStageLabel("Preparing your first question");
    try {
      const started = await api.startInterview(token);
      setSession(started);
      setSlot(started.current_slot ?? 1);
      setQuestion(started.current_question ?? "");
      setPhase("question");
    } catch (cause) {
      setErrorMessage(
        cause instanceof ApiError ? cause.message : "This link is no longer valid.",
      );
      setPhase("invalid");
    }
  }, [token, cameraStatus]);

  const retryAnswer = useCallback(() => {
    recorder.reset();
    setErrorMessage("");
    setPreviousQuestion("");
    setPhase("question");
  }, [recorder]);

  // --- Render -------------------------------------------------------------

  if (phase === "loading") {
    return <Frame>{null}</Frame>;
  }

  if (phase === "invalid") {
    // A dead link and a failed request look the same to the candidate but
    // need different words. The backend's message for an expired token is
    // deliberately terse and would only restate the heading, so the
    // blocking copy from design-system.md section 17 is used instead: it
    // says why it might have happened and what to do about it. Anything
    // else is a real failure and keeps its own message.
    const deadLink = !loadFailure || loadFailure.code === "invalid_token";
    return (
      <Frame>
        <ErrorState
          variant="blocking"
          title={
            deadLink
              ? "This interview link is no longer valid"
              : "We could not open your interview"
          }
          body={
            deadLink
              ? "The link may have expired, or the interview may already be complete. If you believe this is a mistake, contact the person who sent you this link."
              : loadFailure.message
          }
        />
      </Frame>
    );
  }

  if (recorder.status === "denied") {
    return (
      <Frame>
        <MicrophoneBlocked />
      </Frame>
    );
  }

  if (recorder.status === "unsupported") {
    return (
      <Frame>
        <ErrorState
          variant="blocking"
          title="This browser cannot record audio"
          body="The interview is answered by voice. Open this link in Chrome, Safari or Edge and it will work."
        />
      </Frame>
    );
  }

  if (phase === "ready") {
    const cameraReady = cameraStatus === "ready";
    const cameraBlocked = cameraStatus === "unavailable";

    return (
      <Frame>
        <div className="rb-interview__ready">
          <h1 className="text-title-1 rb-interview__job">{session?.job_title}</h1>
          <p className="text-label rb-interview__eyebrow">Voice interview</p>
          <p className="text-body-lg rb-interview__intro">
            {spellOut(total)} question{total === 1 ? "" : "s"}. You will hear and
            read each one, then answer out loud. There is no time limit and no
            way to go back.
          </p>
          <p className="text-body-lg rb-interview__intro">
            Find somewhere quiet. Your microphone and camera stay on for the
            whole interview.
          </p>

          {/* The readiness check, and the reason this screen exists before
              question one. The preview doubles as the framing aid: what
              they see here is what the camera will show throughout. */}
          <div className="rb-interview__ready-check">
            <CameraPreview onStatus={setCameraStatus} />
            <p
              className={`rb-interview__ready-status${
                cameraBlocked ? " rb-interview__ready-status--blocked" : ""
              }`}
              role="status"
            >
              {cameraReady
                ? "Camera ready."
                : cameraBlocked
                  ? "Camera access is required for this interview. Allow the camera in your browser's address bar, then reload this page."
                  : "Waiting for camera access. Choose Allow when your browser asks."}
            </p>
          </div>

          <div className="rb-interview__ready-orb" aria-hidden="true">
            <VoiceOrb state="idle" analyser={recorder.analyser} size={160} />
          </div>
          <div className="rb-interview__start">
            <Button
              level="primary"
              size="large"
              onClick={handleStart}
              disabled={!cameraReady}
              loading={recorder.status === "requesting"}
            >
              {cameraReady ? "Start interview" : "Waiting for camera"}
            </Button>
          </div>
        </div>
      </Frame>
    );
  }

  const showing = phase === "processing" ? previousQuestion || question : question;
  // The orb reflects what is actually happening, and only ever from a real
  // signal: microphone amplitude while listening, word-boundary events
  // while speaking, and neither while processing.
  const orbState: OrbState = speaking
    ? "speaking"
    : phase === "processing"
      ? "processing"
      : recorder.status === "recording"
        ? "listening"
        : "idle";

  const hint = captionFor({
    speaking,
    recording: recorder.status === "recording",
    requesting: recorder.status === "requesting",
    heardSound: recorder.heardSound,
    silentMs: recorder.silentMs,
  });

  return (
    <Frame>
      <div className="rb-interview__turn">
        <p className="text-label rb-interview__progress-label">
          Question {slot} of {total}
        </p>
        <ProgressTrack current={slot} total={total} />

        <div className="rb-interview__question-frame">
          <h1
            className={[
              "rb-interview__question",
              questionSizeClass(showing),
              entering ? "rb-interview__question--entering" : "",
              phase === "processing" ? "rb-interview__question--dimmed" : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            {showing}
          </h1>
        </div>

        {/* The control region is a fixed height so replacing the button
            with a status label causes no layout shift (screens.md stage 3). */}
        <div className={`rb-interview__presence${cameraSettled ? " rb-interview__presence--camera-settled" : ""}`}>
          <CameraPreview onSettled={settleCamera} />
          <div className={`rb-interview__orb rb-interview__orb--${orbState}`}>
            <VoiceOrb
              state={orbState}
              analyser={recorder.analyser}
              impulse={impulse}
              size={orbSize}
            />
          </div>
        </div>

        <div className="rb-interview__control">
          {phase === "question" && (
            <>
              <div className="rb-interview__meter-group">
                <div className="rb-interview__meter">
                  <span
                    className={`rb-live-dot${
                      recorder.status === "recording" ? " rb-live-dot--on" : ""
                    }`}
                    aria-hidden="true"
                  />
                  <AudioLevelMeter
                    analyser={recorder.analyser}
                    active={recorder.status === "recording"}
                  />
                  <span className="text-mono rb-interview__timer">
                    {formatElapsed(recorder.elapsedSeconds)}
                  </span>
                </div>

                <p
                  className={`rb-interview__hint${
                    hint.caution ? " rb-interview__hint--caution" : ""
                  }`}
                  aria-live="polite"
                >
                  {hint.text}
                </p>
              </div>

              <Button
                level="primary"
                size="large"
                fullWidth
                onClick={handleDone}
                disabled={recorder.status !== "recording"}
              >
                Done answering
              </Button>
            </>
          )}

          {phase === "processing" && (
            <p className="rb-interview__stage" role="status" aria-live="polite">
              {stageLabel}
            </p>
          )}

          {phase === "turn-error" && (
            <div className="rb-interview__turn-error">
              <p className="rb-interview__stage">{errorMessage}</p>
              <Button level="primary" size="large" onClick={retryAnswer}>
                Record that answer again
              </Button>
            </div>
          )}
        </div>
      </div>
    </Frame>
  );
}

/** The full-viewport layout. No wordmark, no navigation, no footer. */
function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div className="rb-interview">
      <main className="rb-interview__inner">{children}</main>
    </div>
  );
}

/** A quiet 240px track, not a stepper with circles (screens.md stage 2). */
function ProgressTrack({ current, total }: { current: number; total: number }) {
  const ratio = total > 0 ? Math.min(1, current / total) : 0;
  return (
    <div
      className="rb-interview__track"
      role="progressbar"
      aria-valuenow={current}
      aria-valuemin={1}
      aria-valuemax={total}
      aria-label={`Question ${current} of ${total}`}
    >
      <span className="rb-interview__track-fill" style={{ width: `${ratio * 100}%` }} />
    </div>
  );
}


/**
 * Picks the type size for a question so it fits the fixed frame.
 *
 * The frame height is what keeps the orb and the control from moving
 * between questions, which means the text has to adapt instead of the
 * layout. Thresholds are character counts because that is what actually
 * predicts wrapped height at a known column width, and they were set
 * against real generated follow-ups: openers run around 60 characters,
 * probing questions 90 to 140, and the occasional deep one goes past 160.
 *
 * Only three sizes are ever used, and all three are existing roles from
 * the scale. Nothing here invents a font size.
 */
function questionSizeClass(text: string): string {
  if (text.length > 155) return "rb-interview__question--longest";
  if (text.length > 88) return "rb-interview__question--long";
  return "";
}

/**
 * Spells the question count in the ready screen's prose.
 *
 * This is the one number in the product that is written as a word.
 * Everything else is data in a column and gets tabular figures, but this
 * sits mid-sentence in a paragraph a nervous person is reading once, and
 * `Seven questions` scans as language where `7 questions` scans as a spec.
 *
 * The backend clamps the count to 5 through 10 (heuristics.py), so the
 * table only needs to cover that range and falls back to the numeral.
 */
function spellOut(count: number): string {
  const words: Record<number, string> = {
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
  };
  return words[count] ?? String(count);
}

/**
 * The one line of text under the meter.
 *
 * Two silences that look identical to a meter mean completely different
 * things, and the difference is whether this take has heard anything yet:
 *
 *   never heard a sound  ->  the microphone is not working. Say so, in
 *                            `caution`, because it needs fixing.
 *   heard, now quiet     ->  the candidate is thinking. `Still listening`,
 *                            in the ordinary caption color, because
 *                            nothing is wrong and this is not an error.
 *
 * Returning a blank space rather than nothing keeps the line's height, so
 * the button below never moves when a hint appears.
 */
function captionFor(input: {
  speaking: boolean;
  recording: boolean;
  requesting: boolean;
  heardSound: boolean;
  silentMs: number;
}): { text: string; caution: boolean } {
  if (input.speaking) return { text: "Reading the question", caution: false };
  // The browser prompt is open and the candidate has not answered it yet.
  // Without this the screen shows an empty caption and a disabled button,
  // which looks like the interview has hung rather than like it is waiting
  // on them (screens.md section 6, "Permission pending").
  if (input.requesting) return { text: "Waiting for microphone access", caution: false };
  if (!input.recording) return { text: " ", caution: false };
  if (!input.heardSound && input.silentMs >= NO_INPUT_WARNING_MS) {
    return { text: "We are not picking up any sound", caution: true };
  }
  if (input.heardSound && input.silentMs >= STILL_LISTENING_MS) {
    return { text: "Still listening", caution: false };
  }
  return { text: " ", caution: false };
}

/** Elapsed only. No countdown: there is no time limit, and a countdown
 *  creates panic (screens.md stage 2). */
function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}
