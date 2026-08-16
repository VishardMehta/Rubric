import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/primitives";
import { VoiceOrb } from "../components/domain";
import "./landing.css";

/*
 * screens.md section 0. The only screen where marketing language is
 * appropriate, and the only screen with its own layout - no HRShell, no
 * CandidateShell. It exists to explain Rubric in one screen and send HR
 * into the product, not to live inside the product's own chrome.
 *
 * The right-hand preview is a real depiction of the product, not a stock
 * illustration: the numbers add up, the rubric points total 100, and the
 * evidence quotes are the shape of quotes screening actually returns. It
 * animates once on arrival and then holds. A landing page that loops
 * forever is a page nobody can read.
 */

const FLOW = [
  {
    number: "01",
    eyebrow: "Screening",
    title: "A shared standard from the start.",
    body: "Turn the role into an explicit rubric before the first application arrives.",
  },
  {
    number: "02",
    eyebrow: "Voice",
    title: "Hear how people think.",
    body: "Pair a resume with a concise voice introduction, then ask adaptive follow-ups.",
  },
  {
    number: "03",
    eyebrow: "Evidence",
    title: "Make every score explainable.",
    body: "Review the evidence, transcript, and criteria behind every recommendation.",
  },
];

/* The rubric shown throughout the page. Points total exactly 100, the same
   rule the real generator is validated against, because a marketing page
   that breaks the product's own contract is the first thing a careful
   viewer notices. */
const CRITERIA = [
  { name: "Python and Django", points: 30, awarded: 24 },
  { name: "SQL and data modelling", points: 25, awarded: 17 },
  { name: "System design", points: 20, awarded: 13 },
  { name: "Technical communication", points: 15, awarded: 12 },
  { name: "Relevant experience", points: 10, awarded: 7 },
];

export function LandingPage() {
  const navigate = useNavigate();
  const openDashboard = () => navigate("/jobs");

  return (
    <div className="rb-landing">
      <main className="rb-landing__main">
        <section className="rb-landing__hero">
          <div className="rb-landing__hero-copy">
            <span className="rb-landing__brand">
              <img src="/logo.png" alt="" className="rb-landing__mark" />
              Rubric
            </span>
            <p className="text-label rb-landing__eyebrow">Structured hiring, with context</p>
            <h1 className="text-display rb-landing__headline">
              See the person behind the application.
            </h1>
            <p className="text-body-lg rb-landing__subhead">
              Rubric turns each role into a shared standard, screens candidates
              against it, and conducts intelligent voice interviews that make the
              reasoning visible.
            </p>
            <div className="rb-landing__entry-points">
              <div className="rb-landing__entry">
                <p className="text-label">For hiring teams</p>
                <p>Build a rubric, review evidence, and decide with consistency.</p>
                <Button level="primary" size="large" onClick={openDashboard}>
                  Go to HR dashboard
                </Button>
              </div>
              <div className="rb-landing__entry rb-landing__entry--candidate">
                <p className="text-label">For candidates</p>
                <p>Sign in to browse open roles, apply, and track every application.</p>
                <Link to="/apply" className="rb-landing__candidate-link">
                  Open candidate portal <span aria-hidden="true">→</span>
                </Link>
              </div>
            </div>
          </div>
          <CandidateReview />
        </section>

        {/* One full-width supporting row under the whole hero, not a pair
            of cards tucked inside the right column. They support the hero
            as a unit, so they span it. */}
        <section className="rb-landing__modules" aria-label="Rubric product modules">
          <SupportingModules />
        </section>

        <section className="rb-landing__steps" aria-label="How Rubric works">
          {FLOW.map((step, index) => (
            <article key={step.number} className="rb-landing__step">
              <div className="rb-landing__step-copy">
                <span className="text-label rb-landing__step-number">{step.number}</span>
                <span className="text-label rb-landing__step-eyebrow">{step.eyebrow}</span>
                <h2 className="text-body-strong rb-landing__step-title">{step.title}</h2>
                <p className="text-body rb-landing__step-body">{step.body}</p>
              </div>
              <div className="rb-landing__step-visual" aria-hidden="true">
                {index === 0 && <RubricAllocation />}
                {index === 1 && <VoiceSample />}
                {index === 2 && <EvidenceSample />}
              </div>
            </article>
          ))}
        </section>
      </main>

      <footer className="rb-landing__footer">
        <p className="text-caption rb-landing__footer-text">Rubric · localhost demo</p>
      </footer>
    </div>
  );
}

