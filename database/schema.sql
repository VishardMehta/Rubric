-- Rubric database schema
--
-- Run this once in the Supabase SQL editor for a fresh project.
-- Source of truth: docs/backend.md section 3. If the two ever disagree,
-- docs/backend.md wins and this file should be updated to match.
--
-- Re-running this on a project that already has these tables will fail on
-- the first create. To start over, uncomment the reset block directly
-- below. It destroys all data in these five tables.

-- ---------------------------------------------------------------------
-- Reset (uncomment to wipe and rebuild)
-- ---------------------------------------------------------------------
-- drop table if exists interview_results cascade;
-- drop table if exists interview_turns   cascade;
-- drop table if exists interviews        cascade;
-- drop table if exists candidates        cascade;
-- drop table if exists jobs              cascade;

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- Jobs
-- ---------------------------------------------------------------------

create table jobs (
  id           uuid primary key default gen_random_uuid(),
  title        text not null,
  description  text not null,
  skills       text[] not null default '{}',
  experience   text,
  rubric       jsonb,                      -- null while state = 'analyzing'
  state        text not null default 'analyzing',
  created_at   timestamptz not null default now(),

  constraint jobs_state_check
    check (state in ('analyzing', 'active', 'closed')),

  -- A job only becomes active once its rubric exists. Without this, an
  -- active job with a null rubric is representable, and the apply page
  -- and screening would both break on it.
  constraint jobs_active_needs_rubric
    check (state <> 'active' or rubric is not null)
);

-- ---------------------------------------------------------------------
-- Candidates
-- ---------------------------------------------------------------------

create table candidates (
  id                      uuid primary key default gen_random_uuid(),
  job_id                  uuid not null references jobs(id) on delete cascade,
  name                    text not null,
  email                   text not null,
  audio_path              text,          -- storage object path, never a URL
  transcript              text,
  resume_path             text,          -- storage object path
  resume_text             text,          -- extracted and normalised
  screening_score         int,           -- 0 to 100
  screening_band          text,          -- strong | borderline | weak
  sub_scores              jsonb,         -- list[SubScore], backend.md 5.2
  matched_skills          text[] not null default '{}',
  unevidenced_skills      text[] not null default '{}',
  resume_intro_conflicts  text[] not null default '{}',
  assessment              text,          -- prose reasoning
  recommendation          text,          -- shortlist | review | reject
  state                   text not null default 'applied',
  created_at              timestamptz not null default now(),

  -- One application per person per job. Re-application and retakes are
  -- out of scope (product.md section 7), and without this a candidate
  -- who double clicks Submit appears twice in the ranked list.
  -- POST /apply maps the resulting error to a readable message.
  constraint candidates_one_application_per_job
    unique (job_id, email),

  constraint candidates_state_check
    check (state in ('applied', 'screening', 'screened', 'approved',
                     'rejected', 'interviewing', 'interviewed')),

  constraint candidates_score_range
    check (screening_score is null or screening_score between 0 and 100),

  -- The band is derived from the score and written with it, so one
  -- present without the other means something failed halfway.
  constraint candidates_score_and_band_together
    check ((screening_score is null) = (screening_band is null)),

  constraint candidates_band_check
    check (screening_band is null or
           screening_band in ('strong', 'borderline', 'weak')),

  constraint candidates_recommendation_check
    check (recommendation is null or
           recommendation in ('shortlist', 'review', 'reject'))
);

-- Ranked candidate list for a job, highest score first. Candidates still
-- being screened have a null score and sort last.
create index candidates_job_score_idx
  on candidates (job_id, screening_score desc nulls last);

-- ---------------------------------------------------------------------
-- Interviews
-- ---------------------------------------------------------------------

create table interviews (
  id              uuid primary key default gen_random_uuid(),
  -- unique: one interview per candidate. Retakes are out of scope.
  candidate_id    uuid not null unique references candidates(id) on delete cascade,
  token           text not null unique,
  plan            jsonb,                 -- InterviewPlan, backend.md 5.3
  state_object    jsonb not null default '{}'::jsonb,  -- backend.md section 6
  total_questions int,
  status          text not null default 'not_started',
  started_at      timestamptz,
  completed_at    timestamptz,
  created_at      timestamptz not null default now(),

  constraint interviews_status_check
    check (status in ('not_started', 'in_progress', 'complete', 'evaluated')),

  constraint interviews_total_questions_range
    check (total_questions is null or total_questions between 1 and 20)
);

-- Every candidate-facing interview request arrives by token.
create index interviews_token_idx on interviews (token);

-- ---------------------------------------------------------------------
-- Turns
-- ---------------------------------------------------------------------

create table interview_turns (
  id                    uuid primary key default gen_random_uuid(),
  interview_id          uuid not null references interviews(id) on delete cascade,
  slot                  int not null,     -- 1-indexed
  question              text not null,
  criterion_ids         text[] not null default '{}',
  answer_text           text,
  answer_audio_path     text,
  answer_scores         jsonb,            -- list[AnswerScore], backend.md 5.4
  response_time_seconds int,
  asked_at              timestamptz not null default now(),
  answered_at           timestamptz,

  -- Answers are persisted per turn so a mid-interview refresh resumes at
  -- the right question rather than restarting.
  unique (interview_id, slot),

  constraint interview_turns_slot_positive
    check (slot > 0),

  constraint interview_turns_response_time_non_negative
    check (response_time_seconds is null or response_time_seconds >= 0)
);

-- ---------------------------------------------------------------------
-- Results
-- ---------------------------------------------------------------------

create table interview_results (
  interview_id         uuid primary key references interviews(id) on delete cascade,
  overall_score        int not null,
  technical_score      int not null,
  communication_score  int not null,
  experience_score     int not null,
  band                 text not null,
  strengths            text[] not null default '{}',
  concerns             text[] not null default '{}',
  recommendation       text not null,
  created_at           timestamptz not null default now(),

  constraint interview_results_scores_range
    check (overall_score       between 0 and 100
       and technical_score     between 0 and 100
       and communication_score between 0 and 100
       and experience_score    between 0 and 100),

  constraint interview_results_band_check
    check (band in ('strong', 'borderline', 'weak')),

  constraint interview_results_recommendation_check
    check (recommendation in ('shortlist', 'review', 'reject'))
);

-- ---------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------
--
-- Tables created through the Supabase dashboard get RLS enabled by
-- default. Tables created from SQL, like these, do NOT. Enabling it here
-- is what makes the posture in docs/backend.md section 3 actually true.
--
-- No policies are defined, which means: the backend's service_role key
-- bypasses RLS and works normally, while the project's public anon key
-- can read nothing. The frontend never holds a Supabase credential, so
-- it loses no access. Without this, anyone with the project URL and the
-- anon key could read every transcript, score and resume.

alter table jobs               enable row level security;
alter table candidates         enable row level security;
alter table interviews         enable row level security;
alter table interview_turns    enable row level security;
alter table interview_results  enable row level security;

-- ---------------------------------------------------------------------
-- Storage buckets
-- ---------------------------------------------------------------------
--
-- Created here rather than by hand so they cannot be missed, and so they
-- cannot accidentally be made public. These hold candidate voice
-- recordings and resumes; public buckets would expose them to anyone
-- holding the object URL.
--
-- The database stores object paths only. The API resolves a path to a
-- short lived signed URL at response time.

insert into storage.buckets (id, name, public)
values
  ('introductions', 'introductions', false),
  ('answers',       'answers',       false),
  ('resumes',       'resumes',       false)
on conflict (id) do nothing;
