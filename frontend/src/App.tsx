import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { HRShell } from "./components/layout";
import { ErrorState, ToastProvider } from "./components/feedback";
import { PrimitivesPage } from "./routes/dev/Primitives";
import { JobsPage } from "./routes/hr/Jobs";
import { CreateJobPage } from "./routes/hr/CreateJob";
import { ApplicationPage } from "./routes/candidate/Application";
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
 *
 * Landing on `/` arrives in Phase 9. Until then `/` sends developers to
 * the primitives page, and a production build has nothing to serve there.
 */
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

          {/* HR. No authentication in the MVP - a stated decision for a
              localhost demo, recorded in the README. */}
          <Route path="/" element={<Navigate to="/jobs" replace />} />
          <Route
            path="/jobs"
            element={
              <HRShell>
                <JobsPage />
              </HRShell>
            }
          />
          <Route
            path="/jobs/new"
            element={
              <HRShell>
                <CreateJobPage />
              </HRShell>
            }
          />

          {/* Candidate application. Unauthenticated, identified only by a
              job id (product.md section 5). */}
          <Route path="/apply/:jobId" element={<ApplicationPage />} />
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
