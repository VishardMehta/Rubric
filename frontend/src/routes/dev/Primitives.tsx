import { useState } from "react";
import {
  Button,
  Chip,
  Divider,
  IconButton,
  Select,
  Spinner,
  TagInput,
  TextArea,
  TextField,
} from "../../components/primitives";
import { Card, PageHeader, Section, Split } from "../../components/layout";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  Modal,
  useToast,
} from "../../components/feedback";
import type { ButtonLevel } from "../../components/primitives";
import "./primitives-page.css";

/**
 * The Phase 5 verification surface. Not part of the product and not
 * reachable in a production build - App.tsx mounts it only under
 * `import.meta.env.DEV`.
 *
 * It exists for two checks that cannot be made from a unit test:
 *
 *   5.2  every primitive rendered in every state, side by side, so a state
 *        that was never styled is visible rather than discovered on a real
 *        screen in Phase 8
 *   5.7  Tab from the top of this page to the bottom without touching the
 *        mouse. Every interactive element must show a focus ring, and the
 *        order must follow the visual order
 */
export function PrimitivesPage() {
  const toast = useToast();
  const [skills, setSkills] = useState<string[]>(["Python", "Django", "PostgreSQL"]);
  const [modalOpen, setModalOpen] = useState(false);
  const [loadingStage, setLoadingStage] = useState(0);

  const levels: ButtonLevel[] = ["primary", "secondary", "tertiary", "destructive"];
  const stages = ["Transcribing introduction", "Scoring against rubric"];

  return (
    <>
      <PageHeader
        title="Primitives"
        subtitle="Phase 5 verification surface. Every component in every state."
        actions={<Button level="primary">Post job</Button>}
      />

      {/* --- Color ------------------------------------------------------ */}
      <Section
        title="Color"
        description="Accent is brand and interaction only, never good or bad. Semantic tones appear as text on their own tint, never as a saturated fill."
      >
        <div className="kp-swatches">
          {[
            ["accent", "--color-accent"],
            ["accent-tint", "--color-accent-tint"],
            ["canvas", "--color-canvas"],
            ["surface", "--color-surface"],
            ["surface-sunken", "--color-surface-sunken"],
            ["hairline", "--color-hairline"],
            ["hairline-strong", "--color-hairline-strong"],
            ["ink", "--color-ink"],
            ["ink-secondary", "--color-ink-secondary"],
            ["ink-tertiary", "--color-ink-tertiary"],
            ["positive", "--color-positive"],
            ["caution", "--color-caution"],
            ["negative", "--color-negative"],
            ["live", "--color-live"],
          ].map(([name, token]) => (
            <div key={token} className="kp-swatch">
              <span className="kp-swatch__chip" style={{ background: `var(${token})` }} />
              <span className="text-caption">{name}</span>
            </div>
          ))}
        </div>
      </Section>

      {/* --- Typography ------------------------------------------------- */}
      <Section
        title="Typography"
        description="Nine text roles plus three number roles. Every number is tabular so a column of scores never shifts as digits change."
      >
        <div className="kp-stack">
          <p className="text-display" style={{ margin: 0 }}>
            Display, the interview question
          </p>
          <p className="text-title-1" style={{ margin: 0 }}>
            Title 1, page titles
          </p>
          <p className="text-title-2" style={{ margin: 0 }}>
            Title 2, section headings
          </p>
          <p className="text-title-3" style={{ margin: 0 }}>
            Title 3, card headings
          </p>
          <p className="text-body-lg" style={{ margin: 0 }}>
            Body large, candidate-facing instructions
          </p>
          <p className="text-body" style={{ margin: 0 }}>
            Body, the default everywhere
          </p>
          <p className="text-body-strong" style={{ margin: 0 }}>
            Body strong, table row primary cell
          </p>
          <p className="text-caption" style={{ margin: 0 }}>
            Caption, metadata and helper text
          </p>
          <p className="text-label" style={{ margin: 0 }}>
            Label, uppercase eyebrow
          </p>
          <p className="text-mono" style={{ margin: 0 }}>
            Mono, interview tokens and ids
          </p>
          <Divider />
          <div className="kp-row kp-row--baseline">
            <span className="text-score-hero band-strong">72</span>
            <span className="text-score-large band-borderline">58</span>
            <span className="text-score-inline band-weak">31</span>
            <span className="text-caption">hero, large, inline</span>
          </div>
        </div>
      </Section>

      {/* --- Buttons ---------------------------------------------------- */}
      <Section
        title="Buttons"
        description="Four levels. Hover shifts the fill one step, pressed shifts one more, and neither moves the button. Destructive is bordered, never filled."
      >
        <div className="kp-stack">
          <div className="kp-row">
            {levels.map((level) => (
              <Button key={level} level={level}>
                {level === "destructive" ? "Reject candidate" : "Approve for interview"}
              </Button>
            ))}
          </div>
          <div className="kp-row">
            {levels.map((level) => (
              <Button key={level} level={level} disabled>
                Disabled
              </Button>
            ))}
          </div>
          <div className="kp-row">
            {levels.map((level) => (
              <Button key={level} level={level} loading>
                Approve for interview
              </Button>
            ))}
          </div>
          <p className="text-caption" style={{ margin: 0 }}>
            Loading keeps the button's width so the row above does not reflow
            mid-request.
          </p>
          <Divider />
          <div className="kp-narrow">
            <Button level="primary" size="large" fullWidth>
              Start interview
            </Button>
          </div>
          <div className="kp-row">
            <IconButton label="Remove">
              <svg width="12" height="12" viewBox="0 0 10 10" fill="none" aria-hidden="true">
                <path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </IconButton>
            <span className="text-caption">IconButton, always has an accessible name</span>
          </div>
        </div>
      </Section>

      {/* --- Inputs ----------------------------------------------------- */}
      <Section
        title="Inputs"
        description="Every input has a visible label. Placeholder text is never the label, and validation happens on blur rather than on submit."
      >
        <Split
          ratio="1:1"
          left={
            <div className="kp-stack">
              <TextField
                label="Job title"
                placeholder="Senior Python Developer"
                help="The role as it will appear to candidates."
              />
              <TextField
                label="Email"
                defaultValue="priya@example"
                error="Enter a complete email address, including the domain."
              />
              <TextField label="Closed field" defaultValue="Not editable" disabled />
              <Select
                label="Experience level"
                optional
                defaultValue=""
                placeholder="Select a level"
                options={[
                  { value: "junior", label: "Junior, 0 to 2 years" },
                  { value: "mid", label: "Mid, 2 to 5 years" },
                  { value: "senior", label: "Senior, 5 years or more" },
                ]}
                help="Used to weight the rubric, not to filter applicants."
              />
            </div>
          }
          right={
            <div className="kp-stack">
              <TagInput
                label="Required skills"
                value={skills}
                onChange={setSkills}
                placeholder="Type a skill, press Enter"
                help="Chips are neutral. Skills are data, not actions."
              />
              <TextArea
                label="Job description"
                minHeight={200}
                placeholder="Paste the full job description. Rubric reads it once and builds the scoring criteria from it."
                help="Longer descriptions produce sharper criteria."
              />
            </div>
          }
        />
      </Section>

      {/* --- Chips ------------------------------------------------------ */}
      <Section
        title="Chips"
        description="Recommendation chips carry semantic color because they carry meaning. Status chips are always neutral, because a pipeline stage is not good or bad."
      >
        <div className="kp-stack">
          <div className="kp-row">
            <Chip tone="positive">Shortlist</Chip>
            <Chip tone="caution">Review</Chip>
            <Chip tone="negative">Reject</Chip>
          </div>
          <div className="kp-row">
            {["Applied", "Screened", "Approved", "Interviewing", "Interviewed"].map((state) => (
              <Chip key={state}>{state}</Chip>
            ))}
          </div>
        </div>
      </Section>

      {/* --- Cards and dividers ----------------------------------------- */}
      <Section
        title="Cards"
        description="A card groups things that are read together. It is not a default container and it never carries a shadow."
      >
        <Split
          left={
            <Card>
              <h3 className="text-title-3" style={{ margin: "0 0 var(--space-2)" }}>
                Standard card
              </h3>
              <p className="text-body prose" style={{ margin: 0, color: "var(--color-ink-secondary)" }}>
                20px padding, hairline border, radius md, no shadow. Cards sit on
                the page rather than above it.
              </p>
            </Card>
          }
          right={
            <Card primary>
              <h3 className="text-title-3" style={{ margin: "0 0 var(--space-2)" }}>
                Primary card
              </h3>
              <p className="text-body prose" style={{ margin: 0, color: "var(--color-ink-secondary)" }}>
                24px padding, used when the card is the main content of the
                screen rather than one item among several.
              </p>
              <div className="kp-row" style={{ marginTop: "var(--space-4)" }}>
                <span className="text-caption">Vertical divider</span>
                <Divider orientation="vertical" />
                <span className="text-caption">between inline items</span>
              </div>
            </Card>
          }
        />
      </Section>

      {/* --- Feedback --------------------------------------------------- */}
      <Section
        title="Empty, error and loading"
        description="Each names what happened, why it matters, and what to do next. Loading labels name real backend work and never advance on a timer."
      >
        <div className="kp-stack">
          <EmptyState
            title="No applications yet"
            body="Share the application link and candidates can apply with a resume and a voice introduction."
            action={<Button level="primary">Copy application link</Button>}
          />

          <ErrorState
            title="Screening could not be completed"
            body="The model provider did not respond in time. The candidate's introduction and transcript are saved."
            action={<Button>Retry screening</Button>}
          />

          <Card>
            <ErrorState
              variant="blocking"
              title="This interview link is no longer valid"
              body="The link may have expired, or the interview may already be complete. If you believe this is a mistake, contact the person who sent you this link."
            />
          </Card>

          <Card>
            <div className="kp-stack">
              <LoadingState label={stages[loadingStage]} />
              <div className="kp-row">
                <Button onClick={() => setLoadingStage((stage) => (stage + 1) % stages.length)}>
                  Advance stage
                </Button>
                <span className="text-caption">
                  In the product this only advances when the backend actually
                  reaches the next stage.
                </span>
              </div>
            </div>
          </Card>

          <div className="kp-row">
            <Button onClick={() => toast.show("Interview link copied")}>Show a toast</Button>
            <Button onClick={() => setModalOpen(true)}>Open the reject modal</Button>
          </div>
        </div>
      </Section>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Reject this candidate?"
        actions={
          <>
            <Button onClick={() => setModalOpen(false)}>Keep candidate</Button>
            <Button level="destructive" onClick={() => setModalOpen(false)}>
              Reject candidate
            </Button>
          </>
        }
      >
        Priya Nair will be marked as rejected. Their screening score and
        transcript are kept, and this can be undone from the candidate page.
      </Modal>

      <div className="kp-row" style={{ marginTop: "var(--space-12)" }}>
        <Spinner size="sm" label="Loading" />
        <Spinner size="md" />
        <span className="text-caption">Spinner, small and medium, inherits currentColor</span>
      </div>
    </>
  );
}
