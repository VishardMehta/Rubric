import "./data.css";

export interface Stat {
  value: string | number;
  label: string;
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
        <div key={stat.label} className="rb-stat-row__item">
          <dd className="rb-stat-row__value">{stat.value}</dd>
          <dt className="rb-stat-row__label">{stat.label}</dt>
        </div>
      ))}
    </dl>
  );
}
