/*
 * The typed API client. Every network call in the app goes through here.
 *
 * Two rules this file exists to enforce:
 *
 * 1. **One error shape.** The backend returns `{error: {code, message,
 *    retryable}}` for every failure it raises on purpose (backend.md
 *    section 9). `message` is written as user-facing prose, so screens
 *    render it directly and never compose their own copy from a status
 *    code. A network failure with no response is normalised into the same
 *    shape so callers only ever handle `ApiError`.
 *
 * 2. **No derived scores.** The types below mirror the backend response
 *    models exactly. `screening_band`, `band` and `recommendation` arrive
 *    computed. The frontend never turns a number into a band
 *    (design-system.md section 3).
 */

import { clearToken, readToken, writeToken } from "../lib/session";

const BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8123";

// --- Error shape -----------------------------------------------------------

/** Codes the backend can return. Mirrors app/core/errors.py. */
export type ErrorCode =
  | "rubric_generation_failed"
  | "screening_failed"
  | "transcription_failed"
  | "evaluation_failed"
  | "schema_validation_failed"
  | "audio_too_large"
  | "resume_too_large"
  | "resume_not_readable"
  | "resume_wrong_format"
  | "job_description_too_large"
  | "job_description_unreadable"
  | "job_description_wrong_format"
  | "audio_unreadable"
  | "invalid_token"
  | "interview_already_complete"
  | "job_not_active"
  | "already_applied"
  | "candidate_not_found"
  | "rate_limited"
  | "provider_timeout"
  | "cassette_miss"
  | "not_authenticated"
  | "invalid_credentials"
  | "email_already_registered"
  | "weak_password"
  | "internal_error"
  | "network_error";

export class ApiError extends Error {
  readonly code: ErrorCode;
  readonly retryable: boolean;
  readonly status: number;

  constructor(code: ErrorCode, message: string, retryable: boolean, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.retryable = retryable;
    this.status = status;
  }
}

/** True for anything a `Try again` button could plausibly fix. */
export function isRetryable(error: unknown): boolean {
  return error instanceof ApiError && error.retryable;
}

// The one case the backend cannot describe for us: the request never
// arrived. Phrased the same way as a backend message so screens do not
// need a separate branch for it.
const NETWORK_ERROR_MESSAGE =
  "Rubric could not reach the server. Check that the backend is running, then try again.";

// --- Transport -------------------------------------------------------------

interface ErrorEnvelope {
  error?: { code?: string; message?: string; retryable?: boolean };
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: ErrorEnvelope | null = null;
  try {
    body = (await response.json()) as ErrorEnvelope;
  } catch {
    body = null;
  }
  const error = body?.error;
  return new ApiError(
    (error?.code as ErrorCode) ?? "internal_error",
    error?.message ?? "Something went wrong. Try again.",
    error?.retryable ?? response.status >= 500,
    response.status,
  );
}

interface RequestOptions {
  method?: "GET" | "POST";
  json?: unknown;
  form?: FormData;
  signal?: AbortSignal;
}

/*
 * Every request carries the HR bearer token when there is one.
 *
 * Attached here rather than per call so a new HR endpoint cannot be added
 * without it. The candidate routes ignore the header entirely, so sending
 * it on those is harmless and keeps this a single rule with no allowlist
 * to fall out of date.
 */
