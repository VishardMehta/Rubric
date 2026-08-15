import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button, TextField } from "../../components/primitives";
import { ApiErrorState } from "../../components/feedback";
import { api, ApiError } from "../../api/client";
import "./hr.css";

/*
 * Sign in and register for the hiring workspace.
 *
 * One screen with two modes rather than two routes. The only difference
 * between them is two extra fields, and a separate /register route would
 * mean a second place to keep the layout and the error handling in sync.
 *
 * This is the only HR screen outside HRShell. The shell's navigation
 * points at pages that all require a session, so rendering it here would
 * show a sidebar where every link bounces straight back.
 */

type Mode = "signin" | "register";

const PASSWORD_MIN_LENGTH = 10;

export function SignInPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<Mode>("signin");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");

  // Whether the backend is running with the auth bypass on. A bypass the
  // person demoing cannot see is one they forget to turn off.
  const [demoAuth, setDemoAuth] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<unknown>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => !cancelled && setDemoAuth(Boolean(h.demo_auth)))
      // A backend that cannot be reached is reported by the form on
      // submit. Nothing useful to say here.
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // Where the guard sent them from, so signing in returns them to the page
  // they actually asked for rather than always to the dashboard.
  const from = (location.state as { from?: string } | null)?.from ?? "/jobs";

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!email.trim()) errors.email = "Enter your email.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errors.email = "Enter a valid email address.";
    }
    if (!password) errors.password = "Enter your password.";
    if (mode === "register") {
      if (!name.trim()) errors.name = "Enter your name.";
      // The length floor is skipped when the backend is not going to apply
      // it either. Enforcing it here while the server accepts anything
      // would block the demo on a rule nothing downstream is keeping.
      if (!demoAuth && password && password.length < PASSWORD_MIN_LENGTH) {
        errors.password = `Use at least ${PASSWORD_MIN_LENGTH} characters.`;
      }
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submitting || !validate()) return;

    setSubmitting(true);
    setFailure(null);
    try {
      if (mode === "register") {
        const session = await api.register({
          email: email.trim(),
          name: name.trim(),
          password,
          company: company.trim() || null,
        });
        // Only ever non-zero for the first account. Worth saying out loud:
        // otherwise the jobs that existed before accounts silently appear
        // under this login with no explanation of why.
        if (session.claimed_jobs > 0) {
          navigate(from, {
            replace: true,
            state: { claimedJobs: session.claimed_jobs },
          });
          return;
        }
      } else {
        await api.login(email.trim(), password);
      }
      navigate(from, { replace: true });
    } catch (cause) {
      // A wrong password is not an error state at the top of the page, it
      // is an answer to what was just typed. Everything else is.
      if (cause instanceof ApiError && cause.code === "invalid_credentials") {
        setFieldErrors({ password: cause.message });
      } else if (cause instanceof ApiError && cause.code === "email_already_registered") {
        setFieldErrors({ email: cause.message });
      } else if (cause instanceof ApiError && cause.code === "weak_password") {
        setFieldErrors({ password: cause.message });
      } else {
        setFailure(cause);
      }
    } finally {
      setSubmitting(false);
    }
  }

  function switchTo(next: Mode) {
    setMode(next);
    setFieldErrors({});
    setFailure(null);
  }

  const registering = mode === "register";

  return (
    <div className="rb-signin">
      <div className="rb-signin__panel">
        <header className="rb-signin__header">
          <img src="/logo.png" alt="" className="rb-signin__mark" />
          <span className="rb-wordmark">Rubric</span>
        </header>

        <h1 className="text-title-1 rb-signin__title">
          {registering ? "Create your workspace." : "Sign in to your workspace."}
        </h1>
        <p className="text-body rb-signin__lede">
          {registering
            ? "Your roles and applicants are visible only to this account."
            : "Continue to the roles you have posted."}
        </p>

        {demoAuth && (
          <p className="rb-signin__demo" role="status">
            Demo mode: any email and any password will sign you in.
          </p>
        )}

        {failure !== null && (
          <div className="rb-signin__failure">
            <ApiErrorState error={failure} title="That did not work" />
          </div>
        )}

        <form className="rb-signin__form" onSubmit={submit} noValidate>
          {registering && (
            <TextField
              label="Your name"
              value={name}
              autoComplete="name"
              onChange={(event) => setName(event.target.value)}
              error={fieldErrors.name}
            />
          )}

          <TextField
            label="Work email"
            type="email"
            value={email}
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            error={fieldErrors.email}
          />

          <TextField
            label="Password"
            type="password"
            value={password}
            autoComplete={registering ? "new-password" : "current-password"}
            onChange={(event) => setPassword(event.target.value)}
            error={fieldErrors.password}
            help={
              registering && !fieldErrors.password && !demoAuth
                ? `At least ${PASSWORD_MIN_LENGTH} characters. Length matters more than symbols.`
                : undefined
            }
          />

          {registering && (
            <TextField
              label="Company"
              optional
              value={company}
              autoComplete="organization"
              onChange={(event) => setCompany(event.target.value)}
            />
          )}

          <Button type="submit" level="primary" disabled={submitting}>
            {submitting
              ? registering
                ? "Creating workspace"
                : "Signing in"
              : registering
                ? "Create workspace"
                : "Sign in"}
          </Button>
        </form>

        <p className="text-caption rb-signin__switch">
          {registering ? "Already have a workspace? " : "First time here? "}
          <button type="button" onClick={() => switchTo(registering ? "signin" : "register")}>
            {registering ? "Sign in" : "Create one"}
          </button>
        </p>
      </div>
    </div>
  );
}
