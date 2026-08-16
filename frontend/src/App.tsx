import type { ReactNode } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { HRShell } from "./components/layout";
import { RequireHR } from "./components/layout/RequireHR";
import { RequireCandidate } from "./components/layout/RequireCandidate";
import type { CandidateSession } from "./lib/candidate-session";
import { ErrorState, ToastProvider } from "./components/feedback";
import { LandingPage } from "./routes/Landing";
import { SignInPage } from "./routes/hr/SignIn";
import { PrimitivesPage } from "./routes/dev/Primitives";
import { JobsPage } from "./routes/hr/Jobs";
import { CreateJobPage } from "./routes/hr/CreateJob";
import { JobDetailPage } from "./routes/hr/JobDetail";
import { CandidateDetailPage } from "./routes/hr/CandidateDetail";
import { InterviewResultPage } from "./routes/hr/InterviewResult";
import { HiringDirectoryPage, SettingsPage } from "./routes/hr/HiringDirectory";
import { ApplicationPage } from "./routes/candidate/Application";
import { CandidateSignInPage } from "./routes/candidate/CandidateSignIn";
import { CandidatePortalPage } from "./routes/candidate/CandidatePortal";
import { OpportunityDetailPage } from "./routes/candidate/OpportunityDetail";
import { ApplicationCompletePage } from "./routes/candidate/ApplicationComplete";
import { InterviewPage } from "./routes/candidate/Interview";
import { InterviewCompletePage } from "./routes/candidate/InterviewComplete";

/*
 * Route map: docs/product.md section 5.
 *
 * Routes appear here as their screens land, phase by phase. Screens that
 * do not exist yet are absent rather than stubbed - a placeholder route
 * makes a missing screen look built, and the implementation plan is
 * explicit that nothing gets built ahead of its spec.
 */
/*
 * Every HR page is the same two wrappers: verify the session, then render
 * inside the shell with the account it resolved. Spelling that out on each
 * route was how the shell and the guard drifted apart, so it is one helper
 * and each route names only its page.
 */
function hr(page: ReactNode) {
  return <RequireHR>{(account) => <HRShell account={account}>{page}</HRShell>}</RequireHR>;
}

/*
 * The candidate's own pages, which need to know whose they are.
 *
 * Only the two screens that are about this person: the portal, and the
 * form that submits under their address. Browsing a role and answering an
 * interview stay open, because both are reached from a link someone was
 * sent rather than from inside the product.
 */
function candidate(page: (session: CandidateSession) => ReactNode) {
  return <RequireCandidate>{page}</RequireCandidate>;
}

function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          {import.meta.env.DEV && (
            <Route
              path="/_primitives"
              element={
                <HRShell>
                  <PrimitivesPage />
                </HRShell>
              }
            />
          )}

          {/* Landing. Its own layout - not HRShell - and the only screen
              where marketing language belongs (screens.md section 0). */}
          <Route path="/" element={<LandingPage />} />

          {/* The only HR route outside the session gate, and outside the
              shell: the shell's navigation all requires a session. */}
          <Route path="/signin" element={<SignInPage />} />

          {/* HR. Every one of these requires a session and shows only the
              signed-in account's own roles and applicants. */}
          <Route path="/dashboard" element={hr(<JobsPage view="overview" />)} />
          <Route path="/jobs" element={hr(<JobsPage />)} />
          <Route path="/candidates" element={hr(<HiringDirectoryPage mode="candidates" />)} />
          <Route path="/interviews" element={hr(<HiringDirectoryPage mode="interviews" />)} />
          <Route path="/settings" element={hr(<SettingsPage />)} />
          <Route path="/jobs/new" element={hr(<CreateJobPage />)} />
          <Route path="/jobs/:jobId" element={hr(<JobDetailPage />)} />
          <Route
            path="/jobs/:jobId/candidates/:candidateId"
            element={hr(<CandidateDetailPage />)}
          />
          <Route
            path="/jobs/:jobId/candidates/:candidateId/interview"
            element={hr(<InterviewResultPage />)}
          />

          {/* Candidate sign in. Accepts any email with any password and
              keeps no server session: it identifies, it does not
              authenticate. See lib/candidate-session.ts. */}
          <Route path="/candidate/signin" element={<CandidateSignInPage />} />

          {/* Candidate application. The portal and the form know who is
              looking; the role page does not, because a role link is meant
              to be shareable (product.md section 5). */}
          <Route path="/apply" element={candidate((session) => <CandidatePortalPage session={session} />)} />
          <Route path="/opportunities/:jobId" element={<OpportunityDetailPage />} />
          <Route
            path="/apply/:jobId"
            element={candidate((session) => <ApplicationPage session={session} />)}
          />
          <Route path="/apply/:jobId/done" element={<ApplicationCompletePage />} />

          {/* Candidate interview. Unauthenticated, identified only by an
              opaque token (product.md section 5). The done route is listed
              before the token route is even reachable, because a completed
              link redirects into it rather than erroring. */}
          <Route path="/interview/:token" element={<InterviewPage />} />
          <Route path="/interview/:token/done" element={<InterviewCompletePage />} />

          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}

/** design-system.md section 17: what happened, why, what to do. */
function NotFound() {
  return (
    <HRShell>
      <ErrorState
        variant="blocking"
        title="That page does not exist"
        body="The link may be mistyped, or the job it pointed to may have been removed."
      />
    </HRShell>
  );
}

export default App;
