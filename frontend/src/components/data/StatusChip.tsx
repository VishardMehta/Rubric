import { Chip } from "../primitives";
import type { CandidateState } from "../../api/client";
import { statusLabel } from "../../lib/tone";

/**
 * design-system.md section 11.
 *
 * Always neutral. A pipeline stage is not good or bad, and a candidate
 * sitting at "Applied" is not failing at anything. There is deliberately
 * no `tone` prop: the moment this could be tinted, someone would tint
 * "Rejected" red and the table would grow a second colour per row.
 *
 * The wording lives in lib/tone.ts beside the other label mappings.
 */
export function StatusChip({ state }: { state: CandidateState }) {
  return <Chip tone="neutral">{statusLabel(state)}</Chip>;
}
