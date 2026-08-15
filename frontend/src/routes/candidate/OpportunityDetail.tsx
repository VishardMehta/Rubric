import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CandidateShell } from "../../components/layout";
import { ApiErrorState, LoadingState } from "../../components/feedback";
import { Button, Chip } from "../../components/primitives";
import { api } from "../../api/client";
import type { PublicJobSummary } from "../../api/client";
import { formatDayMonth } from "../../lib/format";
import "./application.css";

export function OpportunityDetailPage() {
  const { jobId = "" } = useParams();
  const [job, setJob] = useState<PublicJobSummary | null>(null);
  const [failure, setFailure] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    api.getPublicJob(jobId).then(
      (loaded) => !cancelled && setJob(loaded),
      (cause) => !cancelled && setFailure(cause),
    );
    return () => { cancelled = true; };
  }, [jobId]);

  return (
    <CandidateShell>
      {failure !== null && <ApiErrorState error={failure} title="This role could not be opened" />}
      {!failure && !job && <LoadingState label="Loading role" block />}
      {job && (
        <article className="rb-opportunity-detail">
          <Link to="/apply" className="rb-opportunity-detail__back">← All open roles</Link>
          <header className="rb-opportunity-detail__header">
            <p className="text-label">Open opportunity</p>
            <h1 className="text-title-1">{job.title}</h1>
            <p className="text-body-lg">
              Posted {formatDayMonth(job.created_at)}
              {job.experience ? ` · ${job.experience} experience` : ""}
            </p>
            <Link to={`/apply/${job.id}`}>
              <Button level="primary" size="large">Apply for this role</Button>
            </Link>
          </header>
          {/* Real columns since database/002_accounts.sql. These used to be
              buried inside the description prose, where a candidate had to
              read the whole posting to find out where the job was. Any the
              hiring team did not state are simply absent. */}
          <RoleFacts job={job} />
          <section className="rb-opportunity-detail__section">
            <p className="text-label">About the role</p>
            <p className="rb-opportunity-detail__description">{job.description}</p>
          </section>
          <section className="rb-opportunity-detail__section">
            <p className="text-label">What the team is looking for</p>
            <div className="rb-opportunity-detail__skills">
              {job.skills.map((skill) => <Chip key={skill}>{skill}</Chip>)}
            </div>
          </section>
        </article>
      )}
    </CandidateShell>
  );
}

const WORKPLACE_LABELS: Record<string, string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  onsite: "On-site",
};

const EMPLOYMENT_LABELS: Record<string, string> = {
  full_time: "Full time",
  part_time: "Part time",
  contract: "Contract",
  internship: "Internship",
};

/*
 * The practical questions, answered before the description.
 *
 * A candidate is deciding whether to spend fifteen minutes on a resume
 * upload and a two minute recording. Where the job is, what it pays and
 * whether it is an internship decide that, and they should not have to be
 * mined out of a paragraph to find out.
 *
 * Renders nothing when the hiring team stated none of them, rather than a
 * row of "Not specified".
 */
function RoleFacts({ job }: { job: PublicJobSummary }) {
  const facts = [
    { label: "Location", value: job.location },
    { label: "Workplace", value: job.workplace_type ? WORKPLACE_LABELS[job.workplace_type] : null },
    { label: "Employment", value: job.employment_type ? EMPLOYMENT_LABELS[job.employment_type] : null },
    { label: "Compensation", value: job.compensation },
    { label: "Team", value: job.department },
  ].filter((fact) => fact.value);

  if (facts.length === 0) return null;

  return (
    <dl className="rb-opportunity-detail__facts">
      {facts.map((fact) => (
        <div key={fact.label}>
          <dt>{fact.label}</dt>
          <dd>{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}
