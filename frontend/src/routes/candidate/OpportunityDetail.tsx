import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CandidateShell } from "../../components/layout";
import { ApiErrorState, LoadingState } from "../../components/feedback";
import { Button, Chip } from "../../components/primitives";
import { api } from "../../api/client";
import type { PublicJobSummary } from "../../api/client";
import { formatDayMonth } from "../../lib/format";
import { readCandidateSession } from "../../lib/candidate-session";
import { parseJobDescription } from "../../lib/job-description";
import "./application.css";

/*
 * One role, as a candidate sees it.
 *
 * Deliberately outside the candidate session gate: a role link is meant to
 * be shareable, so a stranger can read this page. When there *is* a signed
 * in candidate their address goes with the request, and the server answers
 * whether they have already applied, which is what decides between the
 * apply action and a pointer back to their application.
 */
export function OpportunityDetailPage() {
  const { jobId = "" } = useParams();
  const [job, setJob] = useState<PublicJobSummary | null>(null);
  const [failure, setFailure] = useState<unknown>(null);

  // Read once per mount rather than subscribed: signing out is not
  // something that happens while reading a job description, and this page
  // has to keep working with no session at all.
  const email = useMemo(() => readCandidateSession()?.email, []);

  useEffect(() => {
    let cancelled = false;
    api.getPublicJob(jobId, email).then(
      (loaded) => !cancelled && setJob(loaded),
      (cause) => !cancelled && setFailure(cause),
    );
    return () => { cancelled = true; };
  }, [jobId, email]);

  return (
    <CandidateShell wide>
      {failure !== null && <ApiErrorState error={failure} title="This role could not be opened" />}
      {!failure && !job && <LoadingState label="Loading role" block />}
      {job && (
        <article className="rb-opportunity-detail">
          <Link to="/apply" className="rb-opportunity-detail__back">← All open roles</Link>

          <header className="rb-opportunity-detail__header">
            <p className="text-label rb-opportunity-detail__eyebrow">
              {job.applied ? "Your application" : "Open opportunity"}
            </p>
            <h1 className="rb-opportunity-detail__title">{job.title}</h1>
            <p className="rb-opportunity-detail__byline">
              {job.department && <span>{job.department}</span>}
              <span>Posted {formatDayMonth(job.created_at)}</span>
              {job.experience && <span>{job.experience} experience</span>}
            </p>
          </header>

          {/* Real columns since database/002_accounts.sql. These used to be
              buried inside the description prose, where a candidate had to
              read the whole posting to find out where the job was. Any the
              hiring team did not state are simply absent. */}
          <RoleFacts job={job} />

          <div className="rb-opportunity-detail__body">
            <div className="rb-opportunity-detail__main">
              <JobDescription description={job.description} />
            </div>

            <aside className="rb-opportunity-detail__aside">
              <ApplyCard job={job} />
              {job.skills.length > 0 && (
                <section className="rb-opportunity-detail__panel">
                  <h2 className="text-label">What the team is looking for</h2>
                  <div className="rb-opportunity-detail__skills">
                    {job.skills.map((skill) => <Chip key={skill}>{skill}</Chip>)}
                  </div>
                </section>
              )}
              <section className="rb-opportunity-detail__panel rb-opportunity-detail__how">
                <h2 className="text-label">How this application works</h2>
                <ol>
                  <li>Upload your resume and record a short voice introduction.</li>
                  <li>Rubric scores it against the criteria set for this role.</li>
                  <li>If the team invites you, you take a voice interview here.</li>
                </ol>
              </section>
            </aside>
          </div>
        </article>
      )}
    </CandidateShell>
  );
}

/*
 * The action, and the one thing a candidate is here to decide.
 *
 * Sticky on desktop so it stays reachable through a long description
 * rather than being stranded at the top of a page they have scrolled past.
 */
function ApplyCard({ job }: { job: PublicJobSummary }) {
  if (job.applied) {
    return (
      <section className="rb-opportunity-detail__apply rb-opportunity-detail__apply--applied">
        <p className="rb-opportunity-detail__applied-mark" aria-hidden="true">✓</p>
        <h2 className="text-body-strong">You have applied to this role</h2>
        <p className="text-caption">
          Your application is with the hiring team. Its status, and your
          interview link if they send one, are in My applications.
        </p>
        <Link to="/apply" className="rb-opportunity-detail__apply-action">
          <Button level="secondary">Go to My applications</Button>
        </Link>
      </section>
    );
  }

  return (
    <section className="rb-opportunity-detail__apply">
      <h2 className="text-body-strong">Apply for this role</h2>
      <p className="text-caption">
        A resume and a two minute voice introduction. About ten minutes.
      </p>
      <Link to={`/apply/${job.id}`} className="rb-opportunity-detail__apply-action">
        <Button level="primary" size="large">Apply for this role</Button>
      </Link>
    </section>
  );
}

/*
 * A pasted job description, rendered as something readable.
 *
 * What arrives here is whatever the hiring team typed or uploaded: usually
 * a heading, a paragraph, then a run of lines beginning with a bullet or a
 * dash. Rendered as one `<p>` it was a wall of text that nobody scans, and
 * the bullets the author wrote were invisible.
 *
 * The parser is in lib/job-description.ts and does not interpret meaning,
 * only shape: headings, paragraphs and lists. It never rewrites a word.
 */
function JobDescription({ description }: { description: string }) {
  const blocks = useMemo(() => parseJobDescription(description), [description]);

  return (
    <section className="rb-opportunity-detail__section">
      <h2 className="text-label rb-opportunity-detail__section-label">About the role</h2>
      <div className="rb-jd">
        {blocks.map((block, index) => {
          if (block.kind === "heading") {
            return <h3 key={index} className="rb-jd__heading">{block.text}</h3>;
          }
          if (block.kind === "list") {
            return (
              <ul key={index} className="rb-jd__list">
                {block.items.map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}
              </ul>
            );
          }
          return <p key={index} className="rb-jd__paragraph">{block.text}</p>;
        })}
      </div>
    </section>
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
