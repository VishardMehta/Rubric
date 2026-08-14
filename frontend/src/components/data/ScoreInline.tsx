import type { Band } from "../../api/client";
import { toneForBand } from "../../lib/tone";
import "./data.css";

interface ScoreInlineProps {
  /** Null while the candidate is still being screened. */
  score: number | null;
  /** Computed by the backend and sent with the score. Never derived here. */
  band: Band | null;
}

/**
 * design-system.md section 12, "In tables".
 *
 * Coloured text on a plain background, with no chip and no fill. The
 * recommendation chip in the next column carries the only tint on the row.
 *
 * A candidate who has not been scored yet gets an em-space, not a zero
 * (screens.md section 3). Zero is a real score that a real candidate can
 * earn, and showing it for "we have not looked yet" would be a lie about
 * someone's application.
 */
export function ScoreInline({ score, band }: ScoreInlineProps) {
  if (score === null) {
    return (
      <span className="rb-score-inline rb-score-inline--pending" aria-label="Not scored yet">
        {" "}
      </span>
    );
  }

  return (
    <span className={`rb-score-inline rb-score-inline--${toneForBand(band)}`}>{score}</span>
  );
}
