import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../../components/layout";
import { Button, Select, TagInput, TextArea, TextField } from "../../components/primitives";
import { ErrorState, LoadingState } from "../../components/feedback";
import { CopyLinkField, RubricPanel } from "../../components/domain";
import { api, ApiError } from "../../api/client";
import type { JobDetail } from "../../api/client";
import { DESCRIPTION_MIN_CHARS } from "../../lib/heuristics";
import "./hr.css";

/*
 * screens.md section 2. Capture the job, then show the rubric that was
 * generated from it.
 *
 * The rubric reveal happens here rather than behind a later click because
 * this is the moment the product explains itself: the criteria and their
 * point allocations are the contract every downstream score is measured
 * against, and HR should meet them before a single candidate applies.
 */

type Stage = "form" | "generating" | "rubric";

const EXPERIENCE_OPTIONS = [
  { value: "", label: "No preference" },
  { value: "0 to 2 years", label: "0 to 2 years" },
  { value: "2 to 4 years", label: "2 to 4 years" },
  { value: "4 to 7 years", label: "4 to 7 years" },
  { value: "7+ years", label: "7+ years" },
];

export function CreateJobPage() {
  const navigate = useNavigate();

  const [stage, setStage] = useState<Stage>("form");
  const [job, setJob] = useState<JobDetail | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [experience, setExperience] = useState("");

  const [touched, setTouched] = useState({ title: false, description: false, skills: false });

  const titleError =
    touched.title && title.trim().length === 0 ? "Enter a job title." : undefined;
  const descriptionError = !touched.description
    ? undefined
    : description.trim().length === 0
      ? "Enter a job description."
      : description.trim().length < DESCRIPTION_MIN_CHARS
        ? "Add more detail so Rubric can build meaningful criteria."
        : undefined;
  const skillsError =
    touched.skills && skills.length === 0 ? "Add at least one required skill." : undefined;

  const valid =
    title.trim().length > 0 &&
    description.trim().length >= DESCRIPTION_MIN_CHARS &&
    skills.length > 0;

  const submit = useCallback(async () => {
    setTouched({ title: true, description: true, skills: true });
    if (!valid) return;

    setFailure(null);
    setStage("generating");
    try {
      const created = await api.createJob({
        title: title.trim(),
        description: description.trim(),
        skills,
        experience: experience || null,
      });
      setJob(created);
      setStage("rubric");
    } catch (cause) {
      // The form data is deliberately kept. The backend saved the job row
      // before generation ran, so the description is not lost either way,
      // and retyping it would be the worst possible response to a
      // provider timeout (screens.md section 2, error state).
      setFailure(cause instanceof ApiError ? cause : null);
      setStage("form");
    }
  }, [valid, title, description, skills, experience]);

  // --- Stage B, generating ------------------------------------------------
  // A single real state. No fake sub-steps: the backend makes one model
  // call here, so claiming two would be inventing progress.
  if (stage === "generating") {
    return (
      <>
        <PageHeader title="Post a job" breadcrumb={{ label: "Jobs", to: "/jobs" }} />
        <div className="rb-createjob__generating">
          <LoadingState label="Analyzing job description" block />
          <p className="rb-createjob__generating-body">
            Extracting criteria and assigning point allocations.
          </p>
        </div>
      </>
    );
  }

  // --- Stage C, rubric ----------------------------------------------------
  if (stage === "rubric" && job?.rubric) {
    return (
      <>
        <PageHeader title="Rubric ready" breadcrumb={{ label: "Jobs", to: "/jobs" }} />
        <div className="rb-createjob__reveal">
          <p className="rb-createjob__lede">
            Every applicant will be scored against these criteria.
          </p>

          <RubricPanel rubric={job.rubric} />

          <div className="rb-createjob__link">
            <h2 className="text-title-3 rb-createjob__link-title">Application link</h2>
            <CopyLinkField
              url={`${window.location.origin}/apply/${job.id}`}
              toastMessage="Application link copied"
              help="Share this with candidates. They apply with a resume and a spoken introduction."
            />
          </div>

          <div className="rb-createjob__actions">
            <Button onClick={() => void regenerate(job, setJob, setStage, setFailure)}>
              Regenerate rubric
            </Button>
            <Button level="primary" onClick={() => navigate(`/jobs/${job.id}`)}>
              Go to job
            </Button>
          </div>
        </div>
      </>
    );
  }

  // --- Stage A, form ------------------------------------------------------
  return (
    <>
      <PageHeader title="Post a job" breadcrumb={{ label: "Jobs", to: "/jobs" }} />

      {failure && (
        <div className="rb-createjob__error">
          <ErrorState
            title="Rubric could not be generated"
            body={failure.message}
            action={<Button onClick={() => void submit()}>Try again</Button>}
          />
        </div>
      )}

      <form
        className="rb-createjob__form"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
        noValidate
      >
        <TextField
          label="Job title"
          help="The role as it will appear to candidates."
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          onBlur={() => setTouched((t) => ({ ...t, title: true }))}
          error={titleError}
        />

        <TextArea
          label="Job description"
          help="Rubric reads this to build the scoring criteria. More detail produces a better rubric."
          minHeight={200}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          onBlur={() => setTouched((t) => ({ ...t, description: true }))}
          error={descriptionError}
        />

        <TagInput
          label="Required skills"
          placeholder="Type a skill and press Enter"
          value={skills}
          onChange={(next) => {
            setSkills(next);
            setTouched((t) => ({ ...t, skills: true }));
          }}
          error={skillsError}
        />

        <Select
          label="Experience required"
          optional
          options={EXPERIENCE_OPTIONS}
          value={experience}
          onChange={(event) => setExperience(event.target.value)}
        />

        <div className="rb-createjob__submit">
          <Button type="submit" level="primary" disabled={!valid}>
            Build rubric
          </Button>
        </div>
      </form>
    </>
  );
}

/**
 * screens.md section 2: regenerate is a secondary action that warns if
 * applicants already exist.
 *
 * The warning is a real one. Candidates already screened were scored
 * against the old criteria, and their scores are not recomputed, so a
 * regenerated rubric would leave one job holding two incompatible sets of
 * numbers.
 */
async function regenerate(
  job: JobDetail,
  setJob: (job: JobDetail) => void,
  setStage: (stage: Stage) => void,
  setFailure: (failure: ApiError | null) => void,
): Promise<void> {
  if (job.applicant_count > 0) {
    const ok = window.confirm(
      `${job.applicant_count} candidate${job.applicant_count === 1 ? " has" : "s have"} already been scored against the current rubric. Their scores will not be recalculated. Regenerate anyway?`,
    );
    if (!ok) return;
  }

  setStage("generating");
  try {
    setJob(await api.regenerateRubric(job.id));
    setStage("rubric");
  } catch (cause) {
    setFailure(cause instanceof ApiError ? cause : null);
    setStage("rubric");
  }
}
