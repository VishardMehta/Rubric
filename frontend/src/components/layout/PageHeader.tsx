import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import "./layout.css";

interface PageHeaderProps {
  title: string;
  /** One line only (design-system.md section 13). `Jobs / Senior Python Developer`. */
  breadcrumb?: { label: string; to: string };
  subtitle?: ReactNode;
  /** Exactly one primary action per screen region. */
  actions?: ReactNode;
}

export function PageHeader({ title, breadcrumb, subtitle, actions }: PageHeaderProps) {
  return (
    <header className="rb-page-header">
      {breadcrumb && (
        <nav className="rb-page-header__breadcrumb" aria-label="Breadcrumb">
          <Link to={breadcrumb.to}>{breadcrumb.label}</Link>
          <span aria-hidden="true">/</span>
          <span>{title}</span>
        </nav>
      )}
      <div className="rb-page-header__row">
        <div className="rb-page-header__titles">
          <h1 className="text-title-1" style={{ margin: 0 }}>
            {title}
          </h1>
          {subtitle && <p className="text-caption" style={{ margin: 0 }}>{subtitle}</p>}
        </div>
        {actions && <div className="rb-page-header__actions">{actions}</div>}
      </div>
    </header>
  );
}
