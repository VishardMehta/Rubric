import type { Rubric } from "../../api/client";
import "./domain.css";

interface RubricPanelProps {
  rubric: Rubric;
  /** Collapsed behind a disclosure, as on Job Detail (screens.md 3). */
  collapsible?: boolean;
}

/**
 * screens.md section 2, stage C. Reused collapsed on Job Detail.
 *
 * The moment the product explains itself: these are the criteria every
 * applicant will be scored against, with the point allocation visible
 * before anyone has applied.
 *
 * **Points are neutral ink, not semantic colour.** They are allocations,
 * not scores. Nobody has earned or lost anything yet, so tinting them
 * would be inventing a judgement that does not exist.
 */
export function RubricPanel({ rubric, collapsible = false }: RubricPanelProps) {
  const total = rubric.criteria.reduce((sum, criterion) => sum + criterion.points, 0);

  const body = (
    <div className="rb-rubric">
      {rubric.criteria.map((criterion) => (
        <div key={criterion.id} className="rb-rubric__row">
          <div className="rb-rubric__head">
            <span className="rb-rubric__name">{criterion.name}</span>
            <span className="rb-rubric__points">{criterion.points} pts</span>
          </div>
          <p className="rb-rubric__description">{criterion.description}</p>
        </div>
      ))}
      <div className="rb-rubric__total">
        <span>Total</span>
        <span>{total} pts</span>
      </div>
    </div>
  );

  if (!collapsible) return body;

  return (
    <details className="rb-rubric__disclosure">
      <summary className="rb-rubric__summary">
        Rubric · {rubric.criteria.length} criteria · {total} points
      </summary>
      {body}
    </details>
  );
}
