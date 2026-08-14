import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Spinner } from "./Spinner";
import "./primitives.css";

export type ButtonLevel = "primary" | "secondary" | "tertiary" | "destructive";

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> {
  level?: ButtonLevel;
  /** 48px, for the single candidate-facing control (screens.md 6, 7). */
  size?: "default" | "large";
  fullWidth?: boolean;
  loading?: boolean;
  children: ReactNode;
}

/**
 * design-system.md section 8.
 *
 * Labels are verbs: `Post job`, `Approve for interview`. Never `Submit`.
 * That rule is not enforceable in code, so it lives in review.
 */
export function Button({
  level = "secondary",
  size = "default",
  fullWidth = false,
  loading = false,
  disabled = false,
  type = "button",
  children,
  ...rest
}: ButtonProps) {
  const classes = [
    "rb-button",
    `rb-button--${level}`,
    size === "large" ? "rb-button--large" : "",
    fullWidth ? "rb-button--full" : "",
    loading ? "rb-button--loading" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      {...rest}
      type={type}
      className={classes}
      // A loading button is not clickable, but it is also not "disabled" to
      // a screen reader - it is busy. aria-busy says so without the
      // disabled styling implying the action is unavailable.
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      <span className={loading ? "rb-button__label--loading" : undefined}>{children}</span>
      {loading && (
        <span className="rb-button__spinner">
          <Spinner size="sm" />
        </span>
      )}
    </button>
  );
}
