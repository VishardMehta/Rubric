/*
 * Data components. design-system.md section 21.
 *
 * Everything that renders a score, a band or a ranked list. The rule they
 * all share: none of them derives meaning from a number. Bands and
 * recommendations arrive computed from the backend and are only ever
 * mapped to a colour (see lib/tone.ts).
 */
export { DataTable } from "./DataTable";
export type { Column } from "./DataTable";
export { EvidenceList } from "./EvidenceList";
export { RecommendationChip } from "./RecommendationChip";
export { ScoreBreakdown } from "./ScoreBreakdown";
export { ScoreHero } from "./ScoreHero";
export { ScoreInline } from "./ScoreInline";
export { StatRow } from "./StatRow";
export type { Stat } from "./StatRow";
export { StatusChip } from "./StatusChip";
