/*
 * Where the HR bearer token lives.
 *
 * localStorage, not a cookie. The backend's CORS is configured with
 * `allow_credentials=false` and pinned origins, so a cookie would not be
 * sent cross-origin without loosening that, and an Authorization header
 * already passes through the existing `allow_headers` rule.
 *
 * The trade this makes: anything that can run a script on the page can
 * read the token. For a localhost demo with no third-party scripts that
 * is acceptable, and it is written down in the README rather than left
 * for someone to discover.
 *
 * Every read and write is wrapped, because a private browsing session can
 * refuse storage entirely and a thrown SecurityError here would take the
 * whole app down on load.
 */

const TOKEN_KEY = "rubric-hr-token";

/** Notified when the token changes, so the app can re-render as signed out. */
type Listener = () => void;
const listeners = new Set<Listener>();

export function readToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function writeToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // The session still works for this tab; it just will not survive a
    // reload. Better than refusing to sign in at all.
  }
  listeners.forEach((listener) => listener());
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing to do. The in-memory listeners below still fire, so the UI
    // returns to the signed-out state either way.
  }
  listeners.forEach((listener) => listener());
}

export function onSessionChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
