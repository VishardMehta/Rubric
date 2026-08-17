import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageHeader } from "../../components/layout";
import { Button } from "../../components/primitives";
import { ApiErrorState, EmptyState, LoadingState } from "../../components/feedback";
import { RubricPanel } from "../../components/domain";
import {
  DataTable,
  RecommendationChip,
  ScoreInline,
  StatRow,
  StatusChip,
} from "../../components/data";
import type { Column } from "../../components/data";
import { api } from "../../api/client";
import type { CandidateSummary, JobDetail } from "../../api/client";
import { useCopyToClipboard } from "../../hooks/useCopyToClipboard";
import { formatDayMonth } from "../../lib/format";
import { statusLabel } from "../../lib/tone";
import { buildPipeline } from "../../lib/pipeline";
import type { PipelineGroup } from "../../lib/pipeline";
import "./hr.css";

/*
 * screens.md section 3. The working screen: every applicant, with enough
 * information to decide who to open.
 *
 * Grouped by pipeline stage since Phase E, interviewed first. Rank is
 * computed across the whole field rather than within a group, so a
 * candidate's number is their standing overall and does not change when
 * they move between groups.
 */

export function JobDetailPage() {
  const { jobId = "" } = useParams();

  const [job, setJob] = useState<JobDetail | null>(null);
  const [candidates, setCandidates] = useState<CandidateSummary[] | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const { copy } = useCopyToClipboard();

  useEffect(() => {
    let cancelled = false;
    // Cleared before the fetch, not after it resolves. Without this,
    // moving from one role to another leaves the previous role's title and
    // its candidate list on screen under the new URL until the request
    // comes back: one job's applicants shown as another's.
    setJob(null);
    setCandidates(null);
    setFailure(null);
    Promise.all([api.getJob(jobId), api.listCandidates(jobId)])
      .then(([loadedJob, loadedCandidates]) => {
        if (cancelled) return;
        setJob(loadedJob);
        setCandidates(loadedCandidates);
      })
      .catch((cause) => !cancelled && setFailure(cause));
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  // Ranked once across the whole field, so a candidate's rank is their
  // rank overall rather than their position inside whichever group they
  // landed in.
  const ranked = useMemo(() => {
    if (!candidates) return [];
    return [...candidates]
      .sort((a, b) => (b.screening_score ?? -1) - (a.screening_score ?? -1))
      .map((candidate, index) => ({ ...candidate, rank: index + 1 }));
  }, [candidates]);

  // Grouped by where each candidate actually is in the pipeline, with the
  // interviewed at the top. The recommendation filter tabs this replaces
  // put a scored interview in the same undifferentiated run as an
  // application from an hour ago.
  const pipeline = useMemo(() => buildPipeline(ranked), [ranked]);

  const applyUrl = `${window.location.origin}/apply/${jobId}`;

  if (failure) {
    return (
      <>
        <PageHeader title="Job" breadcrumb={{ label: "Jobs", to: "/jobs" }} />
        <ApiErrorState error={failure} title="This job could not be loaded" />
      </>
    );
  }

  if (!job || !candidates) {
    return <LoadingState label="Loading job" block />;
  }

  return (
    <>
      <PageHeader
        title={job.title}
        breadcrumb={{ label: "Jobs", to: "/jobs" }}
        actions={
          <Button onClick={() => void copy(applyUrl, "Application link copied")}>
            Copy application link
          </Button>
        }
      />

      <div className="rb-jobdetail">
        <StatRow
          stats={[
            { value: job.applicant_count, label: pluralise(job.applicant_count, "applicant") },
            { value: job.shortlisted_count, label: "shortlisted" },
            { value: job.interviewed_count, label: "interviewed" },
            { value: formatDayMonth(job.created_at), label: "posted", labelFirst: true },
          ]}
        />

        {job.rubric && <RubricPanel rubric={job.rubric} collapsible />}

        {ranked.length === 0 ? (
          <EmptyState
            title="No applications yet"
            body="Share the application link and candidates can apply with a voice introduction."
            action={
              <Button
                level="primary"
                onClick={() => void copy(applyUrl, "Application link copied")}
              >
                Copy application link
              </Button>
            }
          />
        ) : (
          <section className="rb-jobdetail__candidates" aria-labelledby="candidate-pipeline-heading">
            <div className="rb-jobdetail__candidates-head">
              <div>
                <p className="text-label rb-jobdetail__candidates-eyebrow">Candidate pipeline</p>
                <h2 id="candidate-pipeline-heading" className="text-title-3 rb-jobdetail__candidates-title">
                  Screened applicants
                </h2>
              </div>
              <p className="text-caption rb-jobdetail__candidates-note">
                Ranked by screening score
              </p>
            </div>
            {pipeline.map((group) => (
              <PipelineSection
                key={group.id}
                group={group}
                jobId={jobId}
                jobTitle={job.title}
              />
            ))}
          </section>
        )}
      </div>
    </>
  );
}

type RankedCandidate = CandidateSummary & { rank: number };

function columns(jobId: string): Column<RankedCandidate>[] {
  return [
    {
      key: "rank",
      header: "#",
      width: "48px",
      cell: (row) => <span className="rb-table__rank">{row.rank}</span>,
    },
    {
      key: "candidate",
      header: "Candidate",
      cell: (row) => (
        <>
          <Link
            to={`/jobs/${jobId}/candidates/${row.id}`}
            className="rb-table__link"
            // The row already navigates here; stop the click so it does
            // not fire twice and push two history entries.
            onClick={(event) => event.stopPropagation()}
          >
            {row.name}
          </Link>
          <span className="rb-table__secondary">{row.email}</span>
        </>
      ),
    },
    {
      key: "score",
      header: "Screening",
      align: "right",
      width: "96px",
      cell: (row) => <ScoreInline score={row.screening_score} band={row.screening_band} />,
    },
    // Shown in every group, including the ones where nobody has been
    // interviewed yet. It used to appear only where a score existed, which
    // meant the two numbers HR is comparing sat in different columns from
    // group to group. An em-space says "not yet"; screens.md is explicit
    // that an unscored candidate never shows a zero.
    {
      key: "interview",
      header: "Interview",
      align: "right",
      width: "96px",
      cell: (row) => <ScoreInline score={row.interview_score} band={row.interview_band} />,
    },
    {
      key: "skills",
      header: "Skills",
      width: "112px",
      cell: (row) =>
        row.skills_total > 0 ? (
          <span className="rb-table__skills">
            {row.matched_count} of {row.skills_total}
          </span>
        ) : null,
    },
    {
      key: "recommendation",
      header: "Recommendation",
      width: "160px",
      cell: (row) => <RecommendationChip recommendation={row.recommendation} />,
    },
    {
      key: "status",
      header: "Status",
      width: "132px",
      cell: (row) => <StatusChip state={row.state} />,
    },
  ];
}

/** screens.md section 3, compact: name and score first, email second,
 *  chips third. */
function CandidateCard({
  jobId,
  candidate,
}: {
  jobId: string;
  candidate: RankedCandidate;
}) {
  return (
    <Link to={`/jobs/${jobId}/candidates/${candidate.id}`} className="rb-card-row">
      <span className="rb-card-row__top">
        <span className="rb-card-row__name">{candidate.name}</span>
        {/* Both numbers, labelled, because the compact layout has no
            column headers to tell them apart. */}
        <span className="rb-card-row__scores">
          <span>
            Screening <ScoreInline score={candidate.screening_score} band={candidate.screening_band} />
          </span>
          <span>
            Interview <ScoreInline score={candidate.interview_score} band={candidate.interview_band} />
          </span>
        </span>
      </span>
      <span className="rb-card-row__secondary">{candidate.email}</span>
      <span className="rb-card-row__chips">
        <RecommendationChip recommendation={candidate.recommendation} />
        <span className="rb-card-row__status">{statusLabel(candidate.state)}</span>
      </span>
    </Link>
  );
}


function pluralise(count: number, word: string): string {
  return count === 1 ? word : `${word}s`;
}


/*
 * One pipeline group: a heading, a hint, and the table.
 *
 * Rejected renders collapsed behind a disclosure, because it is the one
 * group you open deliberately. Everything else is expanded: a group you
 * have to click to see is a group you will forget is there.
 */
function PipelineSection({
  group,
  jobId,
  jobTitle,
}: {
  group: PipelineGroup<RankedCandidate>;
  jobId: string;
  jobTitle: string;
}) {
  const interviewLed = group.id === "interviewed" || group.id === "hired";

  const table = (
    <DataTable
      caption={`${group.title} candidates for ${jobTitle}`}
      rows={group.candidates}
      rowKey={(row) => row.id}
      rowHref={(row) =>
        // Interviewed candidates go straight to the result, which is the
        // thing you opened the row to read. Everyone else goes to their
        // detail page.
        // The interview result only exists if there was one. A hired
        // candidate normally has one, but the row still has to link
        // somewhere real if HR hired them without interviewing.
        interviewLed && row.interview_status
          ? `/jobs/${jobId}/candidates/${row.id}/interview`
          : `/jobs/${jobId}/candidates/${row.id}`
      }
      columns={columns(jobId)}
      renderCard={(row) => <CandidateCard jobId={jobId} candidate={row} />}
    />
  );

  if (group.collapsed) {
    return (
      <details className="rb-pipeline__group rb-pipeline__group--collapsed">
        <summary>
          {group.title} <span className="rb-pipeline__count">{group.candidates.length}</span>
        </summary>
        <div className="rb-pipeline__body">{table}</div>
      </details>
    );
  }

  return (
    <section className="rb-pipeline__group">
      <div className="rb-pipeline__head">
        <h3 className="text-title-3 rb-pipeline__title">
          {group.title} <span className="rb-pipeline__count">{group.candidates.length}</span>
        </h3>
        <p className="text-caption rb-pipeline__hint">{group.hint}</p>
      </div>
      {table}
    </section>
  );
}
