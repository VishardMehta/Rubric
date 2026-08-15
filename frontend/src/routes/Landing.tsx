import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/primitives";
import "./landing.css";

/*
 * screens.md section 0. The only screen where marketing language is
 * appropriate, and the only screen with its own layout - no HRShell, no
 * CandidateShell. It exists to explain Rubric in one screen and send HR
 * into the product, not to live inside the product's own chrome.
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

export function LandingPage() {
  const navigate = useNavigate();
  const openDashboard = () => navigate("/jobs");

  return (
    <div className="rb-landing">
      <header className="rb-landing__header">
        <span className="rb-landing__brand">
          <img src="/logo.png" alt="" className="rb-landing__mark" />
          Rubric
        </span>
      </header>

      <main className="rb-landing__main">
        <section className="rb-landing__hero">
          <div className="rb-landing__hero-copy">
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
                <p>Apply securely using the private link shared by the hiring team.</p>
                <Link to="/apply" className="rb-landing__candidate-link">
                  Open candidate portal <span aria-hidden="true">→</span>
                </Link>
              </div>
            </div>
          </div>
          <ProductStory />
        </section>

        <section className="rb-landing__steps" aria-label="How Rubric works">
          {FLOW.map((step) => (
            <div key={step.number} className="rb-landing__step">
              <span className="text-label rb-landing__step-number">{step.number}</span>
              <span className="text-label rb-landing__step-eyebrow">{step.eyebrow}</span>
              <h2 className="text-body-strong rb-landing__step-title">{step.title}</h2>
              <p className="text-body rb-landing__step-body">{step.body}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="rb-landing__footer">
        <p className="text-caption rb-landing__footer-text">Rubric · localhost demo</p>
      </footer>
    </div>
  );
}

function ProductStory() {
  return (
    <div className="rb-landing__story-stack" aria-label="Rubric product flow">
      <div className="rb-landing__story rb-landing__story--primary">
        <div className="rb-landing__story-topbar">
          <span className="rb-landing__story-mark" aria-hidden="true">R</span>
          <span>Candidate review</span>
          <span className="rb-landing__story-status">In review</span>
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
                <strong>Candidate dossier</strong>
                <span>Resume, voice introduction, interview</span>
              </div>
            </div>
            <div className="rb-landing__story-score">
              <span>Screening score</span>
              <strong>73</strong>
              <small>Shortlist</small>
            </div>
            <div className="rb-landing__story-evidence">
              <span className="text-label">Evidence across the rubric</span>
              <i />
              <i />
              <i />
            </div>
          </div>
        </div>
        <div className="rb-landing__story-foot">
          <span>Voice interview</span>
          <span>Adaptive questions</span>
        </div>
      </div>
      <div className="rb-landing__story-mini rb-landing__story-mini--rubric">
        <div>
          <p className="text-label">Role rubric</p>
          <strong>What matters for this role</strong>
          <span>Criteria set before candidates apply.</span>
        </div>
        <div className="rb-landing__story-mini-bars" aria-hidden="true">
          <i /><i /><i />
        </div>
      </div>
      <div className="rb-landing__story-mini rb-landing__story-mini--interview">
        <div>
          <p className="text-label">Voice interview</p>
          <strong>Follow the candidate’s thinking</strong>
          <span>Questions adapt as the conversation develops.</span>
        </div>
        <span className="rb-landing__story-mini-orb" aria-hidden="true" />
      </div>
    </div>
  );
}
