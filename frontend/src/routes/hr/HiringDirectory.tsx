import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { CandidateSummary, JobSummary } from "../../api/client";
import { RecommendationChip, ScoreInline, StatusChip } from "../../components/data";
import { ApiErrorState, EmptyState, LoadingState } from "../../components/feedback";
import { PageHeader } from "../../components/layout";
import { TextField } from "../../components/primitives";
import "./hr.css";

type DirectoryMode = "candidates" | "interviews";

interface DirectoryRow extends CandidateSummary {
  job: Pick<JobSummary, "id" | "title">;
}

/**
 * A cross-role view of every applicant.
 *
 * This was built by listing the jobs and then fanning out over
 * `listCandidates`, one request per role, each running four queries of its
 * own. It read as a small amount of client-side glue and behaved like a
 * page that took several seconds to appear. `GET /api/candidates` returns
 * the same rows in one request, already labelled with their role.
 */
export function HiringDirectoryPage({ mode }: { mode: DirectoryMode }) {
  const [rows, setRows] = useState<DirectoryRow[] | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    api.listAllCandidates()
      .then((candidates) => {
        if (cancelled) return;
        setRows(candidates.map((candidate) => ({
          ...candidate,
          job: { id: candidate.job_id ?? "", title: candidate.job_title ?? "" },
        })));
      })
      .catch((cause) => !cancelled && setFailure(cause));
    return () => { cancelled = true; };
  }, []);

  const heading = mode === "candidates" ? "Candidates" : "Interviews";
  const description = mode === "candidates"
    ? "Review every applicant across your open roles."
    : "Keep scheduled and completed interviews in one calm queue.";
  const filteredRows = useMemo(() => {
    const eligible = (rows ?? []).filter((row) => mode === "candidates" || ["approved", "interviewing", "interviewed"].includes(row.state));
    const normalized = query.trim().toLowerCase();
    if (!normalized) return eligible;
    return eligible.filter((row) => `${row.name} ${row.email} ${row.job.title}`.toLowerCase().includes(normalized));
  }, [mode, query, rows]);

  return (
    <>
      <PageHeader title={heading} subtitle={description} />
      {failure && <ApiErrorState error={failure} title={`${heading} could not be loaded`} />}
      {!failure && rows === null && <LoadingState label={`Loading ${heading.toLowerCase()}`} block />}
      {!failure && rows && (
        <section className="rb-directory" aria-label={heading}>
          <div className="rb-directory__toolbar">
            <TextField
              label={`Search ${heading.toLowerCase()}`}
              value={query}
              placeholder="Search a name, email, or role"
              onChange={(event) => setQuery(event.target.value)}
            />
            <p className="text-caption">{filteredRows.length} {mode === "candidates" ? "people" : "interviews"}</p>
          </div>
          {filteredRows.length === 0 ? (
            <EmptyState
              inline
              title={query ? `No ${heading.toLowerCase()} match that search` : `No ${heading.toLowerCase()} yet`}
              body={mode === "candidates" ? "Applications will appear here as candidates apply." : "Approve a candidate to begin an interview."}
            />
          ) : (
            <div className="rb-directory__list">
              <div className="rb-directory__head" aria-hidden="true">
                <span>Candidate</span>
                <span>Role</span>
                <span>Score</span>
                <span>Status</span>
                <span>Action</span>
              </div>
              {filteredRows.map((row) => <DirectoryRowCard key={row.id} row={row} mode={mode} />)}
            </div>
          )}
        </section>
      )}
    </>
  );
}

function DirectoryRowCard({ row, mode }: { row: DirectoryRow; mode: DirectoryMode }) {
  const completed = row.state === "interviewed";
  const href = completed && mode === "interviews"
    ? `/jobs/${row.job.id}/candidates/${row.id}/interview`
    : `/jobs/${row.job.id}/candidates/${row.id}`;
  return (
    <Link className="rb-directory__row" to={href}>
      <span className="rb-directory__person">
        <strong>{row.name}</strong>
        <small>{row.email}</small>
      </span>
      <span className="rb-directory__role">{row.job.title}</span>
      <span className="rb-directory__score"><ScoreInline score={row.screening_score} band={row.screening_band} /></span>
      <span className="rb-directory__chips">
        {mode === "candidates" ? <RecommendationChip recommendation={row.recommendation} /> : null}
        <StatusChip state={row.state} />
      </span>
      <span className="rb-directory__action">{completed && mode === "interviews" ? "View result" : "Review"} <span aria-hidden="true">→</span></span>
    </Link>
  );
}

export function SettingsPage() {
  return (
    <>
      <PageHeader title="Workspace settings" subtitle="Local demo workspace" />
      <section className="rb-settings" aria-label="Workspace details">
        <div>
          <p className="text-label">Workspace</p>
          <h2 className="text-title-3">Rubric demo</h2>
          <p className="text-body">Use the sidebar control to choose the expanded or compact workspace navigation that suits your review session.</p>
        </div>
        <div className="rb-settings__notice">
          <span className="text-label">Privacy</span>
          <p>Candidate evidence remains visible only inside the HR workspace.</p>
        </div>
      </section>
    </>
  );
}