/*
 * Counts to a number once, when the element is first seen.
 *
 * Tied to visibility rather than mount so the figures in the section below
 * the fold animate when they are read, not while they are off screen. Held
 * at the final value afterwards: the point is that a score was computed,
 * not that a number is spinning.
 */
function useCountUp(target: number, durationMs = 900) {
  const ref = useRef<HTMLSpanElement>(null);
  const [value, setValue] = useState(0);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setValue(target);
      return;
    }

    let frame = 0;
    let start = 0;
    const step = (now: number) => {
      start = start || now;
      const progress = Math.min(1, (now - start) / durationMs);
      // Ease out: fast to roughly the right answer, then settles, which is
      // how a number being computed reads rather than a timer.
      setValue(Math.round(target * (1 - (1 - progress) ** 3)));
      if (progress < 1) frame = requestAnimationFrame(step);
    };

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();
        frame = requestAnimationFrame(step);
      },
      { threshold: 0.4 },
    );
    observer.observe(node);

    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [target, durationMs]);

  return { ref, value };
}

/* The hero's right column, and nothing else. It used to share a sunken
   frame with the two supporting modules, which made the right side of the
   hero half again as tall as the left. */
function CandidateReview() {
  const score = useCountUp(73);

  return (
    <div className="rb-landing__story rb-landing__story--primary" aria-label="Candidate review">
        <div className="rb-landing__story-topbar">
          <span className="rb-landing__story-mark" aria-hidden="true">R</span>
          <span>Candidate review</span>
          <span className="rb-landing__story-status">
            <i aria-hidden="true" />
            In review
          </span>
        </div>
        <div className="rb-landing__story-workspace">
          <aside className="rb-landing__story-nav" aria-label="Candidate review sections">
            <span>Overview</span>
            <span className="rb-landing__story-nav-active">Screening</span>
            <span>Interview</span>
          </aside>
          <div className="rb-landing__story-body">
            <div className="rb-landing__story-person">
              <span className="rb-landing__story-avatar" aria-hidden="true">AN</span>
              <div>
                <strong>Ananya Nair</strong>
                <span>Resume · Voice introduction</span>
              </div>
              <span className="rb-landing__story-rec">Shortlist</span>
            </div>

            <div className="rb-landing__story-score">
              <div>
                <span>Screening score</span>
                <strong>
                  <span ref={score.ref}>{score.value}</span>
                  <small>/100</small>
                </strong>
              </div>
              {/* Sub-scores summing to the total is the product's core
                  discipline, so the preview shows the sum, not a number
                  arrived at some other way. */}
              <p>Five criteria, each scored against quoted evidence.</p>
            </div>

            <div className="rb-landing__story-criteria">
              {CRITERIA.slice(0, 3).map((criterion, index) => (
                <div
                  key={criterion.name}
                  className="rb-landing__criterion"
                  style={{ animationDelay: `${420 + index * 130}ms` }}
                >
                  <span>{criterion.name}</span>
                  <span className="rb-landing__criterion-track">
                    <i style={{ width: `${(criterion.awarded / criterion.points) * 100}%` }} />
                  </span>
                  <em>
                    {criterion.awarded}<span>/{criterion.points}</span>
                  </em>
                </div>
              ))}
            </div>

            <blockquote className="rb-landing__story-quote">
              <span className="text-label">Evidence · System design</span>
              “we moved the recommendation service to a pre-computed table and
              cut p95 from 900ms to 120ms”
            </blockquote>
          </div>
        </div>
      <div className="rb-landing__story-foot">
        <span>Voice interview</span>
        <span>10 adaptive questions</span>
      </div>
    </div>
  );
}

