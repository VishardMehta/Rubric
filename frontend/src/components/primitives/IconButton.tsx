import type { ButtonHTMLAttributes, ReactNode } from "react";
import "./primitives.css";

interface IconButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "aria-label"> {
  /** Required. An icon with no accessible name is an unlabelled control. */
  label: string;
  children: ReactNode;
}

export function IconButton({ label, children, type = "button", ...rest }: IconButtonProps) {
  return (
    <button {...rest} type={type} className="rb-icon-button" aria-label={label} title={label}>
      {children}
    </button>
  );
}
