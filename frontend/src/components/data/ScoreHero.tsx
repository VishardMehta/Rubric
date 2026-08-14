import type { Band } from "../../api/client";
import { toneForBand } from "../../lib/tone";
import "./data.css";

interface ScoreHeroProps {
  /** Uppercase eyebrow: `SCREENING SCORE`, `OVERALL`. */
  label: string;
  score: number;
  outOf?: number;
  band: Band | null;
  /** The word beside the denominator: `Shortlist`, `Review`, `Reject`. */
  bandLabel?: string;
}

/**
 * design-system.md section 12, "Hero score". One per screen, maximum.
 *
 * No progress ring, no gauge, no arc. A number set large is more confident
 * than a number wrapped in a donut, and every radial score widget in this
 * category of product looks the same.
 *
 * The band word sits beside the number in its semantic tone, which is what
 * makes the colour redundant rather than load-bearing: remove all colour
 * and the screen still says "Shortlist" in words (section 3).
 */
export function ScoreHero({ label, score, outOf = 100, band, bandLabel }: ScoreHeroProps) {
  const tone = toneForBand(band);
  return (
    <div className="rb-score-hero">
      <p className="text-label rb-score-hero__eyebrow">{label}</p>
      <p className={`rb-score-hero__value rb-score-hero__value--${tone}`}>{score}</p>
      <p className="rb-score-hero__meta">
        out of {outOf}
        {bandLabel && (
          <>
            {" · "}
            <span className={`rb-score-hero__band rb-score-hero__band--${tone}`}>
              {bandLabel}
            </span>
          </>
        )}
      </p>
    </div>
  );
}
