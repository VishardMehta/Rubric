import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { Card, PageHeader } from "../../components/layout";
import { Button } from "../../components/primitives";
import { ApiErrorState, LoadingState } from "../../components/feedback";
import { AudioPlayer } from "../../components/domain";
import { ScoreHero } from "../../components/data";
import { api, ApiError } from "../../api/client";
import type { InterviewResult, InterviewTurnOut } from "../../api/client";
import { formatDayMonth, formatResponseTime, formatSlot } from "../../lib/format";
import { recommendationLabel } from "../../lib/tone";
import "./hr.css";

/*
 * screens.md section 5. The outcome of the voice interview, and the screen
 * that carries the demo.
 *
 * One hero score. The three sub-scores are `score-large`, evenly spaced,
 * not in cards. Each transcript turn shows which rubric criteria that
 * question probed, which is the visible proof that the questions were
 * planned rather than random.
 */

export function InterviewResultPage() {
  const { jobId = "", candidateId = "" } = useParams();
  const navigate = useNavigate();

  const [result, setResult] = useState<InterviewResult | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getInterviewResult(candidateId)
      .then((loaded) => !cancelled && setResult(loaded))
      .catch((cause) => !cancelled && setFailure(cause));
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  async function retryEvaluation() {
    setRetrying(true);
    try {
      setResult(await api.retryEvaluation(candidateId));
      setFailure(null);
    } catch (cause) {
      setFailure(cause instanceof ApiError ? cause : null);
    } finally {
      setRetrying(false);
    }
  }

  const backToCandidate = (
    <Button onClick={() => navigate(`/jobs/${jobId}/candidates/${candidateId}`)}>
      Back to candidate
    </Button>
  );

  if (failure) {
    return (
      <>
        <PageHeader title="Interview result" breadcrumb={{ label: "Jobs", to: "/jobs" }} />
        <ApiErrorState error={failure} title="This interview result could not be loaded" />
      </>
    );
  }

  if (!result) return <LoadingState label="Loading interview result" block />;

  // Reached before the interview finished: there is nothing to show, so
  // send them back rather than rendering an empty result (screens.md 5).
  if (result.status === "not_started" || result.status === "in_progress") {
    return <Navigate to={`/jobs/${jobId}/candidates/${candidateId}`} replace />;
  }

  // Complete but not yet evaluated. The answers are all saved; only the
  // final scoring call is missing.
  if (result.overall_score === null) {
    return (
      <>
        <PageHeader
          title="Interview result"
          breadcrumb={{ label: result.job_title, to: `/jobs/${jobId}` }}
          actions={backToCandidate}
        />
        <div className="rb-result__pending">
          <LoadingState label="Reviewing the interview" block />
          <p className="rb-result__pending-body">
            Scoring {spellOut(result.turns.length)} answers against the rubric.
          </p>
          <Button onClick={() => void retryEvaluation()} loading={retrying}>
            Retry evaluation
          </Button>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Interview result"
        breadcrumb={{ label: result.job_title, to: `/jobs/${jobId}` }}
        subtitle={`${result.candidate_name} · ${result.turns.length} questions · Completed ${formatDayMonth(result.completed_at)}`}
        actions={backToCandidate}
      />

      <div className="rb-result">
        <section className="rb-result__score-region" aria-label="Interview evaluation summary">
          <div>
            <p className="text-label rb-result__score-context">Interview evaluation</p>
            <ScoreHero
              label="Overall"
              score={result.overall_score}
              band={result.band}
              bandLabel={recommendationLabel(result.recommendation)}
            />
          </div>
          <p className="rb-result__score-note">
            An evidence-based summary of {spellOut(result.turns.length)} recorded answers,
            assessed against this role’s interview rubric.
          </p>
        </section>

        {/* Three sub-scores, evenly spaced, not in cards.

            Set in neutral ink rather than coloured. screens.md section 5
            allows colouring them when they cross a band boundary, but the
            backend sends exactly one band, for the overall score, and
            deriving three more here would mean the frontend computing a
            band from a number - the one thing it must never do
            (design-system.md section 3). Painting all three with the
            overall band would be worse still: it would assert that a
            weak communication score is "strong" because the total was. */}
        <div className="rb-subscores">
          <SubScore label="Technical" score={result.technical_score} />
          <SubScore label="Communication" score={result.communication_score} />
          <SubScore label="Experience" score={result.experience_score} />
        </div>

        <div className="rb-result__lists">
          <Card>
            <h2 className="text-title-3 rb-candidate__card-title">Strengths</h2>
            <PlainList items={result.strengths} empty="No specific strengths were recorded." />
          </Card>
          <Card>
            {/* Concerns are not red. They are observations, not failures. */}
            <h2 className="text-title-3 rb-candidate__card-title">Concerns</h2>
            <PlainList items={result.concerns} empty="No specific concerns were recorded." />
          </Card>
        </div>

        <section className="rb-transcript-section">
          <h2 className="text-title-2 rb-transcript-section__title">Transcript</h2>
          <div className="rb-turns">
            {result.turns.map((turn) => (
              <Turn key={turn.slot} turn={turn} />
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

function SubScore({ label, score }: { label: string; score: number | null }) {
  return (
    <div className="rb-subscore">
      <p className="text-label rb-subscore__label">{label}</p>
      <p className="rb-subscore__value">{score ?? 0}</p>
      <p className="rb-subscore__unit">out of 100</p>
    </div>
  );
}

function Turn({ turn }: { turn: InterviewTurnOut }) {
  return (
    <article className="rb-turn">
      <span className="rb-turn__slot text-mono">{formatSlot(turn.slot)}</span>
      <div className="rb-turn__body">
        <h3 className="rb-turn__question">{turn.question}</h3>
        <div className="rb-turn__meta">
          {/* The criteria this question probed. Proof the interview was
              planned against the rubric rather than improvised. */}
          <span className="text-label rb-turn__criteria">{turn.criteria.join(" · ")}</span>
          {turn.response_time_seconds !== null && (
            <span className="rb-turn__time">{formatResponseTime(turn.response_time_seconds)}</span>
          )}
        </div>
        {turn.answer_text ? (
          <p className="rb-turn__answer">{turn.answer_text}</p>
        ) : (
          <p className="rb-turn__unanswered">This question was not answered.</p>
        )}
        {turn.audio_url && (
          <AudioPlayer src={turn.audio_url} label={`Answer to question ${turn.slot}`} />
        )}
      </div>
    </article>
  );
}

function PlainList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <p className="rb-result__empty">{empty}</p>;
  return (
    <ul className="rb-result__list">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

/** Mid-sentence in prose, so the count reads as language (see the same
 *  helper on the interview ready screen). */
function spellOut(count: number): string {
  const words: Record<number, string> = {
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
  };
  return words[count] ?? String(count);
}
