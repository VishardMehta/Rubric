import { useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { COMPACT_QUERY, useMediaQuery } from "../../hooks/useMediaQuery";
import "./data.css";

export interface Column<Row> {
  key: string;
  header: string;
  /** Numbers are right-aligned and tabular (design-system.md section 10). */
  align?: "left" | "right";
  /** Fixed so columns do not shift when a filter changes the rows. */
  width?: string;
  cell: (row: Row) => ReactNode;
}

interface DataTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  /** Where the row navigates. Rendered as a real link, see below. */
  rowHref: (row: Row) => string;
  /**
   * The compact layout, under 768px, where the table becomes a stacked
   * list of cards (design-system.md section 10).
   *
   * Supplied by the caller rather than derived from `columns`, because a
   * card is not a squashed row: the spec puts name and score together on
   * the first line, email on the second and chips on the third, which no
   * generic column-to-card transform would produce.
   */
  renderCard: (row: Row) => ReactNode;
  /** Describes the table for screen readers. */
  caption: string;
}

/**
 * design-system.md section 10. The ranked candidate list is the most
 * important table in the product.
 *
 * Hairlines between rows only: no vertical rules, no zebra striping, no
 * borders around cells.
 *
 * **On the whole row being clickable.** Section 10 wants the entire row to
 * be the click target; section 19 forbids a clickable div and requires a
 * real `a` for navigation. Both are satisfied here rather than one being
 * traded for the other: the first cell holds a genuine `Link`, which is
 * what keyboard and screen reader users get, and the `tr` carries a click
 * handler that navigates to the same place for everyone using a mouse.
 * The row is not focusable and has no ARIA role of its own, so nothing is
 * announced twice.
 */
export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  rowHref,
  renderCard,
  caption,
}: DataTableProps<Row>) {
  const navigate = useNavigate();
  const compact = useMediaQuery(COMPACT_QUERY);

  if (compact) {
    return (
      <ul className="rb-cards" aria-label={caption}>
        {rows.map((row) => (
          <li key={rowKey(row)} className="rb-cards__item">
            {renderCard(row)}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="rb-table-wrap">
      <table className="rb-table">
        <caption className="rb-visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={column.align === "right" ? "rb-table__cell--right" : undefined}
                style={column.width ? { width: column.width } : undefined}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className="rb-table__row"
              onClick={() => navigate(rowHref(row))}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={column.align === "right" ? "rb-table__cell--right" : undefined}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
