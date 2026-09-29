import React from 'react';

// Maps domain statuses to standardized tones
export function Badge({ children, type }) {
  let tone = type;
  if (!tone && typeof children === 'string') {
    const s = children.trim().toUpperCase();
    if (['SUCCESS', 'GOOD', 'PROTECTED', 'VERIFIED', 'ONLINE', 'ACTIVE', 'COMMITTED', 'IDENTIFIED', 'GENERATED'].includes(s)) {
      tone = 'success';
    } else if (['WARNING', 'WARN', 'PENDING', 'REVIEW', 'IN REVIEW'].includes(s)) {
      tone = 'warning';
    } else if (['DANGER', 'BAD', 'FAILED', 'INVALID', 'REVOKED', 'UNATTRIBUTED'].includes(s)) {
      tone = 'danger';
    } else if (['INVESTIGATION', 'PQC'].includes(s)) {
      tone = 'purple';
    } else if (['INFO', 'DECRYPTION', 'RECIPIENT', 'POST-QUANTUM'].includes(s)) {
      tone = 'info';
    } else {
      tone = 'neutral';
    }
  }

  return <span className={`badge badge-${tone || 'neutral'}`}>{children}</span>;
}

export default Badge;
