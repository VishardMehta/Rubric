import { useId, useRef, useState } from "react";
import type { DragEvent } from "react";
import { RESUME_MAX_BYTES } from "../../lib/heuristics";
import "./primitives.css";

interface FileDropzoneProps {
  /** The accepted file, or null. Owned by the parent so the submit button
   *  can gate on it existing. */
  value: File | null;
  onChange: (file: File | null) => void;
  /** A rejection the server found after upload - the image-only PDF case,
   *  which needs extraction to detect (screens.md section 6). Client-side
   *  rejections never reach here; they are resolved locally instead. */
  serverError?: string | null;
  disabled?: boolean;
}

const CLIENT_MESSAGES = {
  wrongType: "Rubric reads PDF resumes. Export yours as a PDF and try again.",
  tooLarge: "That file is over 5 MB. Try exporting it again at a smaller size.",
};

/**
 * screens.md section 6, "Resume upload states": idle, selected, rejected.
 *
 * Client-side validation covers type and size, since both are knowable
 * before any network call. The fourth case - a scanned, image-only PDF -
 * can only be found by extracting text, which happens server-side after
 * submit; that rejection arrives as `serverError` and reuses this same
 * rejected layout.
 */
export function FileDropzone({ value, onChange, serverError, disabled = false }: FileDropzoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();

  const error = clientError ?? serverError ?? null;

  function accept(file: File) {
    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setClientError(CLIENT_MESSAGES.wrongType);
      onChange(null);
      return;
    }
    if (file.size > RESUME_MAX_BYTES) {
      setClientError(CLIENT_MESSAGES.tooLarge);
      onChange(null);
      return;
    }
    setClientError(null);
    onChange(file);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    if (disabled) return;
    const file = event.dataTransfer.files[0];
    if (file) accept(file);
  }

  function handleRemove() {
    setClientError(null);
    onChange(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  if (value) {
    return (
      <div className="rb-dropzone rb-dropzone--selected">
        <span className="text-mono rb-dropzone__filename">{value.name}</span>
        <span className="text-caption rb-dropzone__filesize">{formatBytes(value.size)}</span>
        <button
          type="button"
          className="rb-dropzone__remove"
          onClick={handleRemove}
          disabled={disabled}
        >
          Remove
        </button>
      </div>
    );
  }

  return (
    <div>
      <div
        className={[
          "rb-dropzone",
          error ? "rb-dropzone--rejected" : "",
          dragActive ? "rb-dropzone--drag" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
      >
        <label htmlFor={inputId} className="rb-dropzone__label">
          <span className="text-body-strong rb-dropzone__prompt">
            Drop your resume here, or choose a file
          </span>
          <span
            className={`text-caption rb-dropzone__hint${
              error ? " rb-dropzone__hint--error" : ""
            }`}
          >
            {error ?? "PDF only, up to 5 MB"}
          </span>
        </label>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept="application/pdf"
          className="rb-visually-hidden"
          disabled={disabled}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) accept(file);
          }}
        />
      </div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}
