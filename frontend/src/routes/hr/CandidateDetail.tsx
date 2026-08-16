import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card, PageHeader, Split } from "../../components/layout";
import { Button, Chip } from "../../components/primitives";
import { ApiErrorState, LoadingState, Modal } from "../../components/feedback";
import { AudioPlayer, CopyLinkField, TranscriptView } from "../../components/domain";
import { ScoreBreakdown, ScoreHero, StatusChip } from "../../components/data";
import { api, ApiError } from "../../api/client";
import type { CandidateDetail, ResumeProfile } from "../../api/client";
import { formatDayMonth } from "../../lib/format";
import { recommendationLabel } from "../../lib/tone";
import "./hr.css";

/*
 * screens.md section 4. Everything known about one applicant before the
 * interview decision. Scores left, evidence right, at 5:7.
 */

export function CandidateDetailPage() {
  const { jobId = "", candidateId = "" } = useParams();

  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [confirmingReject, setConfirmingReject] = useState(false);
  const [acting, setActing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getCandidate(candidateId)
      .then((loaded) => !cancelled && setCandidate(loaded))
      .catch((cause) => !cancelled && setFailure(cause));
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  const approve = useCallback(async () => {
    setActing(true);
    setActionError(null);
    try {
      await api.approveCandidate(candidateId);
      // Re-fetch rather than patching state locally: approval mints the
      // interview token server-side, and the detail response is the only
      // thing that knows it.
      setCandidate(await api.getCandidate(candidateId));
    } catch (cause) {
      setActionError(cause instanceof ApiError ? cause.message : "Something went wrong. Try again.");
    } finally {
      setActing(false);
    }
  }, [candidateId]);

  const reject = useCallback(async () => {
    setActing(true);
    setActionError(null);
    try {
      await api.rejectCandidate(candidateId);
      setCandidate(await api.getCandidate(candidateId));
      setConfirmingReject(false);
    } catch (cause) {
      setActionError(cause instanceof ApiError ? cause.message : "Something went wrong. Try again.");
      setConfirmingReject(false);
    } finally {
      setActing(false);
    }
  }, [candidateId]);

  if (failure) {
    return (
      <>
        <PageHeader title="Candidate" breadcrumb={{ label: "Jobs", to: "/jobs" }} />
        <ApiErrorState error={failure} title="This candidate could not be loaded" />
      </>
    );
  }

  if (!candidate) return <LoadingState label="Loading candidate" block />;

  const screening = candidate.screening_score !== null;
  const decided = candidate.state === "approved" || candidate.state === "interviewing" ||
    candidate.state === "interviewed" || candidate.state === "rejected";

  return (
    <>
      <PageHeader
        title={candidate.name}
        breadcrumb={{ label: candidate.job_title, to: `/jobs/${jobId}` }}
        subtitle={`${candidate.email} · Applied ${formatDayMonth(candidate.created_at)}`}
        actions={
          decided ? (
            <StatusChip state={candidate.state} />
          ) : (
            <div className="rb-candidate__actions">
              <Button level="destructive" onClick={() => setConfirmingReject(true)} disabled={acting}>
                Reject
              </Button>
              <Button level="primary" onClick={() => void approve()} loading={acting}>
                Approve for interview
              </Button>
            </div>
          )
        }
      />

      {actionError && (
        <div className="rb-candidate__action-error" role="alert">
          {actionError}
        </div>
      )}

      <CandidateSnapshot candidate={candidate} screening={screening} />

      {/* Post-approval: the interview link replaces the action bar. */}
      {candidate.interview_token && (
        <div className="rb-candidate__link">
          <div className="rb-candidate__link-head">
            <p className="text-label rb-candidate__link-eyebrow">Next step</p>
            <h2 className="text-title-3 rb-candidate__link-title">Interview link is ready</h2>
          </div>
          <CopyLinkField
            url={`${window.location.origin}/interview/${candidate.interview_token}`}
            toastMessage="Interview link copied"
            help="Send this to the candidate. It works once and expires when the interview is complete."
          />
        </div>
      )}

      <Split
        left={
          <div className="rb-candidate__col">
            {candidate.interview_status &&
              candidate.interview_status !== "not_started" && (
                <InterviewLink jobId={jobId} candidate={candidate} />
              )}

            {!screening ? (
              // Do not block the whole screen: the transcript on the right
              // is already useful while this finishes (screens.md 4).
              <Card>
                <LoadingState label="Scoring against rubric" />
              </Card>
            ) : (
              <Card primary>
                <div className="rb-candidate__evidence-head">
                  <div>
                    <p className="text-label">Screening evidence</p>
                    <h2 className="text-title-3">How the score was earned</h2>
                  </div>
                  <span className="text-caption">Open a criterion for quotes</span>
                </div>
                {/* The two components behind the headline number. A
                    weighted total is not explainable without them: 72
                    from a strong resume and a thin introduction is a
                    different candidate from 72 the other way round. */}
                {candidate.resume_score !== null && candidate.voice_score !== null && (
                  <div className="rb-candidate__components">
                    <div className="rb-candidate__component">
                      <p className="text-label">Resume · 60%</p>
                      <strong>{candidate.resume_score}<span>/100</span></strong>
                    </div>
                    <div className="rb-candidate__component">
                      <p className="text-label">Voice introduction · 40%</p>
                      <strong>{candidate.voice_score}<span>/100</span></strong>
                    </div>
                  </div>
                )}
                <div className="rb-candidate__breakdown">
                  <p className="text-label rb-candidate__breakdown-label">
                    Resume, against the rubric
                  </p>
                  <ScoreBreakdown
                    subScores={candidate.sub_scores}
                    total={candidate.resume_score ?? (candidate.screening_score as number)}
                    showEvidence
                  />
                </div>
                {candidate.voice_sub_scores.length > 0 && (
                  <div className="rb-candidate__breakdown">
                    <p className="text-label rb-candidate__breakdown-label">
                      Voice introduction, against the same rubric
                    </p>
                    <ScoreBreakdown
                      subScores={candidate.voice_sub_scores}
                      total={candidate.voice_score as number}
                      showEvidence
                    />
                  </div>
                )}
              </Card>
            )}
          </div>
        }
        right={
          <div className="rb-candidate__col">
            <Card>
              <h2 className="text-title-3 rb-candidate__card-title">Voice introduction</h2>
              <AudioPlayer src={candidate.audio_url} label={`${candidate.name}'s introduction`} />
              <div className="rb-candidate__transcript">
                <TranscriptView text={candidate.transcript} collapsible />
              </div>
            </Card>

            {/* Who this person is, before the numbers about them. HR asked
                for "what kind of candidate they are getting", and until now
                the answer was one raw text blob behind a collapsed
                disclosure. Absent when parsing failed or the row predates
                the feature, in which case that disclosure is still there. */}
            {candidate.resume_profile && <ResumeProfileCards profile={candidate.resume_profile} />}

            {screening && (
              <Card>
                <h2 className="text-title-3 rb-candidate__card-title">Skills</h2>
                <SkillGroup title="Matched" skills={candidate.matched_skills} />
                {/* `Not evidenced`, never `Missing`. The system knows what
                    neither source mentioned, not what the candidate cannot
                    do (screens.md section 4). */}
                <SkillGroup title="Not evidenced" skills={candidate.unevidenced_skills} />
              </Card>
            )}

            {candidate.assessment && (
              <Card>
                <h2 className="text-title-3 rb-candidate__card-title">Assessment</h2>
                <p className="rb-candidate__assessment">{candidate.assessment}</p>
              </Card>
            )}

            {/* Neutral panel, only when non-empty. No semantic colour and
                no warning icon: this reports a discrepancy, it does not
                accuse anyone, and it carries no score penalty. */}
            {candidate.resume_intro_conflicts.length > 0 && (
              <div className="rb-conflicts">
                <h2 className="text-title-3 rb-candidate__card-title">
                  Differences between sources
                </h2>
                <ul className="rb-conflicts__list">
                  {candidate.resume_intro_conflicts.map((conflict) => (
                    <li key={conflict}>{conflict}</li>
                  ))}
                </ul>
              </div>
            )}

            {candidate.resume_url && (
              <Card>
                <h2 className="text-title-3 rb-candidate__card-title">Resume</h2>
                <a
                  className="rb-candidate__resume-link"
                  href={candidate.resume_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open the original PDF
                </a>
                {candidate.resume_text && (
                  <details className="rb-transcript">
                    <summary className="rb-transcript__summary">Extracted text</summary>
                    <p className="rb-transcript__text">{candidate.resume_text}</p>
                  </details>
                )}
              </Card>
            )}
          </div>
        }
      />

      <Modal
        open={confirmingReject}
        onClose={() => setConfirmingReject(false)}
        title={`Reject ${candidate.name}?`}
        actions={
          <>
            <Button onClick={() => setConfirmingReject(false)}>Keep reviewing</Button>
            <Button level="destructive" onClick={() => void reject()} loading={acting}>
              Reject
            </Button>
          </>
        }
      >
        They will not receive an interview link. This cannot be undone in the MVP.
      </Modal>
    </>
  );
}

function CandidateSnapshot({
  candidate,
  screening,
}: {
  candidate: CandidateDetail;
  screening: boolean;
}) {
  const interview = candidate.interview_status === "evaluated" || candidate.interview_status === "complete"
    ? "Interview complete"
    : candidate.interview_status && candidate.interview_status !== "not_started"
      ? "Interview in progress"
      : "Interview not started";

  return (
    <section className="rb-candidate__snapshot" aria-label="Candidate overview">
      <div className="rb-candidate__snapshot-role">
        <p className="text-label">Candidate dossier</p>
        <strong>{candidate.job_title}</strong>
        <span>Applied {formatDayMonth(candidate.created_at)}</span>
      </div>
      <div className="rb-candidate__snapshot-score">
        {screening ? (
          <ScoreHero
            label="Screening score"
            score={candidate.screening_score as number}
            band={candidate.screening_band}
            bandLabel={recommendationLabel(candidate.recommendation)}
          />
        ) : (
          <>
            <p className="text-label">Screening score</p>
            <strong>—</strong>
            <span>Evaluation in progress</span>
          </>
        )}
      </div>
      <div className="rb-candidate__snapshot-state">
        <div>
          <p className="text-label">Screening status</p>
          <StatusChip state={candidate.state} />
        </div>
        <div>
          <p className="text-label">Interview</p>
          <span>{interview}</span>
        </div>
      </div>
    </section>
  );
}

function InterviewLink({ jobId, candidate }: { jobId: string; candidate: CandidateDetail }) {
  const done = candidate.interview_status === "evaluated" || candidate.interview_status === "complete";
  if (!done) {
    return (
      <div className="rb-candidate__interview-note" role="status">
        <span className="rb-candidate__interview-note-label">Interview in progress</span>
        <span>The result appears here once the candidate has completed every answer.</span>
      </div>
    );
  }
  return (
    <Link
      to={`/jobs/${jobId}/candidates/${candidate.id}/interview`}
      className="rb-candidate__interview-link"
    >
      <span>Interview complete</span>
      <span className="rb-candidate__interview-link-detail">View the scored result and transcript</span>
    </Link>
  );
}

function SkillGroup({ title, skills }: { title: string; skills: string[] }) {
  if (skills.length === 0) return null;
  return (
    <div className="rb-candidate__skills">
      <p className="text-label rb-candidate__skills-title">{title}</p>
      <div className="rb-candidate__chips">
        {skills.map((skill) => (
          <Chip key={skill}>{skill}</Chip>
        ))}
      </div>
    </div>
  );
}


/*
 * The structured resume: who they are, where they studied, what they have
 * done. Display only. Nothing here feeds or explains a score, which is why
 * it carries no points, no bars and no band colour: screening reads the
 * raw resume text against the rubric and is the only thing that produces a
 * number.
 *
 * Each card renders only when it has something in it. A candidate with no
 * work history shows education and stops, rather than an empty panel
 * captioned "None".
 */
function ResumeProfileCards({ profile }: { profile: ResumeProfile }) {
  const { headline, education, experience, links } = profile;
  const hasAnything =
    headline || education.length > 0 || experience.length > 0 || links.length > 0;
  if (!hasAnything) return null;

  return (
    <>
      {(headline || links.length > 0) && (
        <Card>
          {headline && <p className="rb-profile__headline">{headline}</p>}
          {links.length > 0 && (
            <ul className="rb-profile__links">
              {links.map((href) => (
                <li key={href}>
                  <a href={href} target="_blank" rel="noreferrer noopener">
                    {href}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {experience.length > 0 && (
        <Card>
          <h2 className="text-title-3 rb-candidate__card-title">Experience</h2>
          <ol className="rb-profile__list">
            {experience.map((entry, index) => (
              <li key={`${entry.organisation}-${index}`} className="rb-profile__entry">
                <div className="rb-profile__entry-head">
                  <span className="rb-profile__entry-title">
                    {entry.role ? `${entry.role}, ${entry.organisation}` : entry.organisation}
                  </span>
                  {/* Dates as the resume wrote them. Never computed: a
                      derived date is indistinguishable from a stated one. */}
                  {entry.period && <span className="rb-profile__period">{entry.period}</span>}
                </div>
                {entry.highlights.length > 0 && (
                  <ul className="rb-profile__highlights">
                    {entry.highlights.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        </Card>
      )}

      {education.length > 0 && (
        <Card>
          <h2 className="text-title-3 rb-candidate__card-title">Education</h2>
          <ol className="rb-profile__list">
            {education.map((entry, index) => (
              <li key={`${entry.institution}-${index}`} className="rb-profile__entry">
                <div className="rb-profile__entry-head">
                  <span className="rb-profile__entry-title">{entry.institution}</span>
                  {entry.period && <span className="rb-profile__period">{entry.period}</span>}
                </div>
                <p className="rb-profile__entry-detail">
                  {[entry.qualification, entry.field_of_study, entry.result]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </>
  );
}
