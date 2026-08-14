import type { ReactNode } from "react";
import "./feedback.css";

interface EmptyStateProps {
  /** What is missing. */
  title: string;
  /** Why it matters. */
  body: string;
  /** What to do about it. */
  action?: ReactNode;
  /** Inline, for a region already inside a card or panel. */
  inline?: boolean;
}

/**
 * design-system.md section 16.
 *
 * Three parts, all required in spirit: what is missing, why it matters,
 * what to do. Never render a blank region, and never render an empty table
 * with headers and no rows.
 *
 * There is no illustration slot. An empty state on a hiring dashboard is
 * not an occasion for a drawing.
 */
export function EmptyState({ title, body, action, inline = false }: EmptyStateProps) {
  return (
    <div className={inline ? "rb-state" : "rb-state rb-state--empty"}>
      <h3 className="rb-state__title">{title}</h3>
      <p className="rb-state__body">{body}</p>
      {action && <div className="rb-state__actions">{action}</div>}
    </div>
  );
}
