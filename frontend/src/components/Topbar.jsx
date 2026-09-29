import React, { useEffect, useRef, useState } from 'react';
import { Icon } from '../icons';
import { api } from '../api';
import { toggleSidebar, useAuthedRecipient, go, useAsync } from '../lib/app';

// Real alert state derived from GET /api/system/status (no mock data: an
// alert exists only when the backend actually reports a degraded subsystem).
function deriveAlerts(sys) {
  if (!sys) return [];
  const alerts = [];
  if (sys.backend !== 'OPERATIONAL') {
    alerts.push({ severity: 'danger', text: `Backend: ${sys.backend || 'unreachable'}` });
  }
  if (typeof sys.database !== 'string' || !sys.database.includes('CONNECTED')) {
    alerts.push({ severity: 'danger', text: `Database: ${sys.database || 'unavailable'}` });
  }
  if (typeof sys.ledger !== 'string' || !sys.ledger.includes('VERIFIED')) {
    alerts.push({ severity: 'danger', text: `Ledger: ${sys.ledger || 'unverified'}` });
  }
  if (sys.pqc_active === false) {
    alerts.push({ severity: 'warning', text: 'PQC NOT AVAILABLE — development fallback active' });
  }
  if (typeof sys.storage === 'string' && !sys.storage.includes('WRITABLE')) {
    alerts.push({ severity: 'warning', text: `Storage: ${sys.storage}` });
  }
  return alerts;
}

export function Topbar() {
  const recipient = useAuthedRecipient();
  const { data: sys, loading: sysLoading } = useAsync(() => api.system.status().catch(() => null), []);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  const alerts = deriveAlerts(sys);
  const count = alerts.length;

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open ]);

  return (
    <header className="topbar">
      <button className="hamb" aria-label="Toggle navigation" onClick={toggleSidebar} type="button">
        <Icon name="menu" size={18} />
      </button>

      <div className="global-search" onClick={() => go('documents')}>
        <Icon name="search" size={14} />
        <input
          type="text"
          placeholder="Search documents, recipients, events, hash, ID..."
          readOnly
        />
        <span className="search-shortcut">Ctrl + K</span>
      </div>

      <div className="topbar-right">
        <div className="notif-wrap" ref={wrapRef}>
          <button
            className={`topbar-bell${count > 0 ? ' has-alerts' : ''}`}
            type="button"
            aria-label={count > 0 ? `Notifications, ${count} unread` : 'Notifications, no unread alerts'}
            aria-expanded={open}
            aria-haspopup="true"
            title="System alerts"
            onClick={() => setOpen((o) => !o)}
          >
            <svg
              className="bell-glyph"
              width={19}
              height={19}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2.1}
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
            {count > 0 && <span className="bell-count">{count}</span>}
          </button>

          {open && (
            <div className="notif-dropdown" role="menu" aria-label="System alerts">
              <div className="notif-head">
                <b>System Alerts</b>
                {count > 0 && <span className="bell-count static">{count}</span>}
              </div>
              {sysLoading ? (
                <div className="notif-row muted">Checking system status…</div>
              ) : !sys ? (
                <div className="notif-row muted">Status unavailable — will retry on next visit.</div>
              ) : count === 0 ? (
                <div className="notif-row ok">
                  <Icon name="check" size={14} />
                  <span>All systems normal</span>
                </div>
              ) : (
                alerts.map((a) => (
                  <div className="notif-row" key={a.text} role="menuitem">
                    <span className={`notif-dot ${a.severity}`} />
                    <span>{a.text}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <div className="topbar-divider" />

        {recipient && (
          <div className="topbar-officer" onClick={() => go('settings')} title="View Officer Profile">
            <div className="topbar-avatar">
              <Icon name="shield" size={15} />
            </div>
            <div className="topbar-officer-meta">
              <b>{recipient.recipient_id}</b>
              <small>{recipient.role || 'Officer'}</small>
            </div>
            <Icon name="chevronDown" size={13} style={{ color: 'var(--text-muted)' }} />
          </div>
        )}
      </div>
    </header>
  );
}

export default Topbar;
