import { CandidateShell } from "../../components/layout";
import "./interview.css";

/**
 * screens.md section 8. Purpose: end cleanly and say nothing more.
 *
 * No score, no band, no feedback, no summary of what they said. The
 * candidate never sees a score at any point (product.md section 2), and
 * this is the screen where the temptation to add one is strongest.
 *
 * No call to action, no link, no button. There is genuinely nothing left
 * to do, and offering something would imply otherwise.
 *
 * Reopening a completed interview link lands here rather than on an error,
 * which is handled by the redirect in InterviewPage.
 */
export function InterviewCompletePage() {
  return (
    <CandidateShell>
      <div className="rb-interview-done">
        <h1 className="text-title-1 rb-interview-done__title">
          Your interview is complete.
        </h1>
        <p className="text-body-lg rb-interview-done__body">
          Your answers have been sent for review. The hiring team will be in
          touch.
        </p>
        <p className="text-body-lg rb-interview-done__body">
          You can close this window.
        </p>
      </div>
    </CandidateShell>
  );
}
