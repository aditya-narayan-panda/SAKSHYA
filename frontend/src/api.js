// Centralized API configuration — the ONLY place a backend URL lives.
// Default targets the local offline backend (127.0.0.1:8100); override with
// VITE_API_BASE_URL for other setups. Inside Docker the build arg sets this
// to "/api" so the same-origin nginx proxy is used (see docker/nginx.conf).
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8100/api';
const BASE = API_BASE_URL;

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// --- Auth: bearer token kept in memory + sessionStorage (survives a reload of
// this tab, not a new tab/device — appropriate for a shared demo console). ---
let authToken = null;
let currentRecipient = null;

function restoreAuth() {
  try {
    const t = sessionStorage.getItem('sakshya_token');
    const r = sessionStorage.getItem('sakshya_recipient');
    if (t && r) {
      authToken = t;
      currentRecipient = JSON.parse(r);
    }
  } catch (_) { /* sessionStorage unavailable — just start logged out */ }
  return currentRecipient;
}

function authHeaders() {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

function clearLocalAuth() {
  authToken = null;
  currentRecipient = null;
  try {
    sessionStorage.removeItem('sakshya_token');
    sessionStorage.removeItem('sakshya_recipient');
  } catch (_) {}
}

// A 401 outside the login call itself means the session is gone (expired,
// revoked, or the backend restarted with the old in-memory store). Clear
// local auth state and tell the app to send the user back to /login with a
// clear message instead of leaving them stuck inside the dashboard.
function handleUnauthorized(path) {
  if (path.startsWith('/auth/login')) return;
  clearLocalAuth();
  try {
    window.dispatchEvent(
      new CustomEvent('sakshya:session-expired', {
        detail: { message: 'Your session has expired. Please log in again.' },
      }),
    );
  } catch (_) {}
}

// FastAPI returns `detail` as a string OR an object like {code, message} (e.g. UNSUPPORTED_WATERMARK_TYPE).
function detailText(body, fallback) {
  const d = body && body.detail;
  if (!d) return fallback;
  if (typeof d === 'string') return d;
  if (d.message) return d.code ? `${d.code}: ${d.message}` : d.message;
  try { return JSON.stringify(d); } catch (_) { return fallback; }
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}), ...authHeaders() };
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized(path);
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = detailText(body, detail);
    } catch (_) {
      /* non-JSON error body, keep statusText */
    }
    throw new ApiError(detail, res.status);
  }
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) return res.json();
  return res.blob();
}

function get(path) {
  return request(path);
}

function post(path, body) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
}

function del(path) {
  return request(path, { method: 'DELETE' });
}

async function postForm(path, form) {
  const res = await fetch(`${BASE}${path}`, { method: 'POST', body: form, headers: authHeaders() });
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized(path);
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = detailText(body, detail);
    } catch (_) {}
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

// Authenticated binary download — a plain <a href> can't carry an
// Authorization header, so this fetches the bytes and hands back a blob the
// caller turns into an object URL (see main.jsx's handleViewAndLog).
async function getBlob(path) {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized(path);
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = detailText(body, detail);
    } catch (_) {}
    throw new ApiError(detail, res.status);
  }
  return res.blob();
}

export const api = {
  ApiError,

  auth: {
    async login(recipientId, password) {
      const res = await post('/auth/login', { recipient_id: recipientId, password });
      authToken = res.token;
      currentRecipient = { recipient_id: res.recipient_id, name: res.name, organization: res.organization, role: res.role, access_role: res.access_role || 'officer' };
      try {
        sessionStorage.setItem('sakshya_token', authToken);
        sessionStorage.setItem('sakshya_recipient', JSON.stringify(currentRecipient));
      } catch (_) {}
      return currentRecipient;
    },
    async logout() {
      try { await post('/auth/logout'); } catch (_) { /* token may already be expired — log out locally anyway */ }
      clearLocalAuth();
    },
    // Validates the stored bearer token against the backend (GET /api/auth/me).
    // A 401 here triggers the normal session-expired flow.
    me: () => get('/auth/me'),
    clearLocal: clearLocalAuth,
    restore: restoreAuth,
    current: () => currentRecipient,
  },

  dashboard: {
    get: () => get('/dashboard'),
  },

  documents: {
    list: (params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return get(`/documents${qs ? `?${qs}` : ''}`);
    },
    get: (documentId) => get(`/documents/${documentId}`),
    remove: (documentId) => del(`/documents/${documentId}`),
  },

  recipients: {
    list: () => get('/recipients'),
    get: (recipientId) => get(`/recipients/${recipientId}`),
    create: (payload) => post('/recipients', payload),
    revoke: (recipientId) => post(`/recipients/${recipientId}/revoke`),
  },

  protection: {
    protect: (file, recipientIds) => {
      const form = new FormData();
      form.append('document', file);
      form.append('recipient_ids', JSON.stringify(recipientIds));
      return postForm('/protect', form);
    },
  },

  decryption: {
    // recipient_id no longer travels in the request body — the server infers
    // it from the logged-in session (see backend/app/api/decryption.py).
    // The signing PRIVATE key never lives on the server: the recipient supplies it per session
    // (file upload / paste, held in memory only) and it is sent over this request alone.
    decrypt: (documentId, signingPrivateKey, applyVisible = false) =>
      post(`/decrypt/${documentId}`, { signing_private_key_b64: signingPrivateKey || '', apply_visible: !!applyVisible }),
    listEvents: () => get('/events'),
    downloadBlob: (eventId) => getBlob(`/events/${eventId}/download`),
    recordRender: (eventId, signingPrivateKey) => post(`/events/${eventId}/render`, { signing_private_key_b64: signingPrivateKey || '' }),
    listRenders: (eventId) => get(`/events/${eventId}/renders`),
  },

  ledger: {
    blocks: () => get('/ledger/blocks'),
    verify: () => get('/ledger/verify'),
  },

  investigations: {
    list: () => get('/investigations'),
    get: (investigationId) => get(`/investigations/${investigationId}`),
    create: (file) => {
      const form = new FormData();
      form.append('file', file);
      return postForm('/investigations', form);
    },
  },

  reports: {
    list: () => get('/reports'),
    create: (investigationId) => post(`/reports?investigation_id=${encodeURIComponent(investigationId)}`),
    // Authenticated download via fetch + blob (a plain <a href> cannot carry
    // the Authorization header, and the endpoint stays login-protected).
    downloadBlob: (reportId, format = 'pdf') => getBlob(`/reports/${reportId}/download?format=${format}`),
  },

  system: {
    settings: () => get('/system/settings'),
    health: () => get('/system/health'),
    cryptoStatus: () => get('/system/crypto-status'),
    status: () => get('/system/status'),
  },
};
