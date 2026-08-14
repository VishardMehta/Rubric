import type { ReactNode } from "react";
import "./layout.css";

/**
 * design-system.md section 2.
 *
 * A quiet wordmark at top and nothing else. No navigation, no back button,
 * no footer. The wordmark is not a link: there is nowhere for a candidate
 * to go, and a link that leads to an empty HR dashboard would be worse
 * than no link at all.
 *
 * The interview screen does not use this shell. It removes even the
 * wordmark and owns the full viewport (screens.md section 7).
 */
export function CandidateShell({ children }: { children: ReactNode }) {
  return (
    <div className="rb-candidate-shell">
      <span className="rb-wordmark rb-candidate-shell__wordmark">Rubric</span>
      <main className="rb-candidate-shell__content">{children}</main>
    </div>
  );
}
