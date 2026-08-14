import { useId } from "react";
import type { TextareaHTMLAttributes } from "react";
import { FieldShell } from "./Field";
import type { FieldProps } from "./Field";
import "./primitives.css";

type TextAreaProps = FieldProps &
  Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className" | "id"> & {
    /** Starting height. The job description field starts at 200px
     *  (design-system.md section 9); everything else uses the 120px floor. */
    minHeight?: number;
  };

export function TextArea({
  label,
  help,
  error,
  optional,
  minHeight,
  style,
  ...rest
}: TextAreaProps) {
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
      <textarea
        {...rest}
        id={id}
        className={`rb-input rb-textarea${error ? " rb-input--invalid" : ""}`}
        style={minHeight ? { ...style, minHeight: `${minHeight}px` } : style}
        aria-invalid={error ? true : undefined}
        aria-describedby={help || error ? messageId : undefined}
      />
    </FieldShell>
  );
}
