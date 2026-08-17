import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader, Split } from "../../components/layout";
import { Button, Chip, Select, TagInput, TextArea, TextField } from "../../components/primitives";
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
  const [department, setDepartment] = useState("");
  const [location, setLocation] = useState("");
  const [workplaceType, setWorkplaceType] = useState("");
  const [employmentType, setEmploymentType] = useState("full_time");
  const [compensation, setCompensation] = useState("");
  const [sourceDocument, setSourceDocument] = useState<File | null>(null);
  // Needed to clear the control: an <input type="file"> keeps its value
  // after the state behind it is dropped, and a value that is still there
  // means picking the same PDF again fires no change event at all.
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [documentError, setDocumentError] = useState<string | null>(null);
  const [documentLoading, setDocumentLoading] = useState(false);
  // What the last PDF import actually filled in. Shown in the side panel
  // so the extraction is visible rather than silently rewriting the form
  // under the recruiter.
  const [imported, setImported] = useState<
    { filename: string; filled: string[]; kept: string[] } | null
  >(null);
  // What the last import wrote, field by field, as the exact string it
  // wrote. This is what tells an extracted value apart from a typed one on
  // a second upload: if a field still holds precisely what extraction put
  // there, nobody has edited it and the new document may replace it. If it
  // holds anything else, a recruiter typed it and it is theirs.
  //
  // Employment type starts in here because the form defaults it to
  // full_time. That default is not something anyone chose, so without this
  // the first upload would treat it as typed and never fill it in.
  const [extracted, setExtracted] = useState<Record<string, string>>({
    employment_type: "full_time",
  });

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
        // Real columns since database/002_accounts.sql. These used to be
        // appended to the description string, which meant a candidate
        // could never be shown them as fields and HR could never edit one
        // without editing prose.
        department: department.trim() || null,
        location: location.trim() || null,
        workplace_type: workplaceType || null,
        employment_type: employmentType || null,
        compensation: compensation.trim() || null,
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
  }, [valid, title, description, skills, experience, department, location, workplaceType, employmentType, compensation]);

  const clearDocument = useCallback(() => {
    setSourceDocument(null);
    setDocumentError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const importDocument = useCallback(async () => {
    if (!sourceDocument) return;
    setDocumentLoading(true);
    setDocumentError(null);
    // The previous import's summary stays up until this one succeeds. If
    // this PDF cannot be read, the form still holds the last document's
    // values, so a panel that had gone blank would be describing a state
    // the form is not in.
    try {
      const document = await api.extractJobDescription(sourceDocument);
      const facts = document.facts;

      // A second upload replaces what the first one extracted and leaves
      // everything the recruiter typed alone. Ownership is decided by
      // comparing the field against the value the last extraction recorded
      // for it: still equal means untouched, anything else means edited.
      const filled: string[] = [];
      const kept: string[] = [];
      const owned: Record<string, string> = {};

      const fill = (
        key: string,
        label: string,
        value: string | null | undefined,
        current: string,
        set: (next: string) => void,
      ) => {
        const mine = !current.trim() || current === extracted[key];
        if (!mine) {
          // Theirs. Not replaced, and not recorded as extracted either, so
          // it stays theirs through every upload after this one.
          if (value) kept.push(label);
          return;
        }
        // Clearing is deliberate when this document does not state a field
        // the last one did. Otherwise the form ends up as a mix of two
        // documents with no way to tell which line came from which.
        const next = value ?? "";
        set(next);
        if (next) {
          owned[key] = next;
          filled.push(label);
        }
      };

      // Without facts the endpoint behaves as it always did: the raw text
      // goes into the description and HR fills the rest in by hand.
      const body = facts?.description?.trim() || document.text;
      fill("description", "Description", body, description, setDescription);
      setTouched((current) => ({ ...current, description: true }));

      if (facts) {
        fill("title", "Job title", facts.title, title, setTitle);
        fill("department", "Team or department", facts.department, department, setDepartment);
        fill("location", "Location", facts.location, location, setLocation);
        fill("workplace_type", "Workplace type", facts.workplace_type, workplaceType, setWorkplaceType);
        fill("employment_type", "Employment type", facts.employment_type, employmentType, setEmploymentType);
        fill("compensation", "Compensation", facts.compensation, compensation, setCompensation);
        fill("experience", "Experience required", facts.experience, experience, setExperience);

        // Same rule, joined for comparison because the field is a list.
        const currentSkills = skills.join(", ");
        const skillsMine = skills.length === 0 || currentSkills === extracted.skills;
        if (skillsMine) {
          setSkills(facts.skills);
          if (facts.skills.length > 0) {
            owned.skills = facts.skills.join(", ");
            filled.push("Required skills");
          }
        } else if (facts.skills.length > 0) {
          kept.push("Required skills");
        }
      }

      setExtracted(owned);
      setImported({ filename: sourceDocument.name, filled, kept });
    } catch (cause) {
      setDocumentError(cause instanceof ApiError ? cause.message : "The PDF could not be read. Try another file.");
    } finally {
      setDocumentLoading(false);
    }
  }, [
    sourceDocument,
    title,
    description,
    department,
    location,
    workplaceType,
    employmentType,
    compensation,
    experience,
    skills,
    extracted,
  ]);

  // --- Stage B, generating ------------------------------------------------
  // A single real state. No fake sub-steps: the backend makes one model
  // call here, so claiming two would be inventing progress.
  if (stage === "generating") {
    return (
      <>
        <PageHeader title="Post a job" breadcrumb={{ label: "Jobs", to: "/jobs" }} />
        <Split
          left={
            <div className="rb-createjob__generating">
              <LoadingState label="Analyzing job description" block />
              <p className="rb-createjob__generating-body">
                Extracting criteria and assigning point allocations.
              </p>
            </div>
          }
          right={
            // The submitted role stays on screen for the wait. Blanking the
            // panel would make the screen look like it had lost the form.
            <RolePanel
              title={title}
              description={description}
              skills={skills}
              experience={experience}
              department={department}
              location={location}
              workplaceType={workplaceType}
              employmentType={employmentType}
              compensation={compensation}
              imported={imported}
              heading="Being analyzed"
            />
          }
        />
      </>
    );
  }

  // --- Stage C, rubric ----------------------------------------------------
  if (stage === "rubric" && job?.rubric) {
    return (
      <>
        <PageHeader title="Rubric ready" breadcrumb={{ label: "Jobs", to: "/jobs" }} />
        <Split
          left={
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
          }
          right={<CandidatePreview job={job} />}
        />
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

      <Split
        left={
          <>
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

              <fieldset className="rb-createjob__context">
                <legend>Role context</legend>
                <p>Clear location, working arrangement, and employment terms help candidates self-select before they apply.</p>
                <div className="rb-createjob__field-grid">
                  <TextField
                    label="Team or department"
                    optional
                    placeholder="Product engineering"
                    value={department}
                    onChange={(event) => setDepartment(event.target.value)}
                  />
                  <TextField
                    label="Location"
                    optional
                    placeholder="Bengaluru, India"
                    value={location}
                    onChange={(event) => setLocation(event.target.value)}
                  />
                  <Select
                    label="Workplace type"
                    optional
                    value={workplaceType}
                    onChange={(event) => setWorkplaceType(event.target.value)}
                    options={[
                      { value: "", label: "Select arrangement" },
                      // Lowercase, matching jobs_workplace_type_check in
                      // database/002_accounts.sql.
                      { value: "remote", label: "Remote" },
                      { value: "hybrid", label: "Hybrid" },
                      { value: "onsite", label: "On-site" },
                    ]}
                  />
                  <Select
                    label="Employment type"
                    value={employmentType}
                    onChange={(event) => setEmploymentType(event.target.value)}
                    options={[
                      // Underscores, matching jobs_employment_type_check in
                      // database/002_accounts.sql. Hyphens here would fail
                      // the constraint on every insert.
                      { value: "full_time", label: "Full-time" },
                      { value: "part_time", label: "Part-time" },
                      { value: "contract", label: "Contract" },
                      { value: "internship", label: "Internship" },
                    ]}
                  />
                </div>
                <TextField
                  label="Compensation"
                  optional
                  help="Share a range and pay period when it is appropriate for the role."
                  placeholder="₹18–24 LPA · annual base"
                  value={compensation}
                  onChange={(event) => setCompensation(event.target.value)}
                />
              </fieldset>

              <section className="rb-createjob__document" aria-labelledby="job-document-heading">
                <div>
                  <p className="text-label">Optional source</p>
                  <h2 id="job-document-heading" className="text-title-3">Upload a job-description PDF</h2>
                  <p>Rubric extracts the text into the editable field below. Review it before building the rubric.</p>
                </div>
                <div className="rb-createjob__document-actions">
                  <label className="rb-createjob__file-control">
                    <span>{sourceDocument ? sourceDocument.name : "Choose PDF"}</span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="application/pdf,.pdf"
                      onChange={(event) => {
                        setSourceDocument(event.target.files?.[0] ?? null);
                        setDocumentError(null);
                      }}
                    />
                  </label>
                  {/* A sibling, not a child of the label. The file input is
                      stretched across the whole control, so a clear button
                      inside it would be under that overlay and would open
                      the picker instead of clearing anything. */}
                  {sourceDocument && (
                    <button
                      type="button"
                      className="rb-createjob__file-clear"
                      onClick={clearDocument}
                      disabled={documentLoading}
                      aria-label={`Remove ${sourceDocument.name}`}
                      title="Remove this file"
                    >
                      <span aria-hidden="true">✕</span>
                    </button>
                  )}
                  <Button type="button" disabled={!sourceDocument || documentLoading} onClick={() => void importDocument()}>
                    {documentLoading ? "Extracting…" : "Use document text"}
                  </Button>
                </div>
                {documentError && <p className="rb-createjob__document-error">{documentError}</p>}
              </section>

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
        }
          right={
            <RolePanel
              title={title}
              description={description}
              skills={skills}
              experience={experience}
              department={department}
              location={location}
              workplaceType={workplaceType}
              employmentType={employmentType}
              compensation={compensation}
              imported={imported}
              heading="What Rubric will read"
            />
          }
        />
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


/*
 * The right column of Create Job.
 *
 * Before this the form sat at 640px inside a 1280px content area and the
 * remaining half of the screen was empty at every stage. What fills it has
 * to earn the space: this shows the role exactly as the model will receive
 * it, which is the one thing HR cannot otherwise see and the thing that
 * decides how good the rubric is.
 */
function RolePanel({
  title,
  description,
  skills,
  experience,
  department,
  location,
  workplaceType,
  employmentType,
  compensation,
  imported,
  heading,
}: {
  title: string;
  description: string;
  skills: string[];
  experience: string;
  department: string;
  location: string;
  workplaceType: string;
  employmentType: string;
  compensation: string;
  imported: { filename: string; filled: string[]; kept: string[] } | null;
  heading: string;
}) {
  const facts = [
    { label: "Department", value: department },
    { label: "Location", value: location },
    { label: "Workplace", value: WORKPLACE_LABELS[workplaceType] ?? workplaceType },
    { label: "Employment", value: EMPLOYMENT_LABELS[employmentType] ?? employmentType },
    { label: "Compensation", value: compensation },
    { label: "Experience", value: experience },
  ].filter((fact) => fact.value.trim().length > 0);

  const length = description.trim().length;
  const short = length > 0 && length < DESCRIPTION_MIN_CHARS;

  return (
    <aside className="rb-rolepanel" aria-label={heading}>
      <p className="text-label rb-rolepanel__eyebrow">{heading}</p>

      {imported && (
        <div className="rb-rolepanel__imported">
          <p className="rb-rolepanel__imported-file">{imported.filename}</p>
          {imported.filled.length > 0 ? (
            <p className="text-caption">
              Filled {imported.filled.join(", ")}. Anything the document did not
              state was left for you.
            </p>
          ) : (
            <p className="text-caption">
              The text was imported. Nothing else could be read from it with
              confidence, so the remaining fields are yours to fill.
            </p>
          )}
          {/* Said out loud rather than left for HR to notice. A second
              upload that quietly skipped a field would read as a failed
              import. */}
          {imported.kept.length > 0 && (
            <p className="text-caption">
              Kept your {imported.kept.join(", ")}. This document had values for
              those, but you had already edited them.
            </p>
          )}
        </div>
      )}

      <h2 className="text-title-3 rb-rolepanel__title">
        {title.trim() || "Untitled role"}
      </h2>

      {facts.length > 0 && (
        <dl className="rb-rolepanel__facts">
          {facts.map((fact) => (
            <div key={fact.label}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {skills.length > 0 && (
        <div className="rb-rolepanel__skills">
          {skills.map((skill) => (
            <Chip key={skill} tone="neutral">
              {skill}
            </Chip>
          ))}
        </div>
      )}

      <div className="rb-rolepanel__body">
        {description.trim() ? (
          <p>{description.trim()}</p>
        ) : (
          <p className="rb-rolepanel__placeholder">
            The description goes to the model as written. The more concretely it
            names the work, the sharper the criteria it produces.
          </p>
        )}
      </div>

      {length > 0 && (
        <p className={`text-caption rb-rolepanel__count${short ? " rb-rolepanel__count--short" : ""}`}>
          {short
            ? `${length} of ${DESCRIPTION_MIN_CHARS} characters needed`
            : `${length} characters`}
        </p>
      )}
    </aside>
  );
}

/*
 * Stage C. The first chance HR gets to see the role the way an applicant
 * will, next to the rubric that was built from it.
 */
function CandidatePreview({ job }: { job: JobDetail }) {
  const facts = [
    { label: "Location", value: job.location },
    { label: "Workplace", value: job.workplace_type ? WORKPLACE_LABELS[job.workplace_type] : null },
    { label: "Employment", value: job.employment_type ? EMPLOYMENT_LABELS[job.employment_type] : null },
    { label: "Compensation", value: job.compensation },
    { label: "Experience", value: job.experience },
  ].filter((fact) => fact.value);

  return (
    <aside className="rb-rolepanel" aria-label="Candidate preview">
      <p className="text-label rb-rolepanel__eyebrow">What candidates will see</p>
      <h2 className="text-title-3 rb-rolepanel__title">{job.title}</h2>

      {facts.length > 0 && (
        <dl className="rb-rolepanel__facts">
          {facts.map((fact) => (
            <div key={fact.label}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {job.skills.length > 0 && (
        <div className="rb-rolepanel__skills">
          {job.skills.map((skill) => (
            <Chip key={skill} tone="neutral">
              {skill}
            </Chip>
          ))}
        </div>
      )}

      <div className="rb-rolepanel__body">
        <p>{job.description}</p>
      </div>

      <p className="text-caption rb-rolepanel__note">
        The rubric is never shown to candidates. It would tell them exactly what
        to say.
      </p>
    </aside>
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
