import { Spinner } from "../primitives/Spinner";
import "./feedback.css";

interface LoadingStateProps {
  /**
   * Names the work actually happening: `Analyzing job description`,
   * `Transcribing your answer`, `Scoring against rubric`.
   *
   * The system is never a person. No `AI is thinking`, no `Hang tight`.
   */
  label: string;
  /** Centered in its own region rather than inline on a row. */
  block?: boolean;
}

/**
 * design-system.md section 15.
 *
 * The label changes only when the backend actually reaches the next stage.
 * Nothing in this component advances it on a timer, and there is no
 * percentage prop: Rubric cannot know a percentage for a model call, so
 * showing one would be a lie.
 *
 * `aria-live="polite"` announces each stage change to a screen reader
 * without interrupting whatever it is currently reading.
 */
export function LoadingState({ label, block = false }: LoadingStateProps) {
  return (
    <div
      className={block ? "rb-loading rb-loading--block" : "rb-loading"}
      role="status"
      aria-live="polite"
    >
      <Spinner size="sm" />
      <span>{label}</span>
    </div>
  );
}
