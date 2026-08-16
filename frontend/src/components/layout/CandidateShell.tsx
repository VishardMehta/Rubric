import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import "./layout.css";

/**
 * design-system.md section 2.
 *
 * A quiet wordmark at top and nothing else. No navigation, no back button,
 * no footer - the only way out is the wordmark itself, which goes to the
 * landing page.
 *
 * The interview screen does not use this shell. It removes even the
 * wordmark and owns the full viewport (screens.md section 7).
 */
export function CandidateShell({
  children,
  wide = false,
}: {
  children: ReactNode;
  /** Widens the content column past the 640px reading measure.
   *
   *  For the one candidate screen that is a document rather than a form:
   *  the opportunity page, where the apply action sits beside the posting
   *  instead of above it. The prose inside keeps a reading measure of its
   *  own, so this widens the frame and not the line length. */
  wide?: boolean;
}) {
  return (
    <div className="rb-candidate-shell">
      <Link to="/" className="rb-wordmark rb-candidate-shell__wordmark" aria-label="Rubric">
        <img src="/logo.png" alt="" className="rb-candidate-shell__mark" />
        Rubric
      </Link>
      <main
        className={`rb-candidate-shell__content${wide ? " rb-candidate-shell__content--wide" : ""}`}
      >
        {children}
      </main>
    </div>
  );
}
