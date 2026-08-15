-- Rubric migration 002: HR accounts, job ownership, and the columns the
-- later phases need.
--
-- Run this once in the Supabase SQL editor, after database/schema.sql.
-- Safe to re-run: every statement is guarded.
--
-- database/schema.sql is NOT edited by this file. It stays the record of
-- the original five-table design, and this file is the record of what was
-- added afterwards and why.
--
-- Ordering note: database/seed.sql inserts jobs with no owner. That is why
-- jobs.owner_id is nullable and why the first registered account claims
-- every ownerless job. If you re-run seed.sql AFTER creating your account,
-- those new rows will be ownerless and therefore invisible in the
-- dashboard. Fix that by re-running the claim by hand:
--
--   update jobs set owner_id = (select id from hr_users order by created_at limit 1)
--   where owner_id is null;

-- ---------------------------------------------------------------------
-- Phase A: accounts and sessions
-- ---------------------------------------------------------------------

create table if not exists hr_users (
  id            uuid primary key default gen_random_uuid(),
  email         text not null unique,   -- always stored lowercased
  name          text not null,
  company       text,
  -- scrypt, hex encoded. See backend/app/services/accounts.py. The salt is
  -- per user, so two accounts with the same password do not share a hash.
  password_hash text not null,
  password_salt text not null,
  created_at    timestamptz not null default now()
);

-- Opaque random session tokens, not JWTs. A JWT cannot be revoked without
-- a server-side list, at which point it is a session table with extra
-- steps. `pyjwt` is also only present as a transitive dependency of
-- supabase and is not declared in pyproject.toml, so relying on it would
-- break the moment that transitive dependency changes.
create table if not exists hr_sessions (
  token      text primary key,
  hr_user_id uuid not null references hr_users(id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index if not exists hr_sessions_user_idx on hr_sessions (hr_user_id);

-- Nullable on purpose: the rows that already exist, including everything
-- from seed.sql, have no owner until the first account claims them.
alter table jobs add column if not exists owner_id uuid references hr_users(id) on delete cascade;
create index if not exists jobs_owner_idx on jobs (owner_id, created_at desc);

-- ---------------------------------------------------------------------
-- Phase B: the job facts the Create Job form already collects
-- ---------------------------------------------------------------------
--
-- Until now these were flattened into the description string by
-- buildDescription() in the frontend and could never be read back out or
-- shown to a candidate as structured fields.

alter table jobs add column if not exists employment_type text;
alter table jobs add column if not exists workplace_type  text;
alter table jobs add column if not exists location        text;
alter table jobs add column if not exists department      text;
alter table jobs add column if not exists compensation    text;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'jobs_employment_type_check') then
    alter table jobs add constraint jobs_employment_type_check
      check (employment_type is null or employment_type in
             ('full_time', 'part_time', 'contract', 'internship'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'jobs_workplace_type_check') then
    alter table jobs add constraint jobs_workplace_type_check
      check (workplace_type is null or workplace_type in ('remote', 'hybrid', 'onsite'));
  end if;
end $$;

-- ---------------------------------------------------------------------
-- Phase C: structured resume profile
-- ---------------------------------------------------------------------
--
-- Null when parsing failed or has not run. Candidate Detail falls back to
-- the raw resume_text, so a null here degrades the screen rather than
-- breaking it.

alter table candidates add column if not exists resume_profile jsonb;

-- ---------------------------------------------------------------------
-- Phase D: interview invitation
-- ---------------------------------------------------------------------
--
-- Set when HR sends the link. Distinct from interviews.created_at, which
-- is when the token was minted: approving and sending are separate acts
-- and HR may approve without sending yet.

alter table interviews add column if not exists invited_at timestamptz;

-- ---------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------
--
-- Same posture as schema.sql: enabled with no policies, so the backend's
-- service_role key works normally and the project's anon key can read
-- nothing. This matters more here than anywhere else in the schema,
-- because hr_users holds password hashes and hr_sessions holds live
-- session tokens.

alter table hr_users    enable row level security;
alter table hr_sessions enable row level security;

-- ---------------------------------------------------------------------
-- Atomic operations
-- ---------------------------------------------------------------------
--
-- PostgREST cannot run a multi-statement transaction, and the supabase
-- python client exposes no transaction API. Anything that has to be
-- all-or-nothing therefore has to be one function called through
-- client.rpc(). These two qualify; the other multi-step writes in the
-- application deliberately do not, because they have a model call in the
-- middle and leave a recoverable partial state on purpose.

-- Registration plus the one-time claim of ownerless jobs.
--
-- Two separate calls would let the insert succeed and the claim fail,
-- leaving a registered user staring at an empty dashboard with their jobs
-- orphaned and no way to reach them.
create or replace function register_hr_user(
  p_email         text,
  p_name          text,
  p_company       text,
  p_password_hash text,
  p_password_salt text
) returns jsonb
language plpgsql
as $$
declare
  v_user    hr_users%rowtype;
  v_first   boolean;
  v_claimed integer := 0;
begin
  -- Serialises concurrent registrations so two accounts cannot both
  -- observe an empty table and both try to claim.
  perform pg_advisory_xact_lock(hashtext('rubric_register_hr_user'));

  select count(*) = 0 into v_first from hr_users;

  insert into hr_users (email, name, company, password_hash, password_salt)
  values (lower(trim(p_email)), p_name, p_company, p_password_hash, p_password_salt)
  returning * into v_user;

  if v_first then
    update jobs set owner_id = v_user.id where owner_id is null;
    get diagnostics v_claimed = row_count;
  end if;

  return jsonb_build_object(
    'id',           v_user.id,
    'email',        v_user.email,
    'name',         v_user.name,
    'company',      v_user.company,
    'created_at',   v_user.created_at,
    'claimed_jobs', v_claimed
  );
end;
$$;

-- Approve a candidate and mint their interview token in one transaction.
--
-- Replaces a read-then-insert-then-update sequence that could interleave:
-- two rapid clicks both saw no interview, both inserted, and the loser hit
-- the interviews.candidate_id unique constraint and surfaced as a 500.
-- `on conflict do nothing` plus the row lock makes this genuinely
-- idempotent instead of idempotent only when nobody double clicks.
create or replace function approve_candidate_atomic(
  p_candidate_id uuid,
  p_token        text
) returns jsonb
language plpgsql
as $$
declare
  v_state text;
  v_token text;
begin
  select state into v_state from candidates where id = p_candidate_id for update;
  if not found then
    raise exception 'candidate_not_found' using errcode = 'no_data_found';
  end if;

  insert into interviews (candidate_id, token)
  values (p_candidate_id, p_token)
  on conflict (candidate_id) do nothing;

  -- Re-read rather than using the insert's RETURNING, which yields nothing
  -- when the conflict path was taken. HR may already have sent the earlier
  -- link, so the existing token is the correct answer and minting a second
  -- one would silently break a link already in someone's inbox.
  select token into v_token from interviews where candidate_id = p_candidate_id;

  if v_state not in ('approved', 'interviewing', 'interviewed') then
    update candidates set state = 'approved' where id = p_candidate_id;
    v_state := 'approved';
  end if;

  return jsonb_build_object('token', v_token, 'state', v_state);
end;
$$;
