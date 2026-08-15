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
import { rememberEmail } from "../../lib/candidate-applications";

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

export function ApplicationPage() {
  const { jobId = "" } = useParams();
  const navigate = useNavigate();

  const [phase, setPhase] = useState<Phase>("loading");
  const [job, setJob] = useState<PublicJobSummary | null>(null);
  const [loadFailure, setLoadFailure] = useState<ApiError | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [nameTouched, setNameTouched] = useState(false);
  const [emailTouched, setEmailTouched] = useState(false);

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
  const emailError = !emailTouched
    ? undefined
    : email.trim().length === 0
      ? "Enter your email address."
      : !EMAIL_PATTERN.test(email.trim())
        ? "Enter a valid email address."
        : undefined;

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
      setEmailTouched(true);
      if (!canSubmit || !resumeFile || !recording) return;

      setSubmitError(null);
      setResumeServerError(null);
      setPhase("submitting");
      setStageLabel(UPLOAD_LABEL);

      try {
        const created = await submitApplicationStreaming(
          jobId,
          { name: name.trim(), email: email.trim(), resume: resumeFile, audio: recording.blob },
          (stage) => setStageLabel(STAGE_LABELS[stage]),
        );
        // The portal looks applications up by this address, so remembering
        // it is what lets a returning candidate see their status without
        // typing it again. It is a convenience, not a credential.
        rememberEmail(email.trim());
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
            onChange={(event) => setEmail(event.target.value)}
            onBlur={() => setEmailTouched(true)}
            error={emailError}
            disabled={submitting}
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
          <p className="text-body-lg rb-apply__voice-copy">
            Tell us who you are, what you have worked on, and what you built.
            About two minutes is plenty. Your resume covers where you worked;
            this covers how you think.
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
