import React from 'react';

export function SectionHead({ n, title, sub }) {
  return (
    <div className="section-head">
      {n !== undefined && <span className="section-num">{n}</span>}
      <div>
        <h3>{title}</h3>
        {sub && <p>{sub}</p>}
      </div>
    </div>
  );
}

export function Panel({ title, action, children, className = '' }) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-head">
          <h3>{title}</h3>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export default Panel;
