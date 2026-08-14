import { useEffect, useState } from "react";
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

export function JobsPage() {
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

  return (
    <>
      <PageHeader title="Jobs" actions={jobs && jobs.length > 0 ? postAction : undefined} />

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
        <ul className="rb-joblist">
          {jobs.map((job) => (
            <li key={job.id}>
              <JobRow job={job} />
            </li>
          ))}
        </ul>
      )}
    </>
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
              : `${job.applicant_count} applicant${job.applicant_count === 1 ? "" : "s"} · ${job.shortlisted_count} shortlisted · ${job.interviewed_count} interviewed`}
        </span>
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
