import type { CandidateSummary } from "../api/client";

/*
 * How Job Detail orders its candidates.
 *
 * Previously one flat list sorted by screening score, with recommendation
 * filter tabs on top. That put a candidate who has already been
 * interviewed, whose result is the most decisive information on the page,
 * in the same undifferentiated run as someone who applied an hour ago,
 * and it showed no interview score at all.
 *
 * The order below follows the pipeline: what has been done, then what is
 * waiting on the candidate, then what is waiting on HR, then what is
 * finished. Rejected sits last and collapsed, because it is the one group
 * you look at only deliberately.
 *
 * Kept out of the component so the ordering can be tested without
 * rendering, and so the group a candidate lands in is decided in one place
 * rather than inside a JSX conditional.
 */

export type PipelineGroupId =
  | "interviewed"
  | "in_progress"
  | "awaiting_interview"
  | "awaiting_decision"
  | "rejected";

/* Generic over the row type so the caller can carry extra fields through.
 * Job Detail attaches a rank computed across the whole field, and losing
 * it here would mean recomputing rank per group, which is exactly the
 * renumbering the rank column exists to avoid. */
export interface PipelineGroup<T extends CandidateSummary = CandidateSummary> {
  id: PipelineGroupId;
  title: string;
  /** Shown under the title when the group has rows. */
  hint: string;
  /** Rejected starts collapsed. */
  collapsed: boolean;
  candidates: T[];
}

const GROUP_ORDER: {
  id: PipelineGroupId;
  title: string;
  hint: string;
  collapsed: boolean;
}[] = [
  {
    id: "interviewed",
    title: "Interviewed",
    hint: "Scored against the rubric across the whole interview.",
    collapsed: false,
  },
  {
    id: "in_progress",
    title: "Interview in progress",
    hint: "Answering now. The result appears when they finish.",
    collapsed: false,
  },
  {
    id: "awaiting_interview",
    title: "Awaiting interview",
    hint: "Invited. The link is in their candidate portal.",
    collapsed: false,
  },
  {
    id: "awaiting_decision",
    title: "Awaiting your decision",
    hint: "Screened and waiting on you to approve or reject.",
    collapsed: false,
  },
  {
    id: "rejected",
    title: "Rejected",
    hint: "Not moving forward.",
    collapsed: true,
  },
];

/** Which group one candidate belongs to.
 *
 * Reads the interview status before the candidate state, because the
 * interview is the more specific fact: a candidate can sit in `approved`
 * while their interview is already `in_progress`.
 */
export function groupFor(candidate: CandidateSummary): PipelineGroupId {
  if (candidate.state === "rejected") return "rejected";

  if (candidate.interview_status === "complete" || candidate.interview_status === "evaluated") {
    return "interviewed";
  }
  if (candidate.interview_status === "in_progress") return "in_progress";

  if (candidate.state === "interviewed") return "interviewed";
  if (candidate.state === "interviewing") return "in_progress";
  if (candidate.state === "approved") return "awaiting_interview";

  return "awaiting_decision";
}

/**
 * Group and order the candidates for Job Detail.
 *
 * Within a group, the interviewed sort by interview score and everyone
 * else by screening score, both descending, because that is the number
 * that group is actually about. A missing score sorts last rather than as
 * zero: not yet scored is not the same as scored badly.
 *
 * Empty groups are dropped. A job with nobody rejected should not show a
 * "Rejected" heading with nothing under it.
 */
export function buildPipeline<T extends CandidateSummary>(candidates: T[]): PipelineGroup<T>[] {
  return GROUP_ORDER.map((group) => ({
    ...group,
    candidates: candidates
      .filter((candidate) => groupFor(candidate) === group.id)
      .sort((a, b) => {
        const key = group.id === "interviewed" ? "interview_score" : "screening_score";
        return (b[key] ?? -1) - (a[key] ?? -1);
      }),
  })).filter((group) => group.candidates.length > 0);
}
