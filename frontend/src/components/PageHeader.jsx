import React from 'react';

// Replaces the old marketing-style "Hero" band with a restrained editorial
// header: label, title, one-line description, and an optional row of small
// uppercase status facts (never a giant colorful badge).
export function PageHeader({ eyebrow, title, description, status, action }) {
  return (
    <div className="page-header">
      <div className="page-header-text">
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <div className="page-header-row">
          <h1>{title}</h1>
          {action && <div className="page-header-action">{action}</div>}
        </div>
        {description && <p>{description}</p>}
        {status && status.length > 0 && (
          <div className="status-line">
            {status.map((s, i) => (
              <React.Fragment key={s.label}>
                {i > 0 && <span className="status-sep" aria-hidden="true">/</span>}
                <span className={`status-line-item ${s.tone || ''}`}>
                  {s.dot && <span className="status-line-dot" />}
                  {s.label}
                </span>
              </React.Fragment>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default PageHeader;