function authHeaders(): Record<string, string> {
  const token = readToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", json, form, signal } = options;

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/api${path}`, {
      method,
      signal,
      headers: {
        // Content-Type is set only for JSON. For FormData the browser must
        // set it itself so it can append the multipart boundary.
        ...(json === undefined ? {} : { "Content-Type": "application/json" }),
        ...authHeaders(),
      },
      body: json !== undefined ? JSON.stringify(json) : form,
    });
  } catch (cause) {
    // An abort is the caller leaving the screen, not a failure to show.
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError("network_error", NETWORK_ERROR_MESSAGE, true, 0);
  }

  if (!response.ok) {
    const error = await toApiError(response);
    // An expired or revoked session. Dropping the dead token here means
    // every screen returns to the sign-in page without each one needing
    // to handle 401 for itself.
    if (error.code === "not_authenticated") clearToken();
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// --- Types: HR accounts ----------------------------------------------------

/** The signed-in account. Carries no credential material of any kind. */
export interface HRAccount {
  id: string;
  email: string;
  name: string;
  company: string | null;
}

export interface RegisterInput {
  email: string;
  name: string;
  password: string;
  company?: string | null;
}

export interface SessionResponse {
  token: string;
  expires_at: string;
  account: HRAccount;
  /** Pre-existing ownerless jobs this account just claimed. Only ever
   *  non-zero for the very first account. */
  claimed_jobs: number;
}

// --- Types: rubric ---------------------------------------------------------

export type Dimension = "technical" | "communication" | "experience";

export interface Criterion {
  id: string;
  name: string;
  description: string;
  points: number;
  dimension: Dimension;
}

export interface Rubric {
  criteria: Criterion[];
  interview_topics: string[];
}

// --- Types: jobs -----------------------------------------------------------

/** `analyzing` rows are not clickable on the dashboard (screens.md 1). */
export type JobState = "analyzing" | "active" | "closed" | "failed";

export interface JobCreate {
  title: string;
  description: string;
  skills: string[];
  experience: string | null;
  /* Real columns, not appended to the description. The workplace and
   * employment values are constrained in the database, so they must match
   * jobs_workplace_type_check and jobs_employment_type_check exactly. */
  department?: string | null;
  location?: string | null;
  workplace_type?: string | null;
  employment_type?: string | null;
  compensation?: string | null;
}

export interface JobSummary {
  id: string;
  title: string;
  state: JobState;
  created_at: string;
  applicant_count: number;
  shortlisted_count: number;
  interviewed_count: number;
}

export interface JobDetail extends JobSummary {
  description: string;
  skills: string[];
  experience: string | null;
  rubric: Rubric | null;
  department: string | null;
  location: string | null;
  workplace_type: string | null;
  employment_type: string | null;
  compensation: string | null;
}

/** Facts parsed out of an uploaded job description. Every field the
 *  document did not state is null: the parser is told to leave a gap
 *  rather than guess, because a fabricated salary gets published. */
export interface JobFacts {
  title: string | null;
  department: string | null;
  location: string | null;
  workplace_type: string | null;
  employment_type: string | null;
  compensation: string | null;
  skills: string[];
  experience: string | null;
  description: string;
}

export interface JobDescriptionDocument {
  text: string;
  /** Null when parsing failed. The raw text is still usable. */
  facts: JobFacts | null;
}

/** What a candidate is allowed to see. Never carries the rubric. */
export interface PublicJobSummary {
  id: string;
  title: string;
  state: JobState;
  description: string;
  skills: string[];
  experience: string | null;
  created_at: string;
  department: string | null;
  location: string | null;
  workplace_type: string | null;
  employment_type: string | null;
  compensation: string | null;
  /** Whether the address passed to the call has already applied. Answered
   *  by the server from the same (job_id, email) relationship the database
   *  enforces, so Explore can only ever offer roles that applying would
   *  actually accept. False for an anonymous browse. */
  applied: boolean;
}

// --- Types: resume profile -------------------------------------------------

/* Structured for display only. Screening reads the raw resume text against
 * the rubric and remains the only thing that produces a number, so nothing
 * here is ever used to derive or explain a score. Every field is optional
 * because a sparse resume is a real resume, not a parse failure. */
export interface EducationEntry {
  institution: string;
  qualification: string | null;
  field_of_study: string | null;
  period: string | null;
  result: string | null;
}

export interface ExperienceEntry {
  organisation: string;
  role: string | null;
  period: string | null;
  highlights: string[];
}

export interface ResumeProfile {
  headline: string | null;
  education: EducationEntry[];
  experience: ExperienceEntry[];
  skills: string[];
  links: string[];
}

// --- Types: candidate portal -----------------------------------------------

/* What an applicant may see about their own application.
 *
 * Deliberately carries no score, band, recommendation or assessment. The
 * candidate never sees a score, at any point (product.md section 2), and
 * the backend builds this response field by field from a whitelist rather
 * than from a candidate row. Do not widen this type to "reuse" it for an
 * HR screen. */
export type ApplicationStatus =
  | "submitted"
  | "in_review"
  | "interview_ready"
  | "interview_in_progress"
  | "interview_complete"
  | "closed";

export interface CandidateApplication {
  candidate_id: string;
  job_id: string;
  job_title: string;
  applied_at: string;
  status: ApplicationStatus;
  status_label: string;
  status_detail: string;
  /** Present only once the hiring team has sent it, and withdrawn once the
   *  interview is finished. */
  interview_url: string | null;
}

// --- Types: candidates -----------------------------------------------------

export type Band = "strong" | "borderline" | "weak";
export type Recommendation = "shortlist" | "review" | "reject";
export type CandidateState =
  | "applied"
  | "screened"
  | "approved"
  | "interviewing"
  | "interviewed"
  | "rejected";

export interface EvidenceOut {
  source: "introduction" | "resume";
  quote: string;
}

export interface SubScoreOut {
  criterion_id: string;
  criterion_name: string;
  points_awarded: number;
  points_possible: number;
  evidence: EvidenceOut[];
}

export interface CandidateSummary {
  id: string;
  name: string;
  email: string;
  screening_score: number | null;
  screening_band: Band | null;
  recommendation: Recommendation | null;
  matched_count: number;
  skills_total: number;
  state: CandidateState;
  created_at: string;
  /** Present once an interview exists. Job Detail leads with candidates who
   *  have been interviewed and cannot rank them without the score. */
  interview_status: InterviewStatus | null;
  interview_score: number | null;
  interview_band: Band | null;
  /** Which role this applicant is for. Redundant on Job Detail, which
   *  already knows; it is what lets the cross-role directory label a row
   *  without fetching each job separately. */
  job_id: string | null;
  job_title: string | null;
}

export interface CandidateDetail {
  id: string;
  job_id: string;
  job_title: string;
  name: string;
  email: string;
  state: CandidateState;
  created_at: string;

  screening_score: number | null;
  screening_band: Band | null;
  recommendation: Recommendation | null;
  /** The two components behind screening_score, each a full 0-100 scoring
   *  of the same rubric: one from the resume, one from the spoken
   *  introduction, weighted 60/40 on the server. Null on rows screened
   *  before the split. */
  resume_score: number | null;
  voice_score: number | null;
  sub_scores: SubScoreOut[];
  voice_sub_scores: SubScoreOut[];
  matched_skills: string[];
  unevidenced_skills: string[];
  resume_intro_conflicts: string[];
  assessment: string | null;

  transcript: string | null;
  audio_url: string | null;
  resume_url: string | null;
  resume_text: string | null;
  /** Structured for display only. Null when parsing failed or the row
   *  predates the feature, in which case the screen falls back to the raw
   *  resume_text disclosure. */
  resume_profile: ResumeProfile | null;

  interview_status: InterviewStatus | null;
  interview_token: string | null;
}

export interface CandidateCreated {
  id: string;
  job_title: string;
}

export interface ApprovalResult {
  candidate_id: string;
  state: CandidateState;
  interview_token: string;
  interview_path: string;
}

// --- Types: interview ------------------------------------------------------

export type InterviewStatus = "not_started" | "in_progress" | "complete" | "evaluated";

export interface InterviewSession {
  status: InterviewStatus;
  job_title: string;
  candidate_name: string;
  total_questions: number | null;
  current_slot: number | null;
  current_question: string | null;
}

export interface TurnAdvanced {
  status: InterviewStatus;
  next_slot: number | null;
  next_question: string | null;
  total_questions: number | null;
}

export interface InterviewTurnOut {
  slot: number;
  question: string;
  answer_text: string | null;
  criteria: string[];
  response_time_seconds: number | null;
  audio_url: string | null;
}

export interface InterviewResult {
  candidate_id: string;
  candidate_name: string;
  job_title: string;
  status: InterviewStatus;
  total_questions: number | null;
  completed_at: string | null;

  overall_score: number | null;
  technical_score: number | null;
  communication_score: number | null;
  experience_score: number | null;
  band: Band | null;
  strengths: string[];
  concerns: string[];
  recommendation: Recommendation | null;

  turns: InterviewTurnOut[];
}

// --- Routes ----------------------------------------------------------------

export const api = {
  health: () => request<{ status: string; demo_auth?: boolean }>("/health"),

  // HR: accounts
  //
  // register and login are the only calls that receive a token, and both
  // store it immediately. No caller ever handles the raw token, so there
  // is one place it can be persisted and one place it can be dropped.
  register: async (input: RegisterInput) => {
    const session = await request<SessionResponse>("/auth/register", {
      method: "POST",
      json: input,
    });
    writeToken(session.token);
    return session;
  },
  login: async (email: string, password: string) => {
    const session = await request<SessionResponse>("/auth/login", {
      method: "POST",
      json: { email, password },
    });
    writeToken(session.token);
    return session;
  },
  logout: async () => {
    try {
      await request("/auth/logout", { method: "POST" });
    } finally {
      // The local token is dropped even if the server call fails. Being
      // signed out locally while a row lingers is recoverable; the reverse
      // leaves someone looking at a workspace they think they left.
      clearToken();
    }
  },
  me: () => request<HRAccount>("/auth/me"),

  // HR: jobs
  listJobs: () => request<JobSummary[]>("/jobs"),
  getJob: (jobId: string) => request<JobDetail>(`/jobs/${jobId}`),
  createJob: (payload: JobCreate) =>
    request<JobDetail>("/jobs", { method: "POST", json: payload }),
  extractJobDescription: (document: File) => {
    const form = new FormData();
    form.append("document", document, document.name);
    return request<JobDescriptionDocument>("/jobs/description-document", { method: "POST", form });
  },
  regenerateRubric: (jobId: string) =>
    request<JobDetail>(`/jobs/${jobId}/rubric/regenerate`, { method: "POST" }),

  // HR: candidates
  listCandidates: (jobId: string) => request<CandidateSummary[]>(`/jobs/${jobId}/candidates`),
  /** Every applicant across the account's roles, in one request. The
   *  directory used to fan out over listCandidates, one call per job. */
  listAllCandidates: () => request<CandidateSummary[]>("/candidates"),
  getCandidate: (candidateId: string) => request<CandidateDetail>(`/candidates/${candidateId}`),
  approveCandidate: (candidateId: string) =>
    request<ApprovalResult>(`/candidates/${candidateId}/approve`, { method: "POST" }),
  rejectCandidate: (candidateId: string) =>
    request<CandidateSummary>(`/candidates/${candidateId}/reject`, { method: "POST" }),
  rescreenCandidate: (candidateId: string) =>
    request<CandidateDetail>(`/candidates/${candidateId}/rescreen`, { method: "POST" }),
  reparseResume: (candidateId: string) =>
    request<CandidateDetail>(`/candidates/${candidateId}/reparse-resume`, { method: "POST" }),
  getInterviewResult: (candidateId: string) =>
    request<InterviewResult>(`/candidates/${candidateId}/interview`),
  retryEvaluation: (candidateId: string) =>
    request<InterviewResult>(`/candidates/${candidateId}/interview/evaluate`, { method: "POST" }),

  // Candidate: application
  /** Every active role. Pass the signed-in candidate's address and each
   *  row comes back flagged with whether they have already applied. */
  listPublicJobs: (email?: string) =>
    request<PublicJobSummary[]>(
      email ? `/apply?email=${encodeURIComponent(email)}` : "/apply",
    ),
  listApplications: (email: string) =>
    request<CandidateApplication[]>(`/applications?email=${encodeURIComponent(email)}`),
  getPublicJob: (jobId: string, email?: string) =>
    request<PublicJobSummary>(
      email ? `/apply/${jobId}?email=${encodeURIComponent(email)}` : `/apply/${jobId}`,
    ),

  // Candidate: interview
  getSession: (token: string) => request<InterviewSession>(`/interview/${token}`),
  startInterview: (token: string) =>
    request<InterviewSession>(`/interview/${token}/start`, { method: "POST" }),
  submitAnswer: (
    token: string,
    input: { slot: number; audio: Blob; responseTimeSeconds?: number },
  ) => {
    const form = new FormData();
    form.append("slot", String(input.slot));
    if (input.responseTimeSeconds !== undefined) {
      form.append("response_time_seconds", String(input.responseTimeSeconds));
    }
    form.append("audio", input.audio, `answer.${audioExtension(input.audio)}`);
    return request<TurnAdvanced>(`/interview/${token}/answer`, { method: "POST", form });
  },
};

/** Stage identifiers streamed mid-turn. Mirrors the STAGE_* constants in
 *  backend/app/api/interview.py. The wording shown to the candidate lives
 *  in the interview screen, not here. */
export type TurnStage = "transcribing" | "preparing" | "reviewing";

/** Stage identifiers streamed during application submission. Mirrors the
 *  STAGE_* constants in backend/app/api/apply.py. */
export type ApplicationStage = "reading_resume" | "transcribing" | "scoring";

/**
 * Reads a newline-delimited JSON response: zero or more `{stage}` lines,
 * then exactly one `{result}` or `{error}` line.
 *
 * Shared by every candidate-facing action slow enough to need real
 * progress (design-system.md section 15): the interview turn and the
 * application submission both take several seconds with the candidate
 * watching, and section 22 forbids a label that advances on a timer, so
 * the stages have to come from the server rather than be guessed at here.
 *
 * The status code is committed to 200 before anything slow can fail, so a
 * mid-stream failure arrives as an `{error}` line instead of a status
 * code. It carries the same envelope as every other error and is raised
 * as the same ApiError, so callers handle failure identically either way.
 */
async function streamNdjson<Stage extends string, Result>(
  path: string,
  form: FormData,
  onStage: (stage: Stage) => void,
  signal?: AbortSignal,
): Promise<Result> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/api${path}`, {
      method: "POST",
      body: form,
      signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError("network_error", NETWORK_ERROR_MESSAGE, true, 0);
  }

  // A failure before the first line still gets a real status code.
  if (!response.ok) throw await toApiError(response);
  if (!response.body) throw new ApiError("internal_error", "Something went wrong. Try again.", true, 0);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: Result | null = null;

  const handleLine = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const message = JSON.parse(trimmed) as {
      stage?: Stage;
      result?: Result;
      error?: { code?: string; message?: string; retryable?: boolean };
    };
    if (message.stage) onStage(message.stage);
    if (message.result) result = message.result;
    if (message.error) {
      throw new ApiError(
        (message.error.code as ErrorCode) ?? "internal_error",
        message.error.message ?? "Something went wrong. Try again.",
        message.error.retryable ?? true,
        200,
      );
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // A chunk can split mid-line, so only whole lines are parsed and the
    // remainder is carried into the next read.
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) handleLine(line);
  }
  if (buffer) handleLine(buffer);

  if (!result) {
    // The stream ended without a verdict, which means the connection died
    // partway. Retryable; the caller decides what "try again" means.
    throw new ApiError("network_error", NETWORK_ERROR_MESSAGE, true, 0);
  }
  return result;
}

