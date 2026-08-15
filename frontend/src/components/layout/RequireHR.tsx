import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { LoadingState } from "../feedback";
import { api } from "../../api/client";
import type { HRAccount } from "../../api/client";
import { onSessionChange, readToken } from "../../lib/session";

/*
 * Gate for every HR route.
 *
 * A stored token is not proof of a live session: it may have expired, been
 * signed out from another tab, or belong to an account that no longer
 * exists. So this verifies once against /auth/me rather than trusting what
 * is in localStorage, and shows a loading state while it does.
 *
 * The alternative, rendering the page immediately and letting the first
 * data call 401, flashes a broken dashboard before redirecting. That reads
 * as a bug even though it recovers.
 *
 * This is deliberately not a route-level `loader`. The account is needed by
 * the shell as well, so it is fetched here and handed down.
 */

type State =
  | { status: "checking" }
  | { status: "signed-in"; account: HRAccount }
  | { status: "signed-out" };

export function RequireHR({ children }: { children: (account: HRAccount) => ReactNode }) {
  const location = useLocation();
  const [state, setState] = useState<State>(() =>
    readToken() ? { status: "checking" } : { status: "signed-out" },
  );

  useEffect(() => {
    let cancelled = false;

    function check() {
      if (!readToken()) {
        setState({ status: "signed-out" });
        return;
      }
      api
        .me()
        .then((account) => !cancelled && setState({ status: "signed-in", account }))
        // The client already dropped the token on a 401, so there is
        // nothing to clean up here beyond re-rendering as signed out.
        .catch(() => !cancelled && setState({ status: "signed-out" }));
    }

    check();
    // Signing out in this tab, or the token being dropped by a 401 from
    // any other screen, re-runs the check rather than leaving a stale
    // signed-in view on screen.
    const unsubscribe = onSessionChange(check);
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  if (state.status === "checking") {
    return (
      <div className="rb-route-gate">
        <LoadingState label="Opening your workspace" block />
      </div>
    );
  }

  if (state.status === "signed-out") {
    // `from` so signing in returns them to the page they asked for.
    return <Navigate to="/signin" replace state={{ from: location.pathname }} />;
  }

  return <>{children(state.account)}</>;
}