/* Two broad modules across the full width, in the same sunken frame the
   right column used to carry. */
function SupportingModules() {
  return (
    <div className="rb-landing__story-row">
      <div className="rb-landing__story-mini rb-landing__story-mini--rubric">
        <div>
          <p className="text-label">Role rubric</p>
          <strong>Criteria set before candidates apply</strong>
          <span>Points allocated by what the role depends on.</span>
        </div>
        <div className="rb-landing__story-mini-bars" aria-hidden="true">
          <i /><i /><i />
        </div>
      </div>

      <div className="rb-landing__story-mini rb-landing__story-mini--interview">
        <div>
          <p className="text-label">Voice interview</p>
          <strong>“How did you handle the cold start problem there?”</strong>
          <span>Questions adapt as the conversation develops.</span>
        </div>
        <AmbientOrb size={72} />
      </div>
    </div>
  );
}

/*
 * The interview orb, reused rather than reimplemented.
 *
 * This is the same WebGL component the interview screen runs, in its
 * `idle` state: present and slowly turning, with no analyser because there
 * is no microphone on this page. It honours prefers-reduced-motion itself
 * and falls back to a static gradient where WebGL is unavailable, so this
 * wrapper only has to supply the ref its props require.
 */
function AmbientOrb({ size }: { size: number }) {
  const silent = useRef<AnalyserNode | null>(null);
  return (
    <span className="rb-landing__orb" aria-hidden="true">
      <VoiceOrb state="idle" analyser={silent} size={size} />
    </span>
  );
}

/** 01 Screening: the rubric as an allocation, totalling 100. */
function RubricAllocation() {
  return (
    <div className="rb-landing__viz rb-landing__viz--rubric">
      <div className="rb-landing__viz-head">
        <span className="text-label">Rubric</span>
        <span className="rb-landing__viz-total">100 points</span>
      </div>
      <div className="rb-landing__alloc">
        {CRITERIA.map((criterion, index) => (
          <div
            key={criterion.name}
            className="rb-landing__alloc-row"
            style={{ animationDelay: `${index * 90}ms` }}
          >
            <span>{criterion.name}</span>
            <span className="rb-landing__alloc-track">
              <i style={{ width: `${criterion.points}%` }} />
            </span>
            <em>{criterion.points}</em>
          </div>
        ))}
      </div>
    </div>
  );
}

/** 02 Voice: an ambient orb, a level meter and one adaptive question. */
function VoiceSample() {
  return (
    <div className="rb-landing__viz rb-landing__viz--voice">
      <AmbientOrb size={104} />
      <div className="rb-landing__voice-copy">
        <span className="text-label">Question 4 of 10</span>
        <strong>“What did you change after the first rollout failed?”</strong>
        <span className="rb-landing__meter" aria-hidden="true">
          {Array.from({ length: 22 }).map((_, index) => (
            <i key={index} style={{ animationDelay: `${index * 55}ms` }} />
          ))}
        </span>
      </div>
    </div>
  );
}

/** 03 Evidence: a quote, the criterion it earns points against, the sum. */
function EvidenceSample() {
  return (
    <div className="rb-landing__viz rb-landing__viz--evidence">
      <div className="rb-landing__evidence-card">
        <span className="text-label">SQL and data modelling</span>
        <p>
          “I added a composite index on user_id and score, then dropped the old
          one once the query planner picked it up”
        </p>
        <footer>
          <span>Introduction</span>
          <em>17<span>/25</span></em>
        </footer>
      </div>
      <div className="rb-landing__evidence-sum">
        <span>Sub-scores are verified to sum to the total</span>
        <em>24 + 17 + 13 + 12 + 7 = 73</em>
      </div>
    </div>
  );
}
