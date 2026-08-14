import "./primitives.css";

interface DividerProps {
  orientation?: "horizontal" | "vertical";
}

/** A hairline rule. Reach for this before a shadow (DESIGN.md item 7). */
export function Divider({ orientation = "horizontal" }: DividerProps) {
  return (
    <hr
      className={`rb-divider rb-divider--${orientation}`}
      aria-orientation={orientation}
    />
  );
}
