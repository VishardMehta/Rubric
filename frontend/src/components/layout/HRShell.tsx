import type { ReactNode } from "react";
import { NavLink, Link } from "react-router-dom";
import "./layout.css";

/**
 * design-system.md section 2 and 13.
 *
 * There is exactly one nav item for the MVP. Building a shell with five
 * placeholder links that lead nowhere is on the anti-pattern list, so when
 * a second section exists it gets added here and not before.
 */
export function HRShell({ children }: { children: ReactNode }) {
  return (
    <div className="rb-hr-shell">
      <aside className="rb-hr-shell__sidebar">
        <Link to="/jobs" className="rb-wordmark">
          Rubric
        </Link>
        <nav className="rb-hr-shell__nav" aria-label="Sections">
          <NavLink
            to="/jobs"
            className={({ isActive }) =>
              `rb-nav-item${isActive ? " rb-nav-item--active" : ""}`
            }
          >
            <JobsIcon />
            <span className="rb-nav-item__label">Jobs</span>
          </NavLink>
        </nav>
      </aside>
      <main className="rb-hr-shell__main">
        <div className="rb-hr-shell__content">{children}</div>
      </main>
    </div>
  );
}

/** Visible only at medium width, where the sidebar is icons alone. */
function JobsIcon() {
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
