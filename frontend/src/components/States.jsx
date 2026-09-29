import React from 'react';
import { Icon } from '../icons';

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="state-box">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBox({ message, onRetry }) {
  return (
    <div className="state-box error">
      <Icon name="alert" size={15} />
      <span style={{ flex: 1 }}>{message}</span>
      {onRetry && (
        <button className="ghost-btn small" onClick={onRetry} type="button" style={{ marginLeft: 8 }}>
          <Icon name="refresh" size={12} />
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyBox({ message }) {
  return (
    <div className="state-box empty">
      <Icon name="info" size={15} />
      <span>{message}</span>
    </div>
  );
}
