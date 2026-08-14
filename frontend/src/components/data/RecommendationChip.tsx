import { Chip } from "../primitives";
import type { Recommendation } from "../../api/client";
import { recommendationLabel, toneForRecommendation } from "../../lib/tone";

/**
 * design-system.md section 11.
 *
 * The one badge in Rubric that carries semantic colour, because it is the
 * one badge that carries a judgement. Pair it with StatusChip, which is
 * always neutral, and never merge the two.
 *
 * Renders nothing when there is no recommendation yet. An empty chip would
 * imply a decision had been made.
 */
export function RecommendationChip({
  recommendation,
}: {
  recommendation: Recommendation | null;
}) {
  if (!recommendation) return null;
  return (
    <Chip tone={toneForRecommendation(recommendation)}>
      {recommendationLabel(recommendation)}
    </Chip>
  );
}
