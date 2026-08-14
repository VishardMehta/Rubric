/*
 * Display formatting. Nothing here computes anything, it only renders what
 * the backend already sent.
 */

/** `4 Aug`. Used for posted, applied and completed dates (screens.md 1, 3, 4, 5). */
export function formatDayMonth(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(date);
}

/** `1:52`. Audio durations and elapsed recording time. */
export function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return "";
  const whole = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(whole / 60);
  return `${minutes}:${String(whole % 60).padStart(2, "0")}`;
}

/**
 * `answered in 9s`. Response time on an interview turn.
 *
 * Context, never a score (screens.md section 5), so it is never coloured
 * and never compared against a threshold.
 */
export function formatResponseTime(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return "";
  return `answered in ${Math.max(0, Math.round(seconds))}s`;
}

/** `01`, `02`. Turn numbers in the transcript, so they align in a column. */
export function formatSlot(slot: number): string {
  return String(slot).padStart(2, "0");
}
