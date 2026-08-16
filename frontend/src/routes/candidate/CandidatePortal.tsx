import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiErrorState, EmptyState, LoadingState } from "../../components/feedback";
import { Button, Chip, TextField } from "../../components/primitives";
import { api } from "../../api/client";
import type { CandidateApplication, PublicJobSummary } from "../../api/client";
import { formatDayMonth } from "../../lib/format";
import { signOutCandidate } from "../../lib/candidate-session";
import type { CandidateSession } from "../../lib/candidate-session";
import "./application.css";

export function CandidatePortalPage({ session }: { session: CandidateSession }) {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<PublicJobSummary[] | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [query, setQuery] = useState("");
  // Applications come from the server, keyed on the address this person
  // signed in with. Two things this replaced: a localStorage list capped at
  // eight that showed a hardcoded "Submitted" chip and could never receive
  // an interview link, and then an email box on this screen that made
  // someone type an address the app was already holding.
  const email = session.email;
  const [applications, setApplications] = useState<CandidateApplication[] | null>(null);
  const [applicationsFailure, setApplicationsFailure] = useState<unknown>(null);
  const [view, setView] = useState<"explore" | "applications">("explore");
  const [experienceFilter, setExperienceFilter] = useState<"all" | "early" | "experienced">("all");

  // Keyed on the address: the server flags each role with whether this
  // person has already applied to it, which is what Explore filters on.
  useEffect(() => {
    let cancelled = false;
    api
      .listPublicJobs(email)
      .then((loaded) => !cancelled && setJobs(loaded))
      .catch((cause) => !cancelled && setFailure(cause));
    return () => {
      cancelled = true;
    };
  }, [email]);

  // Loaded on arrival rather than on a button, because the address is
  // already known. The count in the navigation depends on it too, so it
  // cannot wait for the applications tab to be opened.
  useEffect(() => {
    let cancelled = false;
    setApplications(null);
    setApplicationsFailure(null);
    api
      .listApplications(email)
      .then((rows) => !cancelled && setApplications(rows))
      .catch((cause) => !cancelled && setApplicationsFailure(cause));
    return () => {
      cancelled = true;
    };
  }, [email]);

  /*
   * Explore is what is still open to this person.
   *
   * A role they have already applied to is not an opportunity, it is an
   * application, and it lives on the other tab. Applying again is refused
   * by the database anyway - the unique constraint on (job_id, email) -
   * so leaving it on this list only offers a button that cannot work.
   *
   * `applied` is decided by the server from that same relationship, not
   * tracked here, so the two tabs cannot disagree about which is which.
   */
  const openJobs = useMemo(() => (jobs ?? []).filter((job) => !job.applied), [jobs]);

  const visibleJobs = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const searchable = (job: PublicJobSummary) =>
      [job.title, job.description, job.experience, ...job.skills]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
    const EARLY_CAREER = /(intern|graduate|junior|0 to|0-|1 year|2 year)/;

    return openJobs.filter((job) => {
      const content = searchable(job);
      const experienceMatches =
        experienceFilter === "all" ||
        (experienceFilter === "early" && EARLY_CAREER.test(content)) ||
        (experienceFilter === "experienced" && !EARLY_CAREER.test(content));
      // The filter used to be skipped entirely on an empty search box, so
      // choosing "Early career" with nothing typed did nothing at all.
      return experienceMatches && (!normalized || content.includes(normalized));
    });
  }, [openJobs, query, experienceFilter]);

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
        <div className="rb-candidate-topbar__right">
          <div className="rb-candidate-topbar__account">
            <span className="rb-candidate-topbar__account-email" title={session.email}>
              {session.name ?? session.email}
            </span>
            <button
              type="button"
              className="rb-candidate-topbar__signout"
              onClick={() => {
                signOutCandidate();
                navigate("/candidate/signin", { replace: true });
              }}
            >
              Sign out
            </button>
          </div>
        </div>
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
              : "Every role you have applied to, where it stands, and your interview link once the hiring team sends one."}
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
            {jobs && (
              <p className="text-caption">
                {openJobs.length} role{openJobs.length === 1 ? "" : "s"} open to you
              </p>
            )}
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
          {!failure && jobs && openJobs.length === 0 && (
            <EmptyState
              title={
                jobs.length === 0
                  ? "No open roles right now"
                  : "You have applied to every open role"
              }
              body={
                jobs.length === 0
                  ? "The hiring team has not published any roles yet. Check back soon."
                  : "Nothing new to apply to yet. Track the ones you have sent under My applications."
              }
              action={
                jobs.length > 0 ? (
                  <Button level="secondary" onClick={() => setView("applications")}>
                    My applications
                  </Button>
                ) : undefined
              }
            />
          )}
          {!failure && openJobs.length > 0 && visibleJobs.length === 0 && (
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

            {/* The signed-in address is in the top bar and does not need
                repeating here. Applications are still looked up by it;
                nothing on this screen carries a score, because the
                candidate never sees one (product.md section 2). */}

            {applicationsFailure !== null && (
              <ApiErrorState error={applicationsFailure} title="Applications could not be loaded" />
            )}

            {!applicationsFailure && applications === null && (
              <LoadingState label="Loading your applications" block />
            )}

            {!applicationsFailure && applications?.length === 0 && (
              <EmptyState
                inline
                title="You have not applied to anything yet"
                body="Browse the open roles and apply. Every application you send shows up here with its status."
                action={
                  <Button level="secondary" onClick={() => setView("explore")}>
                    Explore jobs
                  </Button>
                }
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
        {/* The role is still readable after applying. It leaves Explore,
            which is what is still open to them, and stays reachable from
            the application it produced. */}
        <Link to={`/opportunities/${application.job_id}`} className="rb-applications__role-link">
          View role
        </Link>
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
