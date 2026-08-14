import "./primitives.css";

interface SpinnerProps {
  size?: "sm" | "md";
  /** Screen-reader text. Omit inside a control that already has a label. */
  label?: string;
}

/**
 * design-system.md section 15: a spinner on its own is only acceptable for
 * operations under one second. Anything slower uses LoadingState, which
 * names the work actually being done.
 */
export function Spinner({ size = "md", label }: SpinnerProps) {
  return (
    <span className={`rb-spinner rb-spinner--${size}`} role={label ? "status" : undefined}>
      {label && <span className="rb-visually-hidden">{label}</span>}
    </span>
  );
}
