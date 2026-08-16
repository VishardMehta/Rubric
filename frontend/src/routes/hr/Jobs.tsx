import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageHeader } from "../../components/layout";
import { Button, Chip } from "../../components/primitives";
import { ApiErrorState, EmptyState, LoadingState } from "../../components/feedback";
import { api } from "../../api/client";
import type { JobSummary } from "../../api/client";
import { formatDayMonth } from "../../lib/format";
import "./hr.css";

/*
 * screens.md section 1. Every job and its pipeline at a glance.
 *
 * Sorted by posted date descending, with no sort controls: the MVP has one
 * ordering and a column header that does nothing is worse than no control
 * at all.
 */

export function JobsPage({ view = "jobs" }: { view?: "overview" | "jobs" }) {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [failure, setFailure] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listJobs()
      .then((loaded) => {
        if (cancelled) return;
        // Newest first. The backend does not promise an order.
        const sorted = [...loaded].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        );
        setJobs(sorted);
      })
      .catch((cause) => !cancelled && setFailure(cause));
    return () => {
      cancelled = true;
    };
  }, []);

  const postAction = (
    <Button level="primary" onClick={() => navigate("/jobs/new")}>
      Post a job
    </Button>
  );

  const overview = useMemo(() => {
    if (!jobs) return null;
    return {
      active: jobs.filter((job) => job.state === "active").length,
      applicants: jobs.reduce((total, job) => total + job.applicant_count, 0),
      shortlisted: jobs.reduce((total, job) => total + job.shortlisted_count, 0),
      interviews: jobs.reduce((total, job) => total + job.interviewed_count, 0),
    };
  }, [jobs]);

  return (
    <>
      <PageHeader
        title={view === "overview" ? "Hiring overview" : "Jobs"}
        subtitle={jobs && jobs.length > 0 ? "Your active hiring workspace" : undefined}
        actions={jobs && jobs.length > 0 ? postAction : undefined}
      />

      {failure && (
        <ApiErrorState
          error={failure}
          title="Jobs could not be loaded"
          action={
            <Button onClick={() => window.location.reload()}>Try again</Button>
          }
        />
      )}

      {!failure && jobs === null && <LoadingState label="Loading jobs" block />}

      {!failure && jobs?.length === 0 && (
        <EmptyState
          title="No jobs yet"
          body="Post a job and Rubric will build a scoring rubric from the description, then screen every applicant against it."
          action={postAction}
        />
      )}

      {!failure && jobs && jobs.length > 0 && (
        <div className="rb-dashboard">
          {overview && <DashboardOverview {...overview} />}
          {view === "overview" && overview && <OverviewPulse overview={overview} />}
          <section className="rb-dashboard__jobs" aria-labelledby="current-jobs-heading">
            <div className="rb-dashboard__jobs-heading">
              <div>
                <p className="text-label rb-dashboard__eyebrow">Current roles</p>
                <h2 id="current-jobs-heading" className="text-title-3 rb-dashboard__title">
                  {view === "overview" ? "Roles needing attention" : "Hiring in progress"}
                </h2>
              </div>
              <p className="text-caption rb-dashboard__note">Select a role to review candidates</p>
            </div>
            <ul className="rb-joblist">
              {jobs.map((job) => (
                <li key={job.id}>
                  <JobRow job={job} />
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </>
  );
}

function OverviewPulse({
  overview,
}: {
  overview: { active: number; applicants: number; shortlisted: number; interviews: number };
}) {
  const largest = Math.max(overview.applicants, 1);
  const stages = [
    { label: "Applied", value: overview.applicants },
    { label: "Shortlisted", value: overview.shortlisted },
    { label: "Interviewed", value: overview.interviews },
  ];

  return (
    <section className="rb-overview-pulse" aria-labelledby="overview-pulse-heading">
      <div className="rb-overview-pulse__pipeline">
        <div className="rb-overview-pulse__heading">
          <div>
            <p className="text-label">Candidate pipeline</p>
            <h2 id="overview-pulse-heading" className="text-title-3">Where candidates are moving</h2>
          </div>
          <span className="text-caption">Across active roles</span>
        </div>
        <div className="rb-overview-pulse__stages">
          {stages.map((stage) => (
            <div key={stage.label} className="rb-overview-pulse__stage">
              <span>{stage.label}</span>
              <div aria-hidden="true"><i style={{ width: `${Math.max(8, (stage.value / largest) * 100)}%` }} /></div>
              <strong>{stage.value}</strong>
            </div>
          ))}
        </div>
      </div>
      <aside className="rb-overview-pulse__focus">
        <p className="text-label">Hiring focus</p>
        <strong>{overview.active} active role{overview.active === 1 ? "" : "s"}</strong>
        <p>Review shortlisted candidates first, then send interview links from each dossier.</p>
      </aside>
    </section>
  );
}

function DashboardOverview({
  active,
  applicants,
  shortlisted,
  interviews,
}: {
  active: number;
  applicants: number;
  shortlisted: number;
  interviews: number;
}) {
  const metrics = [
    { value: active, label: "active roles" },
    { value: applicants, label: "applicants" },
    { value: shortlisted, label: "shortlisted" },
    { value: interviews, label: "interviews complete" },
  ];

  return (
    <section className="rb-dashboard__summary" aria-label="Hiring overview">
      {metrics.map((metric) => (
        <div key={metric.label} className="rb-dashboard__metric">
          <span className="text-label">{metric.label}</span>
          <strong>{metric.value}</strong>
        </div>
      ))}
    </section>
  );
}

/**
 * One job.
 *
 * A job still being analyzed is not clickable (screens.md section 1).
 * There is nothing behind it yet - no rubric, no application link, no
 * candidates - so a row that navigated to an empty page would be a
 * broken promise rather than a shortcut. It renders as a plain element
 * with its progress line instead of a link.
 */
function JobRow({ job }: { job: JobSummary }) {
  const analyzing = job.state === "analyzing";
  const failed = job.state === "failed";

  const body = (
    <>
      <div className="rb-joblist__top">
        <span className="rb-joblist__title">{job.title}</span>
        <Chip tone="neutral">{stateLabel(job.state)}</Chip>
      </div>
      <div className="rb-joblist__bottom">
        <span className="rb-joblist__counts">
          {analyzing
            ? "Building rubric from description"
            : failed
              ? "Rubric generation did not finish"
              : "Review progress at a glance"}
        </span>
        {!analyzing && !failed && (
          <span className="rb-joblist__pipeline" aria-label="Hiring pipeline">
            <span><strong>{job.applicant_count}</strong> applicant{job.applicant_count === 1 ? "" : "s"}</span>
            <span><strong>{job.shortlisted_count}</strong> shortlisted</span>
            <span><strong>{job.interviewed_count}</strong> interviewed</span>
          </span>
        )}
        <span className="rb-joblist__posted">Posted {formatDayMonth(job.created_at)}</span>
      </div>
    </>
  );

  if (analyzing || failed) {
    return <div className="rb-joblist__row rb-joblist__row--inert">{body}</div>;
  }

  return (
    <Link to={`/jobs/${job.id}`} className="rb-joblist__row">
      {body}
    </Link>
  );
}

function stateLabel(state: JobSummary["state"]): string {
  switch (state) {
    case "analyzing":
      return "Analyzing";
    case "active":
      return "Active";
    case "closed":
      return "Closed";
    case "failed":
      return "Failed";
    default:
      return state;
  }
}
