/*
 * Text to speech via the browser's own `speechSynthesis`.
 *
 * No TTS API, by constraint: it is free, needs no key, and has zero
 * network latency, so the interview feels faster than the paid version.
 *
 * The contract every caller depends on: `speak` always settles. If speech
 * is unsupported, refused, interrupted, or silently dropped, it resolves
 * anyway. The interview auto-starts recording when speech ends, so a
 * promise that never settles would strand the candidate on a dead screen
 * with no way forward. That failure mode matters more than the speech.
 */

/** Chrome stops speaking after roughly 15 seconds unless nudged. */
const KEEPALIVE_INTERVAL_MS = 10_000;

/** Hard ceiling on waiting for `onend`. Backgrounded tabs sometimes never
 *  fire it at all. Generous enough that it never truncates a real question. */
const SPEECH_TIMEOUT_MS = 30_000;

export function speechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/**
 * Picks a natural English voice, preferring a local one.
 *
 * Local voices start instantly; remote ones round-trip to the vendor and
 * add a beat of silence before the question is spoken, which reads as a
 * hang on a screen where the candidate is waiting to be asked something.
 */
function pickVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  if (voices.length === 0) return null;

  const english = voices.filter((voice) => voice.lang.startsWith("en"));
  const pool = english.length > 0 ? english : voices;

  const preferred = ["Samantha", "Google US English", "Microsoft Aria", "Daniel"];
  for (const name of preferred) {
    const match = pool.find((voice) => voice.name === name);
    if (match) return match;
  }
  return pool.find((voice) => voice.localService) ?? pool[0];
}

/** Voices populate asynchronously in Chrome, so the first question would
 *  otherwise be spoken by whatever default happened to be loaded. */
function voicesReady(): Promise<void> {
  if (!speechSupported()) return Promise.resolve();
  if (window.speechSynthesis.getVoices().length > 0) return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      window.speechSynthesis.removeEventListener("voiceschanged", done);
      resolve();
    };
    window.speechSynthesis.addEventListener("voiceschanged", done);
    // Some browsers never fire the event. Do not wait forever on it.
    window.setTimeout(done, 1000);
  });
}

/**
 * Speaks `text`, resolving when it finishes or is cut short.
 *
 * Resolves rather than rejects on every failure path, deliberately. The
 * caller's next step is always the same - show the question and start
 * recording - and it should not have to branch on whether audio worked.
 */
export interface SpeakOptions {
  /**
   * Fires as each word begins.
   *
   * This is the only real signal available from speech synthesis. Its audio
   * goes straight to the system output and never through an AudioContext,
   * so there is no waveform to analyse and no amplitude to read - see
   * VoiceOrb, which uses these events rather than inventing a level.
   *
   * Not every voice reports boundaries. Callers must behave sensibly when
   * this never fires.
   */
  onBoundary?: () => void;
}

export async function speak(text: string, options: SpeakOptions = {}): Promise<void> {
  if (!speechSupported()) return;

  await voicesReady();

  return new Promise<void>((resolve) => {
    let settled = false;
    let keepAlive = 0;
    let timeout = 0;
    let startCheck = 0;

    const finish = () => {
      if (settled) return;
      settled = true;
      window.clearInterval(keepAlive);
      window.clearTimeout(timeout);
      window.clearTimeout(startCheck);
      resolve();
    };

    try {
      // Anything already queued is stale by definition: the only caller is
      // the question that is on screen right now.
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      const voice = pickVoice();
      if (voice) utterance.voice = voice;
      utterance.lang = voice?.lang ?? "en-US";
      // Slightly under default. An interview question read at full speed
      // sounds hurried, and the candidate is hearing it once.
      utterance.rate = 0.95;
      utterance.pitch = 1;

      utterance.onend = finish;
      utterance.onerror = finish;
      if (options.onBoundary) {
        utterance.onboundary = (event) => {
          // Sentence boundaries fire too; only words are wanted, so that
          // the pulse tracks speech rhythm rather than punctuation.
          if (event.name === "word" || event.name === undefined) options.onBoundary?.();
        };
      }

      window.speechSynthesis.speak(utterance);

      // Did it actually start?
      //
      // Autoplay policy blocks synthesis that was not triggered by a user
      // gesture, and it fails silently: no error, no `onend`, nothing
      // speaking. That happens on the resume path, where a refresh drops
      // the candidate straight onto a question with no click in between.
      // Without this check the keepalive below would not notice for ten
      // seconds, and the candidate would sit in front of a disabled button
      // waiting for audio that is never coming.
      startCheck = window.setTimeout(() => {
        const synth = window.speechSynthesis;
        if (!synth.speaking && !synth.pending) finish();
      }, 1200);

      keepAlive = window.setInterval(() => {
        if (!window.speechSynthesis.speaking) {
          finish();
          return;
        }
        window.speechSynthesis.pause();
        window.speechSynthesis.resume();
      }, KEEPALIVE_INTERVAL_MS);

      timeout = window.setTimeout(finish, SPEECH_TIMEOUT_MS);
    } catch {
      finish();
    }
  });
}

/** Stops immediately. Called when the candidate submits an answer while
 *  the question is still being read, and on unmount. */
export function stopSpeaking(): void {
  if (speechSupported()) window.speechSynthesis.cancel();
}
