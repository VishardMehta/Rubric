import type { EvidenceOut } from "../../api/client";
import "./data.css";

const SOURCE_LABELS: Record<EvidenceOut["source"], string> = {
  introduction: "Introduction",
  resume: "Resume",
};

/**
 * screens.md section 4: every evidence quote is tagged with its source.
 *
 * This is the point of the whole screen. A score that came from a written
 * claim on a resume and a score that came from someone explaining their
 * work out loud are different kinds of evidence, and HR has to be able to
 * tell them apart at a glance. Without the tag the breakdown is just
 * numbers with decoration under them.
 *
 * The quote is rendered verbatim. It is validated server-side as a real
 * span from the named source, so nothing here truncates or reflows it
 * beyond wrapping.
 */
export function EvidenceList({ evidence }: { evidence: EvidenceOut[] }) {
  if (evidence.length === 0) {
    return (
      <p className="rb-evidence__none">
        No supporting quote was found in either source for this criterion.
      </p>
    );
  }

  return (
    <ul className="rb-evidence">
      {evidence.map((item, index) => (
        <li key={`${item.source}-${index}`} className="rb-evidence__item">
          <span className="text-label rb-evidence__source">{SOURCE_LABELS[item.source]}</span>
          <blockquote className="rb-evidence__quote">{item.quote}</blockquote>
        </li>
      ))}
    </ul>
  );
}
