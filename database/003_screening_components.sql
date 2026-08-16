-- Screening becomes two weighted components.
--
-- Additive only. Existing rows keep their screening_score and sub_scores
-- and simply have no component breakdown, which every read path already
-- treats as "not recorded" rather than as zero.
--
-- Why this exists: one number scored from the resume and the introduction
-- together let a polished CV carry a candidate who could not describe
-- anything they had built, and the reverse. The rubric is now scored twice,
-- once per source, and the two 0-100 results are weighted in Python
-- (SCREENING_RESUME_WEIGHT / SCREENING_VOICE_WEIGHT in
-- app/core/heuristics.py) into the screening_score column that already
-- exists.
--
-- The rubric itself is unchanged: it still totals exactly 100, and each
-- component is a complete scoring of it.

alter table candidates
  add column if not exists resume_score      int,
  add column if not exists voice_score       int,
  add column if not exists voice_sub_scores  jsonb;

-- Same range rule the existing screening_score column carries. Each
-- component is a full 0 to 100 scoring in its own right, not a share of
-- the final total.
alter table candidates
  drop constraint if exists candidates_resume_score_check;
alter table candidates
  add constraint candidates_resume_score_check
  check (resume_score is null or resume_score between 0 and 100);

alter table candidates
  drop constraint if exists candidates_voice_score_check;
alter table candidates
  add constraint candidates_voice_score_check
  check (voice_score is null or voice_score between 0 and 100);

-- The two components are written in the same update as screening_score, so
-- a row carrying one without the other means a partial write got through.
alter table candidates
  drop constraint if exists candidates_screening_components_check;
alter table candidates
  add constraint candidates_screening_components_check
  check ((resume_score is null) = (voice_score is null));

comment on column candidates.resume_score is
  'Rubric scored from the resume alone, 0 to 100. Weighted into screening_score.';
comment on column candidates.voice_score is
  'Rubric scored from the voice introduction alone, 0 to 100. Weighted into screening_score.';
comment on column candidates.voice_sub_scores is
  'list[SubScore] for the voice component. sub_scores holds the resume component.';
