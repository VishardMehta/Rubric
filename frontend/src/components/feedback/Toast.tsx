import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ToastContext } from "./toast-context";
import "./feedback.css";

interface ToastItem {
  id: number;
  message: string;
}

const DISMISS_AFTER_MS = 4000;

/**
 * Transient confirmation of a completed action: `Interview link copied`.
 *
 * Toasts never carry an error. An error needs somewhere to stay while the
 * user decides what to do about it, and something that disappears after
 * four seconds is not that place - see ErrorState instead.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);
  const timers = useRef<number[]>([]);

  const show = useCallback((message: string) => {
    const id = nextId.current++;
    setToasts((current) => [...current, { id, message }]);
    const timer = window.setTimeout(
      () => setToasts((current) => current.filter((toast) => toast.id !== id)),
      DISMISS_AFTER_MS,
    );
    timers.current.push(timer);
  }, []);

  // Unmounting mid-timeout would otherwise set state on a gone component.
  useEffect(() => () => timers.current.forEach(window.clearTimeout), []);

  const value = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="rb-toast-region" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className="rb-toast">
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
