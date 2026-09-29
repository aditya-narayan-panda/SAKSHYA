import React, { useEffect, useState, useSyncExternalStore } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import { api } from './api';
import { path, go, session, notifyAuthChanged, useAuthedRecipient } from './lib/app';

import { Landing } from './pages/Landing';
import { LoginScreen } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Documents } from './pages/Documents';
import { Protect } from './pages/Protect';
import { ProtectSuccess } from './pages/ProtectSuccess';
import { Recipients } from './pages/Recipients';
import { AddRecipient } from './pages/AddRecipient';
import { Events } from './pages/Events';
import { Ledger } from './pages/Ledger';
import { Leak } from './pages/Leak';
import { Reports } from './pages/Reports';
import { Settings } from './pages/Settings';

// Route map.
//   /          public landing page          (no login)
//   /login     recipient/officer login      (no login; bounces to /dashboard if already signed in)
//   /<page>    everything below             (login required, via the existing bearer-token session)
const PAGES = {
  dashboard: Dashboard,
  documents: Documents,
  protect: Protect,
  'protect-success': ProtectSuccess,
  recipients: Recipients,
  'add-recipient': AddRecipient,
  events: Events,
  ledger: Ledger,
  leak: Leak,
  reports: Reports,
  settings: Settings,
};
const isProtectedRoute = (p) => Object.prototype.hasOwnProperty.call(PAGES, p);

// Restore any saved session synchronously, before the first render, so a page
// reload doesn't flash the login screen or lose the logged-in state.
api.auth.restore();

// Route subscription for useSyncExternalStore. Unlike a popstate listener
// added in useEffect, this re-checks the location right after subscribing, so
// a redirect fired by a child's effect (which runs BEFORE this component's
// own effects) can never be missed.
const subscribeRoute = (cb) => {
  window.addEventListener('popstate', cb);
  return () => window.removeEventListener('popstate', cb);
};
const getRoute = () => window.location.pathname;

// Navigates in an effect (never during render) and renders nothing.
function Redirect({ to, before, after }) {
  useEffect(() => {
    if (before) before();
    go(to, { replace: true });
    if (after) after();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [to]);
  return null;
}

function SessionCheck() {
  return (
    <div className="session-check" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-0)' }}>
      <div className="state-box">
        <span className="spinner" aria-hidden="true" />
        <span>Verifying secure officer session…</span>
      </div>
    </div>
  );
}

function App() {
  useSyncExternalStore(subscribeRoute, getRoute);
  // A session restored from sessionStorage is verified once against
  // GET /api/auth/me before any officer page renders, so a token the backend
  // no longer knows about never shows a half-loaded dashboard.
  const [checking, setChecking] = useState(() => !!api.auth.current());

  // A 401 anywhere (expired/invalidated session) clears auth. On an officer
  // page the user is sent to /login with an explanation and returns to the
  // same page after signing in again; on the public pages it is silent.
  useEffect(() => {
    const onExpired = (ev) => {
      api.auth.clearLocal();
      const here = path();
      if (isProtectedRoute(here)) {
        session.expiredNotice = (ev && ev.detail && ev.detail.message) || 'Your session has expired. Please log in again.';
        session.redirectTo = here;
        go('login', { replace: true });
      }
      notifyAuthChanged();
    };
    window.addEventListener('sakshya:session-expired', onExpired);
    return () => window.removeEventListener('sakshya:session-expired', onExpired);
  }, []);

  useEffect(() => {
    if (!api.auth.current()) {
      setChecking(false);
      return undefined;
    }
    let alive = true;
    api.auth
      .me()
      .catch(() => { /* 401 is handled by the session-expired listener; other errors surface on the pages themselves */ })
      .finally(() => alive && setChecking(false));
    return () => { alive = false; };
  }, []);

  const recipient = useAuthedRecipient();
  const p = path();

  // Public landing page — never waits on, or requires, authentication.
  if (p === '') return <Landing />;

  if (checking) return <SessionCheck />;

  if (p === 'login') {
    if (!recipient) return <LoginScreen />;
    const target = isProtectedRoute(session.redirectTo) ? session.redirectTo : 'dashboard';
    return <Redirect to={target} after={() => { session.redirectTo = null; }} />;
  }

  if (!isProtectedRoute(p)) {
    return <Redirect to={recipient ? 'dashboard' : 'login'} />;
  }

  if (!recipient) {
    return <Redirect to="login" before={() => { session.redirectTo = p; }} />;
  }

  const Page = PAGES[p];
  return <Page />;
}

createRoot(document.getElementById('root')).render(<App />);
