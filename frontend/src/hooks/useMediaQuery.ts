import { useEffect, useState } from "react";

/**
 * Subscribes to a media query.
 *
 * Used where a layout genuinely cannot be expressed in CSS: a table that
 * becomes a list of cards under 768px is two different DOM trees, not one
 * tree with different styles (design-system.md section 10). Rendering both
 * and hiding one with CSS would put both in the accessibility tree and
 * read every row twice.
 *
 * Anything that CSS can express should stay in CSS.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === "undefined" ? false : window.matchMedia(query).matches,
  );

  useEffect(() => {
    const list = window.matchMedia(query);
    const update = () => setMatches(list.matches);
    // Re-read on subscribe: the query may have changed between the initial
    // state and this effect running.
    update();
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, [query]);

  return matches;
}

/** design-system.md section 20: under 768 is the compact layout. */
export const COMPACT_QUERY = "(max-width: 767px)";
