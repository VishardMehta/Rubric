import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiErrorState, EmptyState, LoadingState } from "../../components/feedback";
import { Button, Chip, TextField } from "../../components/primitives";
import { api } from "../../api/client";
import type { CandidateApplication, PublicJobSummary } from "../../api/client";
import { formatDayMonth } from "../../lib/format";
import { readRememberedEmail, rememberEmail } from "../../lib/candidate-applications";
import "./application.css";

export function CandidatePortalPage() {
  const [jobs, setJobs] = useState<PublicJobSummary[] | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [query, setQuery] = useState("");
  // Applications come from the server now, keyed on the email the person
  // applied with. The old version was a localStorage list capped at eight
  // that showed a hardcoded "Submitted" chip and could never receive an
  // interview link from the hiring team.
  const [email, setEmail] = useState(() => readRememberedEmail());
  const [lookupEmail, setLookupEmail] = useState(() => readRememberedEmail());
  const [applications, setApplications] = useState<CandidateApplication[] | null>(null);
  const [applicationsFailure, setApplicationsFailure] = useState<unknown>(null);
  const [view, setView] = useState<"explore" | "applications">("explore");
  const [experienceFilter, setExperienceFilter] = useState<"all" | "early" | "experienced">("all");

  useEffect(() => {
    let cancelled = false;
    api
      .listPublicJobs()
      .then((loaded) => !cancelled && setJobs(loaded))
      .catch((cause) => !cancelled && setFailure(cause));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!lookupEmail.trim()) {
      setApplications(null);
      return;
    }
    let cancelled = false;
    setApplicationsFailure(null);
    api
      .listApplications(lookupEmail.trim())
      .then((rows) => !cancelled && setApplications(rows))
      .catch((cause) => !cancelled && setApplicationsFailure(cause));
    return () => {
      cancelled = true;
    };
  }, [lookupEmail]);

  const visibleJobs = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized || !jobs) return jobs ?? [];
    return jobs.filter((job) => {
      const content = [job.title, job.description, job.experience, ...job.skills]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const experienceMatches = experienceFilter === "all"
        || (experienceFilter === "early" && /(intern|graduate|junior|0 to|0–|1 year|2 year)/.test(content))
        || (experienceFilter === "experienced" && !/(intern|graduate|junior|0 to|0–|1 year|2 year)/.test(content));
      return experienceMatches &&
      [job.title, job.description, job.experience, ...job.skills]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(normalized);
    });
  }, [jobs, query, experienceFilter]);

  return (
    <div className="rb-candidate-portal-shell">
      <header className="rb-candidate-topbar">
        <Link to="/" className="rb-candidate-topbar__brand" aria-label="Rubric">
          <img src="/logo.png" alt="" />
          <strong>Rubric</strong>
        </Link>
        <nav className="rb-candidate-topbar__nav" aria-label="Candidate portal">
          <button
            type="button"
            className={view === "explore" ? "rb-candidate-topbar__nav-item rb-candidate-topbar__nav-item--active" : "rb-candidate-topbar__nav-item"}
            onClick={() => setView("explore")}
          >
            Explore jobs
          </button>
          <button
            type="button"
            className={view === "applications" ? "rb-candidate-topbar__nav-item rb-candidate-topbar__nav-item--active" : "rb-candidate-topbar__nav-item"}
            onClick={() => setView("applications")}
          >
            My applications{applications && applications.length > 0 ? ` (${applications.length})` : ""}
          </button>
        </nav>
        <label className="rb-candidate-topbar__search">
          <span className="rb-visually-hidden">Search roles</span>
          <span aria-hidden="true">⌕</span>
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setView("explore");
            }}
            placeholder="Search roles or skills"
          />
        </label>
      </header>
      <main className="rb-candidate-portal-main">
      <div className="rb-opportunities">
        <header className="rb-opportunities__header">
          <p className="text-label rb-opportunities__eyebrow">Candidate portal</p>
          <h1 className="text-title-1 rb-opportunities__title">
            {view === "explore" ? "Find work worth doing." : "Keep your search in view."}
          </h1>
          <p className="text-body-lg rb-opportunities__body">
            {view === "explore"
              ? "Explore open roles, understand what each team is looking for, and apply when you are ready."
              : "Enter the email you applied with to see where each application stands."}
          </p>
        </header>

        {view === "explore" && <section className="rb-opportunities__browse" aria-labelledby="open-roles-heading">
          <div className="rb-opportunities__browse-head">
            <div>
              <p className="text-label rb-opportunities__section-label">Open opportunities</p>
              <h2 id="open-roles-heading" className="text-title-3 rb-opportunities__section-title">
                Recommended roles
              </h2>
            </div>
            {jobs && <p className="text-caption">{jobs.length} role{jobs.length === 1 ? "" : "s"} open</p>}
          </div>

          <div className="rb-opportunities__controls">
            <TextField
              label="Search roles"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search title, skill, or experience"
            />
            <label className="rb-opportunities__filter">
              <span>Experience</span>
              <select value={experienceFilter} onChange={(event) => setExperienceFilter(event.target.value as typeof experienceFilter)}>
                <option value="all">All levels</option>
                <option value="early">Early career</option>
                <option value="experienced">Experienced</option>
              </select>
            </label>
          </div>

          {failure !== null && <ApiErrorState error={failure} title="Roles could not be loaded" />}
          {!failure && jobs === null && <LoadingState label="Loading open roles" block />}
          {!failure && jobs?.length === 0 && (
            <EmptyState
              title="No open roles right now"
              body="The hiring team has not published any roles yet. Check back soon."
            />
          )}
          {!failure && jobs && jobs.length > 0 && visibleJobs.length === 0 && (
            <EmptyState
              inline
              title="No roles match that search"
              body="Try a broader skill or role title."
            />
          )}
          {!failure && visibleJobs.length > 0 && (
            <div className="rb-opportunities__list">
              {visibleJobs.map((job) => <OpportunityCard key={job.id} job={job} />)}
            </div>
          )}
        </section>}

        {view === "applications" && (
          <section className="rb-opportunities__applications" aria-labelledby="application-status-heading">
            <div>
              <p className="text-label rb-opportunities__section-label">Your activity</p>
              <h2 id="application-status-heading" className="text-title-3 rb-opportunities__section-title">
                Your applications
              </h2>
            </div>

            {/* An email, not a login. There are no candidate accounts: a
                password would need a reset flow, which would need email
                delivery, which is out of scope. The address is only a
                lookup key, and nothing it returns carries a score. */}
            <form
              className="rb-applications__lookup"
              onSubmit={(event) => {
                event.preventDefault();
                const next = email.trim();
                setLookupEmail(next);
                rememberEmail(next);
              }}
            >
              <TextField
                label="Email you applied with"
                type="email"
                value={email}
                autoComplete="email"
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
              />
              <Button type="submit" level="primary">
                Show my applications
              </Button>
            </form>

            {applicationsFailure !== null && (
              <ApiErrorState error={applicationsFailure} title="Applications could not be loaded" />
            )}

            {!applicationsFailure && lookupEmail.trim() && applications === null && (
              <LoadingState label="Looking up your applications" block />
            )}

            {!applicationsFailure && !lookupEmail.trim() && (
              <EmptyState
                inline
                title="Enter your email to continue"
                body="Applications are looked up by the address you applied with."
              />
            )}

            {!applicationsFailure && applications?.length === 0 && (
              <EmptyState
                inline
                title="No applications for that email"
                body="Check the address, or browse the open roles and apply."
              />
            )}

            {!applicationsFailure && applications && applications.length > 0 && (
              <ul className="rb-applications__list">
                {applications.map((application) => (
                  <ApplicationRow key={application.candidate_id} application={application} />
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
      </main>
    </div>
  );
}

/*
 * One application and where it stands.
 *
 * Carries no score, no band and no recommendation, because the candidate
 * never sees one (product.md section 2). A closed application says it is
 * closed and stops; it does not explain why, and there is no number behind
 * the words on this screen to explain it with.
 */
function ApplicationRow({ application }: { application: CandidateApplication }) {
  const ready =
    application.status === "interview_ready" || application.status === "interview_in_progress";

  return (
    <li className="rb-applications__row">
      <div className="rb-applications__main">
        <strong>{application.job_title}</strong>
        <small>Applied {formatDayMonth(application.applied_at)}</small>
        <p className="rb-applications__detail">{application.status_detail}</p>
      </div>
      <div className="rb-applications__aside">
        {/* Neutral throughout. A status is not a verdict, and colouring
            "Closed" red would tell the candidate something the product
            deliberately does not. */}
        <Chip tone="neutral">{application.status_label}</Chip>
        {ready && application.interview_url && (
          <Link to={application.interview_url} className="rb-applications__cta">
            {application.status === "interview_in_progress" ? "Resume interview" : "Start interview"}
          </Link>
        )}
      </div>
    </li>
  );
}

function OpportunityCard({ job }: { job: PublicJobSummary }) {
  const summary = job.description.length > 180 ? `${job.description.slice(0, 177).trim()}…` : job.description;
  return (
    <article className="rb-opportunity-card">
      <div className="rb-opportunity-card__main">
        <div className="rb-opportunity-card__title-row">
          <h3>{job.title}</h3>
          <span className="text-caption">Posted {formatDayMonth(job.created_at)}</span>
        </div>
        <p>{summary}</p>
        <div className="rb-opportunity-card__meta">
          {job.experience && <span>{job.experience} experience</span>}
          {job.skills.slice(0, 4).map((skill) => <Chip key={skill}>{skill}</Chip>)}
        </div>
      </div>
      <Link to={`/opportunities/${job.id}`} className="rb-opportunity-card__action">
        View role <span aria-hidden="true">→</span>
      </Link>
    </article>
  );
}
