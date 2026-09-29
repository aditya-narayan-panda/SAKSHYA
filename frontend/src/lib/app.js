import { useEffect, useState } from 'react';
import { api } from '../api';

// Simple in-memory bridge between pages that a URL-based route (no client
// router state) can't otherwise pass data through. Lost on a full page
// reload, which is fine: these are "what just happened" hints, not the
// source of truth (the backend is).
export const session = {
  lastProtect: null,
  lastInvestigation: null,
  expiredNotice: null, // shown on /login after a 401 (error styling)
  infoNotice: null, // shown on /login after an explicit logout (neutral styling)
  redirectTo: null, // protected page the user was trying to reach before login
  // Recipient's signing private key for THIS browser session. Memory only: never put in
  // sessionStorage/localStorage, cleared on logout (see clearLocalAuth in api.js) and page reload.
  signingKey: null,
};

try {
  window.addEventListener('sakshya:session-expired', () => { session.signingKey = null; });
} catch (_) {}

// --- Auth: tiny pub-sub so any component can re-render when login state
// changes, without introducing a React context just for one value. ---
const authBus = { listeners: new Set() };
export function notifyAuthChanged() {
  authBus.listeners.forEach((l) => l());
}
export function useAuthedRecipient() {
  const [, tick] = useState(0);
  useEffect(() => {
    const l = () => tick((x) => x + 1);
    authBus.listeners.add(l);
    return () => authBus.listeners.delete(l);
  }, []);
  return api.auth.current();
}

// Current route segment: '' = public landing page, 'login' = login page,
// anything else = an officer page (see PAGES in main.jsx).
export function path() {
  return window.location.pathname.replace(/^\/+|\/+$/g, '');
}
// go('documents') -> /documents, go('') -> /. Pass { replace: true } for
// redirects so the Back button doesn't bounce the user through a dead route.
export function go(p, { replace = false } = {}) {
  const url = p ? `/${p}` : '/';
  window.history[replace ? 'replaceState' : 'pushState']({}, '', url);
  window.dispatchEvent(new PopStateEvent('popstate'));
  window.scrollTo({ top: 0, behavior: replace ? 'auto' : 'smooth' });
}
export function toggleSidebar() {
  document.body.classList.toggle('sidebar-open');
}
export function closeSidebar() {
  document.body.classList.remove('sidebar-open');
}

export function formatTs(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (e) {
    return String(iso);
  }
}

export function shortHash(h, head = 10, tail = 4) {
  if (!h) return '—';
  return h.length > head + tail ? `${h.slice(0, head)}...${h.slice(-tail)}` : h;
}

// --- Async data-fetching hook: every list/detail page uses this the same
// way, so loading/error/empty states behave consistently across the app. ---
export function useAsync(fn, deps) {
  const [state, setState] = useState({ loading: true, error: null, data: null });
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => alive && setState({ loading: false, error: null, data }))
      .catch((err) => alive && setState({ loading: false, error: err.message || 'Something went wrong', data: null }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  const reload = () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => setState({ loading: false, error: null, data }))
      .catch((err) => setState({ loading: false, error: err.message || 'Something went wrong', data: null }));
  };
  return { ...state, reload };
}