/** Submits an interview answer and reports each backend stage as it
 *  begins. See `streamNdjson` for the wire format and the reasoning. */
export function submitAnswerStreaming(
  token: string,
  input: { slot: number; audio: Blob; responseTimeSeconds?: number },
  onStage: (stage: TurnStage) => void,
  signal?: AbortSignal,
): Promise<TurnAdvanced> {
  const form = new FormData();
  form.append("slot", String(input.slot));
  if (input.responseTimeSeconds !== undefined) {
    form.append("response_time_seconds", String(input.responseTimeSeconds));
  }
  form.append("audio", input.audio, `answer.${audioExtension(input.audio)}`);
  return streamNdjson<TurnStage, TurnAdvanced>(
    `/interview/${token}/answer/stream`,
    form,
    onStage,
    signal,
  );
}

/** Submits a candidate application and reports each backend stage as it
 *  begins. See `streamNdjson` for the wire format and the reasoning. */
export function submitApplicationStreaming(
  jobId: string,
  input: { name: string; email: string; resume: File; audio: Blob },
  onStage: (stage: ApplicationStage) => void,
  signal?: AbortSignal,
): Promise<CandidateCreated> {
  const form = new FormData();
  form.append("name", input.name);
  form.append("email", input.email);
  form.append("resume", input.resume, input.resume.name);
  // The extension is how the transcription provider infers the container,
  // so it is derived from the recorded MIME type rather than hardcoded:
  // Chrome gives webm, Safari gives mp4 (backend.md 7.2).
  form.append("audio", input.audio, `introduction.${audioExtension(input.audio)}`);
  return streamNdjson<ApplicationStage, CandidateCreated>(
    `/apply/${jobId}/stream`,
    form,
    onStage,
    signal,
  );
}

/** Maps a recorded blob's MIME type to the file extension the backend
 *  expects. Chrome emits `audio/webm;codecs=opus`, Safari `audio/mp4`. */
export function audioExtension(blob: Blob): string {
  const type = blob.type.split(";")[0].trim().toLowerCase();
  switch (type) {
    case "audio/mp4":
      return "mp4";
    case "audio/ogg":
      return "ogg";
    case "audio/mpeg":
      return "mp3";
    case "audio/wav":
    case "audio/x-wav":
      return "wav";
    default:
      return "webm";
  }
}
