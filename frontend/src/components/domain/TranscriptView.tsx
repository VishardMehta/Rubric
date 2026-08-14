import "./domain.css";

interface TranscriptViewProps {
  text: string | null;
  /** Collapsed by default on Candidate Detail (screens.md section 4). */
  collapsible?: boolean;
  summary?: string;
}

/**
 * The spoken introduction or one interview answer, as transcribed.
 *
 * Constrained to 68ch (design-system.md section 4). Transcripts are the
 * longest prose in the product and full browser-width text is the fastest
 * way to make a premium layout look cheap.
 *
 * Rendered verbatim, including the disfluencies. This is what the model
 * scored against, so cleaning it up here would show HR something other
 * than the evidence.
 */
export function TranscriptView({
  text,
  collapsible = false,
  summary = "Transcript",
}: TranscriptViewProps) {
  if (!text) {
    return <p className="rb-transcript__pending">The transcript is not ready yet.</p>;
  }

  const body = <p className="rb-transcript__text">{text}</p>;

  if (!collapsible) return body;

  return (
    <details className="rb-transcript">
      <summary className="rb-transcript__summary">{summary}</summary>
      {body}
    </details>
  );
}
