import type { ReactNode } from "react";
import "./primitives.css";

export interface FieldProps {
  /** Always rendered. design-system.md section 9: placeholder is never the label. */
  label: string;
  /** Below the field. Replaced by `error` when one is present. */
  help?: string;
  error?: string;
  optional?: boolean;
}

interface FieldShellProps extends FieldProps {
  htmlFor: string;
  describedById: string;
  children: ReactNode;
}

/**
 * The label/control/message wrapper shared by every input.
 *
 * The error message replaces the helper text rather than appearing under
 * it, so a form does not grow taller the moment it is validated and push
 * the fields the user is reading. Validation runs on blur, not on submit
 * (design-system.md section 9).
 */
export function FieldShell({
  label,
  help,
  error,
  optional = false,
  htmlFor,
  describedById,
  children,
}: FieldShellProps) {
  const message = error ?? help;

  return (
    <div className="rb-field">
      <label className="rb-field__label" htmlFor={htmlFor}>
        {label}
        {optional && <span className="rb-field__optional"> (optional)</span>}
      </label>
      {children}
      {message && (
        <span
          id={describedById}
          className={error ? "rb-field__error" : "rb-field__help"}
          // Announced when it appears, but never interrupting: the user is
          // usually still typing in the next field by then.
          role={error ? "alert" : undefined}
        >
          {message}
        </span>
      )}
    </div>
  );
}
