import type { Band, CandidateState, Recommendation } from "../api/client";
import type { ChipTone } from "../components/primitives";

/*
 * Band and recommendation to semantic tone.
 *
 * READ THIS BEFORE ADDING A FUNCTION HERE.
 *
 * Every function in this file takes an enum the backend already decided
 * and returns a color role. None of them takes a number, and none of them
 * ever may. Turning a score into a band is the backend's job, done once,
 * in app/services/scoring.py, and returned alongside the score
 * (design-system.md section 3, CLAUDE.md scoring discipline).
 *
 * The reason is not purity. Thresholds move. A frontend that recomputes a
 * band from 69 disagrees with a backend that just moved the boundary to
 * 68, and the two contradict each other on screen, in front of a client,
 * with the number and the word saying different things.
 *
 * If you find yourself wanting `bandFor(score: number)`, the value you
 * need is already in the response.
 */

export function toneForBand(band: Band | null): ChipTone {
  switch (band) {
    case "strong":
      return "positive";
    case "borderline":
      return "caution";
    case "weak":
      return "negative";
    default:
      return "neutral";
  }
}

export function toneForRecommendation(recommendation: Recommendation | null): ChipTone {
  switch (recommendation) {
    case "shortlist":
      return "positive";
    case "review":
      return "caution";
    case "reject":
      return "negative";
    default:
      return "neutral";
  }
}

/** Display text for a recommendation. The backend sends the decision; the
 *  capitalised word HR reads is a presentation concern and lives here. */
export function recommendationLabel(recommendation: Recommendation | null): string {
  switch (recommendation) {
    case "shortlist":
      return "Shortlist";
    case "review":
      return "Review";
    case "reject":
      return "Reject";
    default:
      return "";
  }
}

/**
 * Display text for a pipeline stage. Always neutral in tone - a stage is
 * not good or bad (design-system.md section 11).
 *
 * `applied` reads as "Screening" because it means the row exists but
 * screening has not finished yet. Naming the stage after what is happening
 * is more use to HR than naming it after the database value
 * (screens.md section 3).
 */
export function statusLabel(state: CandidateState): string {
  switch (state) {
    case "applied":
      return "Screening";
    case "screened":
      return "Screened";
    case "approved":
      return "Approved";
    case "interviewing":
      return "Interviewing";
    case "interviewed":
      return "Interviewed";
    case "hired":
      return "Hired";
    case "rejected":
      return "Rejected";
    default:
      return state;
  }
}
