import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import {
  onCandidateSessionChange,
  readCandidateSession,
} from "../../lib/candidate-session";
import type { CandidateSession } from "../../lib/candidate-session";

/*
 * Gate for the candidate's own pages: the portal and the application form.
 *
 * Not the same kind of gate as `RequireHR`. That one verifies a bearer
 * token against `/auth/me` because the server is the authority on whether
 * an HR session is live. There is no server-side candidate session at all
 * (see `lib/candidate-session.ts`), so there is nothing to verify and no
 * loading state to show: the answer is already in localStorage.
 *
 * Which means this keeps the flow coherent, it does not protect anything.
 * The pages behind it call unauthenticated endpoints that anyone can reach
 * directly, and those endpoints are written to carry nothing a stranger
 * should not see.
 *
 * Deliberately not applied to `/opportunities/:jobId` or `/interview/:token`.
 * A role link is meant to be shareable, and an interview link is already
 * its own credential; bouncing either to a sign in screen would break the
 * one path the candidate is actually given.
 */
export function RequireCandidate({
  children,
}: {
  children: (session: CandidateSession) => ReactNode;
}) {
  const location = useLocation();
  const [session, setSession] = useState<CandidateSession | null>(readCandidateSession);

  useEffect(
    () => onCandidateSessionChange(() => setSession(readCandidateSession())),
    [],
  );

  if (!session) {
    // `from` so signing in lands on the role they were trying to apply to
    // rather than dropping them at the top of the portal.
    return (
      <Navigate
        to="/candidate/signin"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }

  return <>{children(session)}</>;
}
