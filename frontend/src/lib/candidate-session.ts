/*
 * The signed-in candidate.
 *
 * Read this before trusting it: **there are no candidate accounts on the
 * server.** `GET /api/applications` is still an unauthenticated lookup by
 * email address, exactly as documented in `backend/app/api/applications.py`.
 * This module is the demo sign in the client asked for, and it is entirely
 * client side: the sign in screen accepts any email with any password and
 * records the address here.
 *
 * So this is a convenience, not a security boundary. It exists to answer
 * "who is looking at this page" so the portal can show someone their
 * applications without asking them to type their address every visit, and
 * so the application form can submit under the address they signed in with.
 * Anyone can still query anyone's applications with a URL, which is why the
 * response carries no score, no band and no recommendation.
 *
 * Real candidate accounts would need a password reset, which needs email
 * delivery, which is out of scope (product.md section 7). The shape here
 * deliberately mirrors `lib/session.ts` so a server-backed version can
 * replace the internals without touching a screen.
 */

import { forgetEmail, readRememberedEmail, rememberEmail } from "./candidate-applications";

const SESSION_KEY = "rubric-candidate-session";

export interface CandidateSession {
  email: string;
  /** From the sign in form or the last application submitted. Null when
   *  neither has supplied one, which is why every caller has a fallback. */
  name: string | null;
}

type Listener = () => void;
const listeners = new Set<Listener>();

export function readCandidateSession(): CandidateSession | null {
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<CandidateSession>;
      if (typeof parsed.email === "string" && parsed.email.trim()) {
        return {
          email: parsed.email.trim(),
          name: typeof parsed.name === "string" && parsed.name.trim() ? parsed.name.trim() : null,
        };
      }
    }
  } catch {
    // A private session can refuse storage, and a half-written value is
    // not worth crashing the app over. Fall through to the older key.
  }

  // Someone who used the email lookup before this screen existed is
  // already identified. Promote that address rather than making them sign
  // in again for an identity we are already holding.
  const remembered = readRememberedEmail().trim();
  return remembered ? { email: remembered, name: null } : null;
}

export function signInCandidate(email: string, name?: string | null): CandidateSession {
  const session: CandidateSession = {
    email: email.trim(),
    name: name?.trim() ? name.trim() : null,
  };
  try {
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    // The session still holds for this tab through the listeners below.
    // It just will not survive a reload.
  }
  // Kept in step so the two stores cannot disagree about who this is.
  rememberEmail(session.email);
  listeners.forEach((listener) => listener());
  return session;
}

export function signOutCandidate(): void {
  try {
    window.localStorage.removeItem(SESSION_KEY);
  } catch {
    // Nothing to do. The listeners still fire, so the UI returns to the
    // signed-out state either way.
  }
  // Without this the promotion above would sign them straight back in.
  forgetEmail();
  listeners.forEach((listener) => listener());
}

export function onCandidateSessionChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
