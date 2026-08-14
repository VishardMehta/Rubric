import type { SubScoreOut } from "../../api/client";
import { EvidenceList } from "./EvidenceList";
import "./data.css";

interface ScoreBreakdownProps {
  subScores: SubScoreOut[];
  /**
   * The authoritative total, as computed and verified by the backend.
   *
   * Deliberately not summed from `subScores` here. The backend already
   * checks that the sub-scores sum to this number before the row is saved
   * (CLAUDE.md scoring discipline), so re-adding them in the browser would
   * at best duplicate that check and at worst quietly disagree with the
   * number shown everywhere else in the product.
   */
  total: number;
  /** Expanding a criterion reveals the quotes that earned the points. */
  showEvidence?: boolean;
}

/**
 * design-system.md section 12, "Breakdown". Rubric's core promise made
 * visible: every hero score expands into the criteria that produced it.
 *
 * The bars are `ink-secondary`, not semantic colour. Five tinted bars in a
 * stack is noise, and the numbers beside them already carry the
 * comparison.
 */
export function ScoreBreakdown({ subScores, total, showEvidence = false }: ScoreBreakdownProps) {
  const possible = subScores.reduce((sum, item) => sum + item.points_possible, 0);

  return (
    <div className="rb-breakdown">
      {subScores.map((item) => (
        <Row key={item.criterion_id} item={item} showEvidence={showEvidence} />
      ))}

      <div className="rb-breakdown__total">
        <span className="rb-breakdown__total-label">Total</span>
        <span className="rb-breakdown__total-value">
          {total} / {possible}
        </span>
      </div>
    </div>
  );
}

function Row({ item, showEvidence }: { item: SubScoreOut; showEvidence: boolean }) {
  const ratio = item.points_possible > 0 ? item.points_awarded / item.points_possible : 0;

  const line = (
    <>
      <span className="rb-breakdown__name">{item.criterion_name}</span>
      <span className="rb-breakdown__score">
        {item.points_awarded} / {item.points_possible}
      </span>
      <span className="rb-breakdown__bar" aria-hidden="true">
        <span className="rb-breakdown__fill" style={{ width: `${ratio * 100}%` }} />
      </span>
    </>
  );

  // Only rows that actually have quotes become disclosures. A row that
  // opens onto "nothing here" teaches people to stop opening rows.
  if (!showEvidence || item.evidence.length === 0) {
    return <div className="rb-breakdown__row">{line}</div>;
  }

  return (
    <details className="rb-breakdown__details">
      <summary className="rb-breakdown__row rb-breakdown__row--expandable">{line}</summary>
      <div className="rb-breakdown__evidence">
        <EvidenceList evidence={item.evidence} />
      </div>
    </details>
  );
}
