import type { ReactNode } from "react";
import { ApiError } from "../../api/client";
import "./feedback.css";

interface ErrorStateProps {
  /** What happened. */
  title: string;
  /** Why, and what the user can do. Never a status code, never a stack trace. */
  body: string;
  action?: ReactNode;
  /**
   * `inline` sits where the failed content would have been and offers a
   * retry. `blocking` takes the region, for an invalid interview link.
   */
  variant?: "inline" | "blocking";
}

/**
 * design-system.md section 17.
 *
 * Candidate-facing copy is gentler and never blames the candidate:
 * `We could not hear that answer clearly` rather than `Transcription
 * failed`.
 */
export function ErrorState({ title, body, action, variant = "inline" }: ErrorStateProps) {
  const classes =
    variant === "blocking"
      ? "rb-state rb-state--centered"
      : "rb-state rb-state--inline-error";

  return (
    <div className={classes} role="alert">
      <h3 className="rb-state__title">{title}</h3>
      <p className="rb-state__body">{body}</p>
      {action && <div className="rb-state__actions">{action}</div>}
    </div>
  );
}

/**
 * Renders whatever the API threw.
 *
 * `error.message` is written by the backend as user-facing prose and is
 * used verbatim. Composing a different sentence here would mean two places
 * decide how a failure reads, and they would drift.
 */
export function ApiErrorState({
  error,
  title = "Something went wrong",
  action,
  variant = "inline",
}: {
  error: unknown;
  title?: string;
  action?: ReactNode;
  variant?: "inline" | "blocking";
}) {
  const message =
    error instanceof ApiError ? error.message : "Something went wrong. Try again.";
  return <ErrorState title={title} body={message} action={action} variant={variant} />;
}
