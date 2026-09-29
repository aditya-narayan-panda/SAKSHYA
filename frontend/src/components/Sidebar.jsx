import React from 'react';
import { logoSrc as logo } from './Logo';
import { Icon } from '../icons';
import { api } from '../api';
import { path, go, closeSidebar, session, useAuthedRecipient, notifyAuthChanged } from '../lib/app';

const mainNavItems = [
  { name: 'Dashboard', route: 'dashboard', icon: 'dashboard' },
  { name: 'Documents', route: 'documents', icon: 'documents' },
  { name: 'Recipients', route: 'recipients', icon: 'users', roles: ['officer'] },
  { name: 'Investigations', route: 'leak', icon: 'investigate', roles: ['auditor'] },
  { name: 'Decryption Events', route: 'events', icon: 'events' },
  { name: 'Immutable Ledger', route: 'ledger', icon: 'ledger' },
  { name: 'Reports', route: 'reports', icon: 'reports', roles: ['auditor'] },
];

const systemNavItems = [
  { name: 'Settings', route: 'settings', icon: 'settings' },
];

export function Sidebar() {
  const p = path();
  const recipient = useAuthedRecipient();

  const handleLogout = async () => {
    await api.auth.logout();
    session.signingKey = null; // recipient signing key is memory-only and dies with the session
    session.redirectTo = null;
    session.infoNotice = 'You have been signed out.';
    closeSidebar();
    go('login', { replace: true });
    notifyAuthChanged();
  };

  const initial = (recipient?.name || 'O').trim().charAt(0).toUpperCase();

  return (
    <aside className="sidebar">
      <div className="brand" onClick={() => go('dashboard')} style={{ cursor: 'pointer' }}>
        <img src={logo} alt="SAKSHYA" />
        <div className="brand-text">
          <span className="brand-name">SAKSHYA</span>
          <span className="brand-sub">Digital Provenance &amp; Forensics</span>
        </div>
      </div>

      <nav className="nav">
        <div className="nav-group">
          {mainNavItems.filter((item) => !item.roles || item.roles.includes(recipient?.access_role || 'officer')).map((item) => (
            <button
              type="button"
              className={p === item.route ? 'nav-item active' : 'nav-item'}
              key={item.route}
              onClick={() => {
                go(item.route);
                closeSidebar();
              }}
            >
              <Icon name={item.icon} size={16} />
              <span>{item.name}</span>
            </button>
          ))}
        </div>

        <div className="nav-group" style={{ marginTop: 24 }}>
          <div className="nav-label">SYSTEM</div>
          {systemNavItems.map((item) => (
            <button
              type="button"
              className={p === item.route ? 'nav-item active' : 'nav-item'}
              key={item.route}
              onClick={() => {
                go(item.route);
                closeSidebar();
              }}
            >
              <Icon name={item.icon} size={16} />
              <span>{item.name}</span>
            </button>
          ))}
        </div>
      </nav>

      <div className="sidebar-footer">
        {recipient && (
          <div className="sidebar-officer-card">
            <div className="officer-info-left">
              <div className="officer-avatar-sm">
                <Icon name="shield" size={14} />
              </div>
              <div>
                <b style={{ color: 'var(--navy-dark)', fontSize: 12.5, display: 'block' }}>
                  {recipient.name || 'Officer-01'}
                </b>
                <small style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                  {recipient.recipient_id}
                </small>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 2 }}>
                  <span className="pulse-dot" style={{ width: 5, height: 5 }} />
                  <span style={{ fontSize: 10.5, color: 'var(--green)', fontWeight: 600 }}>Active</span>
                </div>
              </div>
            </div>
            <button className="ghost-btn small" onClick={handleLogout} type="button" title="Sign out of workstation">
              <Icon name="logout" size={13} />
              Logout
            </button>
          </div>
        )}

        <div className="sidebar-system-status">
          <span style={{ color: 'var(--text-muted)' }}>SAKSHYA v2.0.0</span>
          <span style={{ color: 'var(--text-secondary)' }}>
            <Icon name="wifiOff" size={12} style={{ color: 'var(--cyan)' }} />
            Offline Mode
          </span>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
