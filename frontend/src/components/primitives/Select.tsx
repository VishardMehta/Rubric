import { useId } from "react";
import type { SelectHTMLAttributes } from "react";
import { FieldShell } from "./Field";
import type { FieldProps } from "./Field";
import "./primitives.css";

interface Option {
  value: string;
  label: string;
}

type SelectProps = FieldProps &
  Omit<SelectHTMLAttributes<HTMLSelectElement>, "className" | "id" | "children"> & {
    options: Option[];
    placeholder?: string;
  };

/**
 * A real `<select>`.
 *
 * A custom listbox would need type-ahead, roving focus and screen reader
 * work to reach what the native element already does, and Rubric has one
 * select in the whole product (experience level on Create Job). The only
 * customisation is the chevron, because the platform one cannot be
 * restyled to match the hairline treatment.
 */
export function Select({
  label,
  help,
  error,
  optional,
  options,
  placeholder,
  ...rest
}: SelectProps) {
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
      <span className="rb-select-wrap">
        <select
          {...rest}
          id={id}
          className={`rb-input rb-select${error ? " rb-input--invalid" : ""}`}
          aria-invalid={error ? true : undefined}
          aria-describedby={help || error ? messageId : undefined}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <svg
          className="rb-select-wrap__chevron"
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M3 4.5 6 7.5 9 4.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    </FieldShell>
  );
}
