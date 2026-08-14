import type { ReactNode } from "react";
import "./layout.css";

interface SectionProps {
  title?: string;
  description?: string;
  /** Sits opposite the title, for a filter row or a tertiary action. */
  aside?: ReactNode;
  children: ReactNode;
}

/**
 * A titled region. Siblings sit 32px apart (design-system.md section 5).
 *
 * A section that already has a heading does not also get a card around it.
 */
export function Section({ title, description, aside, children }: SectionProps) {
  return (
    <section className="rb-section">
      {(title || aside || description) && (
        <div className="rb-section__header">
          {(title || aside) && (
            <div className="rb-section__head">
              {title && (
                <h2 className="text-title-2" style={{ margin: 0 }}>
                  {title}
                </h2>
              )}
              {aside}
            </div>
          )}
          {description && <p className="rb-section__description">{description}</p>}
        </div>
      )}
      {children}
    </section>
  );
}
