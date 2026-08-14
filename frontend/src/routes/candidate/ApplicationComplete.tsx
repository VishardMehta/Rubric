import { useLocation } from "react-router-dom";
import { CandidateShell } from "../../components/layout";
// Reuses the "done" screen's classes from the interview screen - both are
// the same quiet, no-action confirmation layout (screens.md sections 6, 8).
import "./interview.css";

interface DoneState {
  jobTitle?: string;
}

/**
 * product.md section 5, `/apply/:jobId/done`. Purpose: confirm receipt and
 * say nothing more.
 *
 * No screening score, band or recommendation - the candidate never sees
 * one, at any point (product.md section 2), and screening has already run
 * by the time this screen renders. No call to action: there is nothing
 * left to do until the hiring team responds.
 */
export function ApplicationCompletePage() {
  const location = useLocation();
  const jobTitle = (location.state as DoneState | null)?.jobTitle;

  return (
    <CandidateShell>
      <div className="rb-interview-done">
        <h1 className="text-title-1 rb-interview-done__title">
          Your application has been received.
        </h1>
        <p className="text-body-lg rb-interview-done__body">
          {jobTitle
            ? `Thank you for applying to ${jobTitle}. The hiring team will be in touch if you are shortlisted.`
            : "Thank you for applying. The hiring team will be in touch if you are shortlisted."}
        </p>
        <p className="text-body-lg rb-interview-done__body">You can close this window.</p>
      </div>
    </CandidateShell>
  );
}
