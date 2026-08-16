import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CandidateShell } from "../../components/layout";
import { Button, Divider, FileDropzone, TextField } from "../../components/primitives";
import { ErrorState } from "../../components/feedback";
import { VoiceRecorder } from "../../components/domain";
import type { AudioRecording } from "../../hooks/useAudioRecorder";
import { api, ApiError, submitApplicationStreaming } from "../../api/client";
import type { ApplicationStage, PublicJobSummary } from "../../api/client";
import "./application.css";
import { signInCandidate } from "../../lib/candidate-session";
import type { CandidateSession } from "../../lib/candidate-session";

/*
 * screens.md section 6. A stranger's first contact with the product.
 *
 * Single column at every width, no cards, hairlines dividing the four
 * groups: identity, resume, voice introduction, submit. Validation runs on
 * blur, never on submit, so nothing turns red until the candidate has
 * actually had a chance to get it right.
 */

type Phase = "loading" | "invalid" | "form" | "submitting";

const RESUME_ERROR_CODES = new Set([
  "resume_wrong_format",
  "resume_too_large",
  "resume_not_readable",
]);

/** Candidate-facing wording for each backend stage. design-system.md
 *  section 15 names these exactly; "Uploading" covers the time before the
 *  first stream line arrives, the same way the interview screen does. */
const STAGE_LABELS: Record<ApplicationStage, string> = {
  reading_resume: "Reading your resume",
  transcribing: "Transcribing your introduction",
  scoring: "Scoring against rubric",
};

const UPLOAD_LABEL = "Uploading";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function ApplicationPage({ session }: { session: CandidateSession }) {
  const { jobId = "" } = useParams();
  const navigate = useNavigate();

  const [phase, setPhase] = useState<Phase>("loading");
  const [job, setJob] = useState<PublicJobSummary | null>(null);
  const [loadFailure, setLoadFailure] = useState<ApiError | null>(null);

  const [name, setName] = useState(session.name ?? "");
  // Fixed to the signed-in address, not merely prefilled. The portal looks
  // applications up by it, so an application sent under a different address
  // would land somewhere its author cannot see. Changing it is a sign out,
  // which is a decision, rather than an edit to a field.
  const email = session.email;
  const [nameTouched, setNameTouched] = useState(false);

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeServerError, setResumeServerError] = useState<string | null>(null);

  const [recording, setRecording] = useState<AudioRecording | null>(null);

  const [stageLabel, setStageLabel] = useState(UPLOAD_LABEL);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getPublicJob(jobId)
      .then((loaded) => {
        if (cancelled) return;
        setJob(loaded);
        setPhase("form");
      })
      .catch((cause) => {
        if (cancelled) return;
        setLoadFailure(cause instanceof ApiError ? cause : null);
        setPhase("invalid");
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const nameError = nameTouched && name.trim().length === 0 ? "Enter your name." : undefined;

  const canSubmit = useMemo(
    () =>
      name.trim().length > 0 &&
      EMAIL_PATTERN.test(email.trim()) &&
      resumeFile !== null &&
      recording !== null &&
      recording.blob.size > 0,
    [name, email, resumeFile, recording],
  );

  const handleResumeChange = useCallback((file: File | null) => {
    setResumeServerError(null);
    setResumeFile(file);
  }, []);

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setNameTouched(true);
      if (!canSubmit || !resumeFile || !recording) return;

      setSubmitError(null);
      setResumeServerError(null);
      setPhase("submitting");
      setStageLabel(UPLOAD_LABEL);

      try {
        const created = await submitApplicationStreaming(
          jobId,
          { name: name.trim(), email, resume: resumeFile, audio: recording.blob },
          (stage) => setStageLabel(STAGE_LABELS[stage]),
        );
        // Carries the name back into the session, so the portal can greet
        // someone who signed in with an address and nothing else.
        signInCandidate(email, name.trim());
        navigate(`/apply/${jobId}/done`, { replace: true, state: { jobTitle: created.job_title } });
      } catch (cause) {
        if (cause instanceof ApiError && RESUME_ERROR_CODES.has(cause.code)) {
          // screens.md section 6: return to the form with the file cleared
          // and the message shown where the resume was.
          setResumeServerError(cause.message);
          setResumeFile(null);
          setPhase("form");
          return;
        }
        setSubmitError(
          cause instanceof ApiError
            ? cause.message
            : "Something went wrong. Try again.",
        );
        setPhase("form");
      }
    },
    [canSubmit, resumeFile, recording, jobId, name, email, navigate],
  );

  if (phase === "loading") {
    return (
      <CandidateShell>
        <div />
      </CandidateShell>
    );
  }

  if (phase === "invalid") {
    return (
      <CandidateShell>
        <ErrorState
          variant="blocking"
          title="This job could not be found"
          body={loadFailure?.message ?? "The link may be mistyped, or this role may no longer be accepting applications."}
        />
      </CandidateShell>
    );
  }

  const submitting = phase === "submitting";

  return (
    <CandidateShell>
      <form className="rb-apply" onSubmit={handleSubmit} noValidate>
        <header className="rb-apply__header">
          <h1 className="text-title-1 rb-apply__title">{job?.title}</h1>
          <p className="text-label rb-apply__eyebrow">Applying with a voice introduction</p>
        </header>

        <Divider />

        <div className="rb-apply__fields">
          <p className="text-label rb-apply__section-label">01 · Your details</p>
          <TextField
            label="Your name"
            autoComplete="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            onBlur={() => setNameTouched(true)}
            error={nameError}
            disabled={submitting}
          />
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            readOnly
            help="You are signed in with this address. Your application appears under it in My applications."
          />
        </div>

        <Divider />

        <div className="rb-apply__resume">
          <div className="rb-apply__section-head">
            <p className="text-label rb-apply__section-label">02 · Your resume</p>
            <span className="rb-apply__label">Resume</span>
          </div>
          <FileDropzone
            value={resumeFile}
            onChange={handleResumeChange}
            serverError={resumeServerError}
            disabled={submitting}
          />
        </div>

        <Divider />

        <div className="rb-apply__voice">
          <div className="rb-apply__section-head">
            <p className="text-label rb-apply__section-label">03 · Your introduction</p>
            <h2 className="text-title-3 rb-apply__label">Voice introduction</h2>
          </div>
          {/* Weighted at 40% of the screening score, against the same
              rubric as the resume, so the brief has to say what earns
              points rather than "tell us about yourself". */}
          <p className="text-body-lg rb-apply__voice-copy">
            <strong>About two minutes.</strong> Cover the experience, projects
            and skills that matter for this role: what you built, the decisions
            you made and why, and anything about you the resume does not show.
            Detailed but concise is what counts here, not length.
          </p>
          <VoiceRecorder onChange={setRecording} disabled={submitting} />
        </div>

        <div className="rb-apply__submit">
          <p className="text-caption rb-apply__submit-note">
            Your application is sent only when every item above is complete.
          </p>
          {submitError && (
            <p className="rb-apply__submit-error" role="alert">
              {submitError}
            </p>
          )}
          <Button
            type="submit"
            level="primary"
            size="large"
            loading={submitting}
            disabled={!canSubmit && !submitting}
          >
            {submitting ? stageLabel : "Submit application"}
          </Button>
        </div>
      </form>
    </CandidateShell>
  );
}
