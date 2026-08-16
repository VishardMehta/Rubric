/*
 * Turning a pasted job description into blocks that can be laid out.
 *
 * What the hiring team supplies is plain text: typed into the Create Job
 * form, or extracted from a PDF. It is not markdown and it is not HTML, but
 * it almost always has structure that a person can see and a `<p>` cannot
 * render - a line ending in a colon acting as a heading, then a run of
 * lines each starting with a bullet or a dash.
 *
 * Rendered as one paragraph that structure is lost and a long posting
 * becomes a wall nobody reads. So this recovers the shape.
 *
 * Two rules it holds to:
 *
 * 1. **Shape only, never meaning.** It decides heading, list item or
 *    paragraph from punctuation and length. It does not classify a section
 *    as "responsibilities" or "requirements", because that would be
 *    guessing at someone's job posting.
 *
 * 2. **Never rewrite a word.** The only text ever removed is a leading
 *    bullet glyph, which is punctuation the renderer supplies instead.
 *    Every remaining character is the author's.
 */

export type JobDescriptionBlock =
  | { kind: "heading"; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; items: string[] };

/** Leading bullet glyphs and list markers, including "1." and "1)". */
const BULLET_RE = /^\s*(?:[-*•·‣▪–—]|\d{1,2}[.)])\s+/;

/** A short line ending in a colon, which is how people write a heading in
 *  plain text: "Responsibilities:", "What you will do:". */
const HEADING_COLON_RE = /^.{2,60}:$/;

/** A short line in title case or caps with no sentence punctuation. */
const HEADING_BARE_RE = /^[A-Z][^.!?]{1,58}$/;

const HEADING_MAX_WORDS = 8;

function isBullet(line: string): boolean {
  return BULLET_RE.test(line);
}

function isHeading(line: string, next: string | undefined): boolean {
  if (isBullet(line)) return false;
  if (HEADING_COLON_RE.test(line)) return true;
  // A bare line only reads as a heading when something follows it that it
  // could be heading. A short last line is the end of the prose.
  if (!next) return false;
  return HEADING_BARE_RE.test(line) && line.split(/\s+/).length <= HEADING_MAX_WORDS;
}

export function parseJobDescription(description: string): JobDescriptionBlock[] {
  const lines = (description || "").split(/\r?\n/);
  const blocks: JobDescriptionBlock[] = [];

  // Consecutive non-blank, non-bullet lines are one paragraph: a PDF
  // extraction hard-wraps mid-sentence, and treating every line break as a
  // paragraph break would shred it.
  let paragraph: string[] = [];
  let items: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length === 0) return;
    blocks.push({ kind: "paragraph", text: paragraph.join(" ").trim() });
    paragraph = [];
  };
  const flushList = () => {
    if (items.length === 0) return;
    blocks.push({ kind: "list", items });
    items = [];
  };
  const flushAll = () => {
    flushParagraph();
    flushList();
  };

  for (let index = 0; index < lines.length; index += 1) {
    const raw = lines[index];
    const line = raw.trim();

    if (!line) {
      flushAll();
      continue;
    }

    if (isBullet(line)) {
      flushParagraph();
      const text = line.replace(BULLET_RE, "").trim();
      if (text) items.push(text);
      continue;
    }

    // A wrapped continuation of the bullet above, rather than a new
    // paragraph: indented, and no bullet of its own.
    if (items.length > 0 && /^\s{2,}/.test(raw)) {
      items[items.length - 1] = `${items[items.length - 1]} ${line}`;
      continue;
    }

    flushList();

    const next = lines.slice(index + 1).find((candidate) => candidate.trim());
    if (isHeading(line, next)) {
      flushParagraph();
      blocks.push({ kind: "heading", text: line.replace(/:$/, "") });
      continue;
    }

    paragraph.push(line);
  }

  flushAll();

  // A description with no blank lines and no bullets comes back as one
  // paragraph, which is correct: there was no structure to recover.
  return blocks.length > 0 ? blocks : [{ kind: "paragraph", text: description.trim() }];
}
