import { useId, useState } from "react";
import type { KeyboardEvent } from "react";
import { FieldShell } from "./Field";
import type { FieldProps } from "./Field";
import "./primitives.css";

type TagInputProps = FieldProps & {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
};

/**
 * design-system.md section 9. Type, press Enter or comma, get a chip.
 *
 * Chips are `surface-sunken` with `ink` text: skills are data, not
 * actions, so they never take the accent.
 *
 * Committing on blur is deliberate. Someone who types a last skill and
 * clicks `Post job` without pressing Enter means to include it, and
 * silently dropping it would change the rubric that gets generated.
 */
export function TagInput({
  label,
  help,
  error,
  optional,
  value,
  onChange,
  placeholder,
  disabled = false,
}: TagInputProps) {
  const id = useId();
  const messageId = `${id}-message`;
  const [draft, setDraft] = useState("");

  function commit(raw: string) {
    const tag = raw.trim();
    if (!tag) return;
    // Case-insensitive de-duplication, but the first spelling is kept:
    // "PostgreSQL" typed first should not be overwritten by "postgresql".
    const exists = value.some((existing) => existing.toLowerCase() === tag.toLowerCase());
    if (!exists) onChange([...value, tag]);
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      // Enter inside a form would submit it; a skill is not a submission.
      event.preventDefault();
      commit(draft);
      return;
    }
    if (event.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <FieldShell
      label={label}
      help={help}
      error={error}
      optional={optional}
      htmlFor={id}
      describedById={messageId}
    >
      <div className={`rb-input rb-taginput${error ? " rb-input--invalid" : ""}`}>
        {value.map((tag) => (
          <span key={tag} className="rb-taginput__tag">
            {tag}
            <button
              type="button"
              className="rb-taginput__remove"
              onClick={() => onChange(value.filter((item) => item !== tag))}
              aria-label={`Remove ${tag}`}
              disabled={disabled}
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
                <path
                  d="M2 2l6 6M8 2l-6 6"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </span>
        ))}
        <input
          id={id}
          className="rb-taginput__input"
          value={draft}
          disabled={disabled}
          placeholder={value.length === 0 ? placeholder : undefined}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => commit(draft)}
          aria-invalid={error ? true : undefined}
          aria-describedby={help || error ? messageId : undefined}
        />
      </div>
    </FieldShell>
  );
}
