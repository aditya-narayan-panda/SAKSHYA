import React from 'react';
import { Icon } from '../icons';

// steps: [{ label, state, detail }] — state: 'done' | 'active' | 'failed' | 'pending'
export function EvidenceChain({ steps }) {
  return (
    <div className="evidence-chain">
      {steps.map((s, i) => (
        <div className={`evidence-step ${s.state}`} key={s.label}>
          <div className="evidence-step-marker">
            {s.state === 'done' && <Icon name="check" size={12} />}
            {s.state === 'failed' && <Icon name="x" size={12} />}
            {s.state === 'active' && (
              <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} />
            )}
            {s.state === 'pending' && (
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--text-dim)' }} />
            )}
          </div>
          <div className="evidence-step-body">
            <b>{s.label}</b>
            {s.detail && <span>{s.detail}</span>}
          </div>
          {i < steps.length - 1 && <div className="evidence-step-connector" />}
        </div>
      ))}
    </div>
  );
}

export default EvidenceChain;
