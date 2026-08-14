import "./domain.css";

interface AudioPlayerProps {
  /** A signed URL from Supabase. Null while it is still being minted. */
  src: string | null;
  label: string;
}

/**
 * A real `<audio controls>`.
 *
 * design-system.md section 19 requires audio players to have real
 * controls, not a custom play button with no keyboard support. The native
 * element already gives play, pause, scrub, volume, keyboard operation and
 * screen reader support in every target browser, and a hand-built
 * transport would have to re-earn all of it to look slightly more on
 * brand.
 *
 * `preload="metadata"` so the duration is known without pulling the whole
 * file: a Job Detail page can hold many of these.
 */
export function AudioPlayer({ src, label }: AudioPlayerProps) {
  if (!src) {
    return <p className="rb-audio__missing">This recording is no longer available.</p>;
  }

  return (
    <audio className="rb-audio" src={src} controls preload="metadata" aria-label={label} />
  );
}
