import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button, TextField } from "../../components/primitives";
import { api } from "../../api/client";
import { readCandidateSession, signInCandidate } from "../../lib/candidate-session";
import "./application.css";

/*
 * Candidate sign in.
 *
 * One screen, no register mode. The HR side needs one because an account
 * there owns rows; here the address is the identity, so the first sign in
 * and the hundredth are the same action.
 *
 * **This does not check the password.** There is no candidate account to
 * check it against: no server call is made, and the address is recorded
 * locally (`lib/candidate-session.ts`). The field is present because the
 * client asked for a login and a login without one reads as broken, and
 * the screen says what it is doing rather than implying a check it is not
 * performing.
 */

export function CandidateSignInPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const existing = readCandidateSession();
  const [email, setEmail] = useState(existing?.email ?? "");
  const [name, setName] = useState(existing?.name ?? "");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Whether the backend is running with its own bypass on. Not what makes
  // this screen accept anything, but worth showing in the same place: a
  // person demoing should see every bypass that is live at once.
  const [demoAuth, setDemoAuth] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((health) => !cancelled && setDemoAuth(Boolean(health.demo_auth)))
      // A backend that cannot be reached is reported by the portal when it
      // tries to load. Nothing useful to say here.
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const from = (location.state as { from?: string } | null)?.from ?? "/apply";

  function submit(event: FormEvent) {
    event.preventDefault();

    // The address is the lookup key for every application, so it is the one
    // thing worth validating. The password is not checked at all.
    const trimmed = email.trim();
    if (!trimmed) {
      setFieldErrors({ email: "Enter your email." });
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setFieldErrors({ email: "Enter a valid email address." });
      return;
    }

    setFieldErrors({});
    signInCandidate(trimmed, name);
    navigate(from, { replace: true });
  }

  return (
    <div className="rb-csignin">
      <div className="rb-csignin__panel">
        <Link to="/" className="rb-csignin__header" aria-label="Rubric">
          <img src="/logo.png" alt="" className="rb-csignin__mark" />
          <span className="rb-wordmark">Rubric</span>
        </Link>

        <h1 className="text-title-1 rb-csignin__title">Sign in to your applications.</h1>
        <p className="text-body rb-csignin__lede">
          Track where every application stands and start an interview when the
          hiring team invites you to one.
        </p>

        <p className="rb-csignin__demo" role="status">
          {demoAuth
            ? "Demo mode: any email and any password will sign you in, on both sides of the product."
            : "Demo sign in: your email identifies your applications. The password is not checked."}
        </p>

        <form className="rb-csignin__form" onSubmit={submit} noValidate>
          <TextField
            label="Email"
            type="email"
            value={email}
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            error={fieldErrors.email}
            help="Use the address you apply with, so your applications appear here."
            placeholder="you@example.com"
          />

          <TextField
            label="Your name"
            optional
            value={name}
            autoComplete="name"
            onChange={(event) => setName(event.target.value)}
            help="Fills in your application form so you do not type it twice."
          />

          <TextField
            label="Password"
            type="password"
            value={password}
            autoComplete="current-password"
            onChange={(event) => setPassword(event.target.value)}
          />

          <Button type="submit" level="primary">
            Sign in
          </Button>
        </form>

        <p className="text-caption rb-csignin__switch">
          Hiring team? <Link to="/signin">Sign in to your workspace</Link>
        </p>
      </div>
    </div>
  );
}
