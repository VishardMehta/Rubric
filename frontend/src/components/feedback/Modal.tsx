import { useCallback, useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import "./feedback.css";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Right-aligned, primary last (design-system.md section 14). */
  actions?: ReactNode;
}

const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

/**
 * design-system.md section 14.
 *
 * Rubric uses a modal in exactly two places: reject confirmation, and the
 * microphone permission explainer. Both are questions. A modal that
 * displays information should have been a panel, so there is no
 * dismiss-only variant here.
 *
 * Clicking the scrim does not close it. Both uses are decisions - one
 * rejects a person, the other explains why the interview cannot start -
 * and a stray click beside the dialog should not answer either.
 */
export function Modal({ open, onClose, title, children, actions }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  const focusable = useCallback(
    () => Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []),
    [],
  );

  // Remember where focus came from, move it into the dialog, and put it
  // back on close. Losing focus to the top of the document after closing a
  // dialog strands a keyboard user.
  useEffect(() => {
    if (!open) return;

    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const first = focusable()[0] ?? dialogRef.current;
    first?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
      returnFocusRef.current?.focus();
    };
  }, [open, focusable]);

  useEffect(() => {
    if (!open) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      // Wrap Tab at both ends so focus cannot leave the dialog for the
      // page behind the scrim, which is inert to the eye but not to Tab.
      const items = focusable();
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || active === dialogRef.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [open, onClose, focusable]);

  if (!open) return null;

  return (
    <div className="rb-modal-scrim">
      <div
        ref={dialogRef}
        className="rb-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <h2 id={titleId} className="rb-modal__title">
          {title}
        </h2>
        <div className="rb-modal__body">{children}</div>
        {actions && <div className="rb-modal__actions">{actions}</div>}
      </div>
    </div>
  );
}
