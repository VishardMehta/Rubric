import { useEffect, useRef } from "react";
import { METER_BAR_COUNT } from "../../lib/heuristics";
import { readLevel } from "../../hooks/useAudioRecorder";
import "./domain.css";

interface AudioLevelMeterProps {
  /** The live analyser. Null before permission is granted. */
  analyser: React.RefObject<AnalyserNode | null>;
  /** Drives the meter only while true. Stops the loop otherwise. */
  active: boolean;
  /** CSS width. The interview narrows this at 375px (screens.md 7). */
  width?: number;
  height?: number;
}

/**
 * The one continuously animating element in the product, and it is driven
 * by real microphone input (design-system.md section 18).
 *
 * Drawn on a canvas rather than as DOM bars: this repaints every animation
 * frame, and 48 elements re-rendering through React at 60Hz would cost far
 * more than it is worth.
 *
 * Under `prefers-reduced-motion` it becomes a single static filled bar
 * showing the current level, updated a few times a second. That is section
 * 18's requirement exactly - the information is still there, the motion is
 * not.
 */
export function AudioLevelMeter({
  analyser,
  active,
  width = 240,
  height = 32,
}: AudioLevelMeterProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const historyRef = useRef<number[]>(new Array(METER_BAR_COUNT).fill(0));
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // Draw at device resolution so the bars are not soft on a retina
    // display, then scale the context back to CSS pixels.
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    context.scale(ratio, ratio);

    const styles = getComputedStyle(document.documentElement);
    const liveColor = styles.getPropertyValue("--color-live").trim() || "#d1453b";
    const trackColor = styles.getPropertyValue("--color-hairline").trim() || "#e8e8e5";

    let stopped = false;

    function paint() {
      if (stopped || !context) return;

      const node = analyser.current;
      const level = active && node ? readLevel(node) : 0;

      if (!reduceMotion) {
        historyRef.current.push(level);
        historyRef.current.shift();
      }

      context.clearRect(0, 0, width, height);

      if (reduceMotion) {
        // One bar, current level, no history and no motion.
        const trackHeight = 4;
        const top = (height - trackHeight) / 2;
        context.fillStyle = trackColor;
        context.beginPath();
        context.roundRect(0, top, width, trackHeight, trackHeight / 2);
        context.fill();

        context.fillStyle = liveColor;
        context.beginPath();
        context.roundRect(0, top, Math.max(2, width * level), trackHeight, trackHeight / 2);
        context.fill();
        return;
      }

      const gap = 2;
      const barWidth = (width - gap * (METER_BAR_COUNT - 1)) / METER_BAR_COUNT;
      const minHeight = 2;

      for (let i = 0; i < METER_BAR_COUNT; i += 1) {
        const value = historyRef.current[i];
        const barHeight = Math.max(minHeight, value * height);
        const x = i * (barWidth + gap);
        const y = (height - barHeight) / 2;
        // Silence stays visible as a flat track rather than disappearing,
        // so the meter always looks connected rather than broken.
        context.fillStyle = value > 0.02 ? liveColor : trackColor;
        context.beginPath();
        context.roundRect(x, y, barWidth, barHeight, barWidth / 2);
        context.fill();
      }
    }

    if (reduceMotion) {
      // Still needs to update, just not every frame.
      paint();
      const timer = window.setInterval(paint, 200);
      return () => {
        stopped = true;
        window.clearInterval(timer);
      };
    }

    function loop() {
      paint();
      frameRef.current = requestAnimationFrame(loop);
    }
    loop();

    return () => {
      stopped = true;
      cancelAnimationFrame(frameRef.current);
    };
  }, [analyser, active, width, height]);

  return (
    <canvas
      ref={canvasRef}
      className="rb-level-meter"
      style={{ width, height }}
      // The meter carries no information a screen reader user can act on;
      // the captions beside it say everything that matters.
      aria-hidden="true"
    />
  );
}
