import { useEffect, useRef, useState } from "react";
import "./domain.css";

/**
 * Local-only interview framing aid. It never records, uploads, or analyses
 * video; the camera is simply a live mirror so the candidate can position
 * themselves before and during their voice interview.
 */
export type CameraState = "loading" | "ready" | "unavailable";

export function CameraPreview({
  onSettled,
  onStatus,
}: {
  onSettled?: () => void;
  /** Reports whether the camera came up. The interview uses this to hold
   *  the Start action until there is a working picture: a candidate who
   *  discovers the camera is blocked on question four has already lost
   *  the first three. */
  onStatus?: (state: CameraState) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [state, setState] = useState<CameraState>("loading");
  const [guidanceVisible, setGuidanceVisible] = useState(true);

  // Held in a ref so neither effect below lists it as a dependency. A
  // parent that re-renders with a fresh callback would otherwise tear down
  // the camera stream and ask for permission again mid-interview.
  const onSettledRef = useRef(onSettled);
  onSettledRef.current = onSettled;
  const onStatusRef = useRef(onStatus);
  onStatusRef.current = onStatus;

  useEffect(() => {
    onStatusRef.current?.(state);
  }, [state]);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;

    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setState("ready");
      } catch {
        if (!cancelled) {
          setState("unavailable");
          onSettledRef.current?.();
        }
      }
    }

    void start();
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    if (state !== "ready") return;
    // Five seconds is enough to frame a face without leaving the live video
    // competing with the conversation for the whole interview.
    const timer = window.setTimeout(() => {
      setGuidanceVisible(false);
      onSettledRef.current?.();
    }, 5000);
    return () => window.clearTimeout(timer);
  }, [state]);

  return (
    <section className={`rb-camera rb-camera--${state}${guidanceVisible ? "" : " rb-camera--settled"}`} aria-label="Camera preview">
      {state !== "unavailable" && <video ref={videoRef} autoPlay muted playsInline />}
      <div className="rb-camera__guide" aria-hidden="true"><span /></div>
      <p className="rb-camera__caption" aria-live="polite">
        {state === "loading" ? "Starting camera" : state === "ready" && guidanceVisible ? "Keep your face centered" : state === "unavailable" ? "Camera unavailable, continue with voice" : ""}
      </p>
    </section>
  );
}
