import type { ReactNode } from "react";
import "./primitives.css";

export type ChipTone = "neutral" | "positive" | "caution" | "negative";

interface ChipProps {
  tone?: ChipTone;
  children: ReactNode;
}

/**
 * design-system.md section 11.
 *
 * The tone is passed in, never derived. A chip does not know what a score
 * means; the backend already decided and sent a band. Callers in Phase 8
 * wrap this as RecommendationChip (semantic) and StatusChip (always
 * neutral, because a pipeline stage is not good or bad).
 *
 * There is no icon slot and no dot variant: a colored dot with no text
 * fails for colorblind users and communicates nothing to anyone else.
 */
export function Chip({ tone = "neutral", children }: ChipProps) {
  return <span className={`rb-chip rb-chip--${tone}`}>{children}</span>;
}
