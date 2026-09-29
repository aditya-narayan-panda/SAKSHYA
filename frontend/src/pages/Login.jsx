import React, { useEffect, useState } from 'react';
import { logoSrc as logo } from '../components/Logo';
import { Icon } from '../icons';
import { api } from '../api';
import { AppLink } from '../components/AppLink';
import { session, notifyAuthChanged, go } from '../lib/app';

export function LoginScreen() {
  const [recipientId, setRecipientId] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState(null);
  const [notice] = useState(session.expiredNotice || null);
  const [info] = useState(session.infoNotice || null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    session.expiredNotice = null;
    session.infoNotice = null;
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!recipientId.trim() || !password) return;
    setBusy(true);
    setError(null);
    try {
      await api.auth.login(recipientId.trim(), password);
      notifyAuthChanged();
    } catch (err) {
      setError(
        err instanceof TypeError
          ? 'Cannot reach the SAKSHYA backend. Verify service is operational on port 8100.'
          : err.message || 'Authentication failed. Please verify credentials.'
      );
    } finally {
      setBusy(false);
    }
  };

  const fillDemo = () => {
    setRecipientId('REC-OFFICER01');
    setPassword('sakshya-officer01');
  };

  return (
    <div className="login-screen">
      <AppLink to="" className="login-back-link">
        <Icon name="arrowRight" size={14} style={{ transform: 'rotate(180deg)' }} />
        Return to Public Portal
      </AppLink>

      <div className="login-container">
        {/* LEFT: branding */}
        <div className="login-panel">
          <div className="login-brand-stack">
            <img src={logo} alt="SAKSHYA Official Insignia" className="login-brand-emblem" />
            <b className="login-brand-title">SAKSHYA</b>
            <small className="login-brand-sub">
              CRYPTOGRAPHIC DOCUMENT ATTRIBUTION
              <br />
              &amp; PROVENANCE SYSTEM
            </small>
            <div className="login-brand-rule" aria-hidden="true">
              <span />
              <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 1l1.9 8.1L22 12l-8.1 2.9L12 23l-1.9-8.1L2 12l8.1-1.9L12 1z" />
              </svg>
              <span />
            </div>
          </div>

          <h1 className="login-tagline">
            Secure Documents. Traceable Access.
            <br />
            Accountable Use.
          </h1>
        </div>

        {/* RIGHT: login card */}
        <div className="login-form-side">
          <form className="login-card" onSubmit={handleSubmit}>
            <div className="login-card-head">
              <h2>Officer Login</h2>
              <p>
                Access SAKSHYA using your authorized{' '}
                <br />
                credentials to manage secure documents.
              </p>
            </div>

            {info && (
              <div className="state-box" style={{ marginBottom: 16 }}>
                <Icon name="info" size={14} style={{ color: 'var(--blue)' }} />
                <span>{info}</span>
              </div>
            )}

            {notice && (
              <div className="state-box error" style={{ marginBottom: 16 }}>
                <Icon name="alert" size={14} />
                <span>{notice}</span>
              </div>
            )}

            <label className="login-field">
              Recipient ID
              <div className="input-with-icon">
                <span className="left-icon">
                  <Icon name="user" size={18} />
                </span>
                <input
                  value={recipientId}
                  onChange={(e) => setRecipientId(e.target.value)}
                  placeholder="Enter your Recipient ID"
                  autoCapitalize="characters"
                  autoComplete="username"
                  spellCheck={false}
                  autoFocus
                />
              </div>
            </label>

            <label className="login-field">
              Password
              <div className="input-with-icon">
                <span className="left-icon">
                  <Icon name="lock" size={18} />
                </span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="toggle-eye"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  <Icon name="eye" size={20} />
                </button>
              </div>
            </label>

            <div className="form-options-row">
              <label>
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
                Remember workstation
              </label>
              <span
                className="login-recovery"
                onClick={() => alert('Contact your unit Cryptographic Administrator to request PIN / key recovery.')}
              >
                Key Recovery?
              </span>
            </div>

            {error && (
              <div className="state-box error" role="alert" style={{ marginBottom: 16 }}>
                <Icon name="alert" size={14} />
                <span>{error}</span>
              </div>
            )}

            <button className="primary wide lg login-submit" disabled={busy} type="submit">
              {busy ? (
                'Authenticating Officer…'
              ) : (
                <>
                  Authenticate
                  <Icon name="arrowRight" size={20} strokeWidth={2} />
                </>
              )}
            </button>

            <div className="or-divider">OR</div>

            <div className="login-security-badge">
              <Icon name="shieldCheck" size={28} strokeWidth={2} />
              <span>
                Protected with post-quantum cryptography
                <br />
                Air-gapped environment
              </span>
            </div>

            <button type="button" className="demo-link" onClick={fillDemo}>
              Use demo credentials (Officer 01)
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default LoginScreen;
