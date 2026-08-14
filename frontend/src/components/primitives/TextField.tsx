import { useId } from "react";
import type { InputHTMLAttributes } from "react";
import { FieldShell } from "./Field";
import type { FieldProps } from "./Field";
import "./primitives.css";

type TextFieldProps = FieldProps &
  Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "id">;

/** design-system.md section 9. 40px, hairline-strong, radius sm. */
export function TextField({ label, help, error, optional, ...rest }: TextFieldProps) {
  const id = useId();
  const messageId = `${id}-message`;

  return (
    <FieldShell
      label={label}
      help={help}
      error={error}
      optional={optional}
      htmlFor={id}
      describedById={messageId}
    >
      <input
        {...rest}
        id={id}
        className={`rb-input${error ? " rb-input--invalid" : ""}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={help || error ? messageId : undefined}
      />
    </FieldShell>
  );
}
