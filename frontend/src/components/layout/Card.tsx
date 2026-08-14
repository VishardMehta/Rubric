import type { ReactNode } from "react";
import "./layout.css";

interface CardProps {
  /** 24px padding instead of 20px, when the card is the page's main content. */
  primary?: boolean;
  /** No padding, for a card wrapping a table that draws its own rows. */
  flush?: boolean;
  children: ReactNode;
}

/**
 * design-system.md section 7.
 *
 * Use for: the rubric block, a sub-score breakdown, one interview turn, a
 * strengths or concerns group. Do not use for: a single statistic, a
 * section that already has a heading, a table, a form.
 *
 * There is no `elevated` prop. Cards do not float in Rubric; popovers and
 * modals do.
 */
export function Card({ primary = false, flush = false, children }: CardProps) {
  const classes = [
    "rb-card",
    primary ? "rb-card--primary" : "",
    flush ? "rb-card--flush" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return <div className={classes}>{children}</div>;
}
