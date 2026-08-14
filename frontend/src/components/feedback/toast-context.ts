import { createContext, useContext } from "react";

export interface ToastContextValue {
  /** Confirms something that already happened. Never asks a question. */
  show: (message: string) => void;
}

export const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used inside a ToastProvider");
  return value;
}
