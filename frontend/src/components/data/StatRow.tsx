import "./data.css";

export interface Stat {
  value: string | number;
  label: string;
  /**
   * Puts the label first: `Posted 14 Aug` rather than `14 Aug posted`.
   *
   * Counts read naturally as number-then-noun, but a date does not, and
   * screens.md section 3 writes it the other way round in the same row.
   */
  labelFirst?: boolean;
}

/**
 * design-system.md section 7: "Statistics are not cards."
 *
 * Text on canvas with generous spacing, not four bordered boxes. Four
 * boxes across the top of a page is the single fastest way to make a
 * hiring tool look like a template dashboard, and it is on the
 * anti-pattern list in section 22.
 */
export function StatRow({ stats }: { stats: Stat[] }) {
  return (
    <dl className="rb-stat-row">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className={`rb-stat-row__item${stat.labelFirst ? " rb-stat-row__item--label-first" : ""}`}
        >
          <dd className="rb-stat-row__value">{stat.value}</dd>
          <dt className="rb-stat-row__label">{stat.label}</dt>
        </div>
      ))}
    </dl>
  );
}
