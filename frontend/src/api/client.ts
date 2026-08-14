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
  | "audio_unreadable"
  | "invalid_token"
  | "interview_already_complete"
  | "job_not_active"
  | "already_applied"
  | "candidate_not_found"
  | "rate_limited"
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

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", json, form, signal } = options;

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/api${path}`, {
      method,
      signal,
      // Content-Type is set only for JSON. For FormData the browser must
      // set it itself so it can append the multipart boundary.
      headers: json === undefined ? undefined : { "Content-Type": "application/json" },
      body: json !== undefined ? JSON.stringify(json) : form,
    });
  } catch (cause) {
    // An abort is the caller leaving the screen, not a failure to show.
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError("network_error", NETWORK_ERROR_MESSAGE, true, 0);
  }

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
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
}

/** What a candidate is allowed to see. Never carries the rubric. */
export interface PublicJobSummary {
  id: string;
  title: string;
  state: JobState;
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
  sub_scores: SubScoreOut[];
  matched_skills: string[];
  unevidenced_skills: string[];
  resume_intro_conflicts: string[];
  assessment: string | null;

  transcript: string | null;
  audio_url: string | null;
  resume_url: string | null;
  resume_text: string | null;

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
  health: () => request<{ status: string }>("/health"),

  // HR: jobs
  listJobs: () => request<JobSummary[]>("/jobs"),
  getJob: (jobId: string) => request<JobDetail>(`/jobs/${jobId}`),
  createJob: (payload: JobCreate) =>
    request<JobDetail>("/jobs", { method: "POST", json: payload }),
  regenerateRubric: (jobId: string) =>
    request<JobDetail>(`/jobs/${jobId}/rubric/regenerate`, { method: "POST" }),

  // HR: candidates
  listCandidates: (jobId: string) => request<CandidateSummary[]>(`/jobs/${jobId}/candidates`),
  getCandidate: (candidateId: string) => request<CandidateDetail>(`/candidates/${candidateId}`),
  approveCandidate: (candidateId: string) =>
    request<ApprovalResult>(`/candidates/${candidateId}/approve`, { method: "POST" }),
  rejectCandidate: (candidateId: string) =>
    request<CandidateSummary>(`/candidates/${candidateId}/reject`, { method: "POST" }),
  rescreenCandidate: (candidateId: string) =>
    request<CandidateDetail>(`/candidates/${candidateId}/rescreen`, { method: "POST" }),
  getInterviewResult: (candidateId: string) =>
    request<InterviewResult>(`/candidates/${candidateId}/interview`),
  retryEvaluation: (candidateId: string) =>
    request<InterviewResult>(`/candidates/${candidateId}/interview/evaluate`, { method: "POST" }),

  // Candidate: application
  getPublicJob: (jobId: string) => request<PublicJobSummary>(`/apply/${jobId}`),

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
