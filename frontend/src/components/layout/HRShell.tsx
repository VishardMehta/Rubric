import { useState } from "react";
import type { ReactNode } from "react";
import { NavLink, Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { HRAccount } from "../../api/client";
import "./layout.css";

/**
 * design-system.md section 2 and 13.
 *
 * There is exactly one nav item for the MVP. Building a shell with five
 * placeholder links that lead nowhere is on the anti-pattern list, so when
 * a second section exists it gets added here and not before.
 *
 * `account` is optional so the shell still renders on the routes that have
 * no session, notably the not-found page, which is reachable while signed
 * out. When it is absent the profile block falls back to naming the local
 * workspace rather than showing an empty row where a person should be.
 */
export function HRShell({
  children,
  account,
}: {
  children: ReactNode;
  account?: HRAccount;
}) {
  const navigate = useNavigate();
  const [compact, setCompact] = useState(() => {
    try {
      return window.localStorage.getItem("rubric-hr-sidebar-compact") === "true";
    } catch {
      return false;
    }
  });

  async function signOut() {
    // The client clears the local token even if the server call fails, and
    // RequireHR is subscribed to that change, so the redirect happens
    // without this needing to navigate on its own. The explicit navigate
    // is for the case where the shell is rendered outside the gate.
    await api.logout();
    navigate("/signin", { replace: true });
  }

  function toggleSidebar() {
    setCompact((current) => {
      const next = !current;
      try {
        window.localStorage.setItem("rubric-hr-sidebar-compact", String(next));
      } catch {
        // A private browser session may reject storage. The toggle still works
        // for the current visit.
      }
      return next;
    });
  }

  return (
    <div className={`rb-hr-shell${compact ? " rb-hr-shell--compact" : ""}`}>
      <aside className="rb-hr-shell__sidebar" aria-label="Hiring workspace">
        <div className="rb-hr-shell__workspace-card">
          <Link to="/" className="rb-hr-shell__brand" aria-label="Rubric hiring workspace">
            <img src="/logo.png" alt="" className="rb-hr-shell__mark" />
            <span className="rb-hr-shell__brand-copy">
              <span className="rb-wordmark">Rubric</span>
              <span className="rb-hr-shell__workspace">Hiring workspace</span>
            </span>
          </Link>
          <button
            type="button"
            className="rb-hr-shell__collapse"
            onClick={toggleSidebar}
            aria-label={compact ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!compact}
          >
            <span aria-hidden="true">{compact ? "›" : "‹"}</span>
          </button>
        </div>
        <nav className="rb-hr-shell__nav" aria-label="Sections">
          <p className="rb-hr-shell__nav-label">Hiring</p>
          <SidebarLink to="/dashboard" label="Overview" icon="overview" />
          <SidebarLink to="/jobs" label="Jobs" icon="jobs" />
          <SidebarLink to="/candidates" label="Candidates" icon="candidates" />
          <SidebarLink to="/interviews" label="Interviews" icon="interviews" />
        </nav>
        <nav className="rb-hr-shell__utility" aria-label="Workspace settings">
          <SidebarLink to="/settings" label="Settings" icon="settings" />
        </nav>
        <div className="rb-hr-shell__profile" aria-label="Current workspace">
          <span className="rb-hr-shell__profile-mark" aria-hidden="true">
            {initial(account)}
          </span>
          <span className="rb-hr-shell__profile-copy">
            <span>{account?.name ?? "Rubric demo"}</span>
            <span>{account?.company ?? account?.email ?? "Local workspace"}</span>
          </span>
          {account && (
            <button
              type="button"
              className="rb-hr-shell__signout"
              onClick={signOut}
              title="Sign out"
              aria-label="Sign out"
            >
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path
                  d="M6 2.75H3.5a1 1 0 0 0-1 1v8.5a1 1 0 0 0 1 1H6M10 11l3-3-3-3M13 8H6.25"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
        </div>
      </aside>
      <main className="rb-hr-shell__main">
        <div className="rb-hr-shell__content">{children}</div>
      </main>
    </div>
  );
}

/** First letter of the account name, for the profile chip. */
function initial(account?: HRAccount): string {
  const source = account?.name?.trim() || account?.email?.trim() || "R";
  return source.charAt(0).toUpperCase();
}

function SidebarLink({
  to,
  label,
  icon,
}: {
  to: string;
  label: string;
  icon: "overview" | "jobs" | "candidates" | "interviews" | "settings";
}) {
  return (
    <NavLink
      to={to}
      end
      title={label}
      className={({ isActive }) => `rb-nav-item${isActive ? " rb-nav-item--active" : ""}`}
    >
      <SidebarIcon name={icon} />
      <span className="rb-nav-item__label">{label}</span>
    </NavLink>
  );
}

function SidebarIcon({ name }: { name: "overview" | "jobs" | "candidates" | "interviews" | "settings" }) {
  if (name === "overview") {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="1.75" y="1.75" width="4.75" height="4.75" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="9.5" y="1.75" width="4.75" height="4.75" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="1.75" y="9.5" width="4.75" height="4.75" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="9.5" y="9.5" width="4.75" height="4.75" rx="1" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }
  if (name === "candidates") {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="6" cy="5.25" r="2.25" stroke="currentColor" strokeWidth="1.5" />
        <path d="M1.75 13.5c.45-2.2 1.86-3.3 4.25-3.3s3.8 1.1 4.25 3.3M11.25 4.25a2.1 2.1 0 0 1 0 4M12 10.35c1.25.34 2 .97 2.25 1.9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "interviews") {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="2" y="2.5" width="12" height="11.5" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M5 1.5v2M11 1.5v2M4.5 6.25h7M6 9.25h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "settings") {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M6.4 1.9h3.2l.4 1.55 1.4.8 1.5-.45 1.6 2.75-1.1 1.1v1.7l1.1 1.1-1.6 2.75-1.5-.45-1.4.8-.4 1.55H6.4L6 12.6l-1.4-.8-1.5.45-1.6-2.75 1.1-1.1v-1.7L1.5 5.6l1.6-2.75 1.5.45 1.4-.8.4-1.55Z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
        <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect
        x="1.75"
        y="4.25"
        width="12.5"
        height="9.5"
        rx="1.5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M5.75 4V3.25a1 1 0 0 1 1-1h2.5a1 1 0 0 1 1 1V4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
