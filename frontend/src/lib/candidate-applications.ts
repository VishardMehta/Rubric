/*
 * The candidate's remembered email.
 *
 * This file used to be the entire application history: a localStorage list
 * capped at eight entries, showing a hardcoded "Submitted" chip that never
 * reflected the real state and could never receive anything from the
 * hiring team. Clearing site data erased it, and a ninth application
 * silently pushed out the first.
 *
 * The applications themselves now come from `GET /api/applications`, keyed
 * on the email the person applied with. All that is kept locally is that
 * email, so a returning candidate does not have to type it every visit.
 * Nothing here is a credential: the address is only a lookup key, and the
 * response carries no score.
 */

const EMAIL_KEY = "rubric-candidate-email";

export function readRememberedEmail(): string {
  try {
    return window.localStorage.getItem(EMAIL_KEY) ?? "";
  } catch {
    return "";
  }
}

export function rememberEmail(email: string): void {
  try {
    window.localStorage.setItem(EMAIL_KEY, email.trim());
  } catch {
    // A private session can refuse storage. The lookup still works for
    // this visit; only the convenience is lost.
  }
}

export function forgetEmail(): void {
  try {
    window.localStorage.removeItem(EMAIL_KEY);
  } catch {
    // Nothing to do.
  }
}
