import { useEffect, useRef, useState } from "react";
import "./domain.css";

/**
 * Local-only interview framing aid. It never records, uploads, or analyses
 * video; the camera is simply a live mirror so the candidate can position
 * themselves before and during their voice interview.
 */
export function CameraPreview() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");

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
        if (!cancelled) setState("unavailable");
      }
    }

    void start();
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  return (
    <section className={`rb-camera rb-camera--${state}`} aria-label="Camera framing guide">
      {state !== "unavailable" && <video ref={videoRef} autoPlay muted playsInline />}
      <div className="rb-camera__guide" aria-hidden="true"><span /></div>
      <p className="rb-camera__caption" aria-live="polite">
        {state === "loading" ? "Starting camera" : state === "ready" ? "Keep your face centered" : "Camera unavailable — continue with voice"}
      </p>
    </section>
  );
}
