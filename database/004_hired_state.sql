-- A terminal 'hired' state for candidates.
--
-- The pipeline had no way to end well. A candidate went applied, screening,
-- screened, approved, interviewing, interviewed, and then stopped: the only
-- terminal state was 'rejected'. HR could record that someone was turned
-- down and could not record that someone was hired, so a finished search
-- looked identical to one still waiting on a decision.
--
-- 'approved' was the other candidate for this and is wrong. It already
-- means "approved for interview" everywhere in the code, in the candidate
-- portal copy and in the approve_candidate_atomic function below. Reusing
-- it would make the same word mean two different points in the pipeline and
-- would make "approved" unreadable in a list.
--
-- Additive only. Existing rows are untouched: nothing is 'hired' until HR
-- says so.

alter table candidates
  drop constraint if exists candidates_state_check;

alter table candidates
  add constraint candidates_state_check
  check (state in ('applied', 'screening', 'screened', 'approved',
                   'rejected', 'interviewing', 'interviewed', 'hired'));

-- approve_candidate_atomic leaves an already-advanced candidate where they
-- are rather than pulling them back to 'approved'. 'hired' has to be in
-- that list for the same reason 'interviewed' is: re-approving a hired
-- candidate, or a double click on a stale screen, must not walk their state
-- backwards. The rest of the function is unchanged from 002_accounts.sql.
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

  select token into v_token from interviews where candidate_id = p_candidate_id;

  if v_state not in ('approved', 'interviewing', 'interviewed', 'hired') then
    update candidates set state = 'approved' where id = p_candidate_id;
    v_state := 'approved';
  end if;

  return jsonb_build_object('token', v_token, 'state', v_state);
end;
$$;
