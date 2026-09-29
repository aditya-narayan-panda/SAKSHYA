# SAKSHYA Frontend — React/Vite, local-only

Single-page React 19 + Vite 8 app. No UI framework swap, no redesign: the
existing SIH demo workflow (Dashboard → Documents → Recipients → Events →
Ledger → Leak Investigation → Reports → Settings) is preserved.

## Backend URL (one place)

`src/api.js` exports `API_BASE_URL`:

```js
import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8100/api'
```

For the offline demo the default is localhost — no cloud backend anywhere.
Inside Docker the build arg sets it to `/api` (same-origin nginx proxy).

## Routes

| Path | Access | Notes |
|------|--------|-------|
| `/` | Public | Landing page (`src/pages/Landing.jsx`). Shows live backend status from the public `/api/system/health` and `/api/system/crypto-status`. |
| `/login` | Public | Recipient/officer login (`POST /api/auth/login`). Signed-in users are sent to `/dashboard`. |
| `/dashboard`, `/documents`, `/protect`, `/recipients`, `/events`, `/ledger`, `/leak`, `/reports`, `/settings`, ... | Login required | Unauthenticated visits redirect to `/login` and return to the requested page after sign-in. |

Routing is still the project's own pathname switch in `src/main.jsx` (no router
dependency added). A session restored from `sessionStorage` is verified once
with `GET /api/auth/me` before any officer page renders. Logout calls
`POST /api/auth/logout`, clears the local token and returns to `/login`.

## Session expiry

Any `401` outside login clears local auth, redirects to the login screen and
shows **"Your session has expired. Please log in again."** — the user is
never stuck inside the dashboard with a dead token.

## Offline assets

No Google Fonts / CDN / external images / analytics. All assets
(`src/assets/`, styles) are bundled locally; the production build makes zero
external requests (verify in DevTools → Network with the network disabled
after `npm run build` + backend up).

Image credit: `src/assets/ins-vikrant-sea.jpg` (INS Vikrant at sea, dashboard
backdrop) is a Government Open Data License – India (GODL-India) photo via
Wikimedia Commons, stored locally — no runtime fetch.
`src/assets/sakshya-landing-hero.jpg` and `src/assets/sakshya-login-bg.jpg` are
the landing hero and login backdrops (referenced from `src/styles.css`), and
`src/assets/sakshya-logo.png` is the single brand mark, exposed through
`src/components/Logo.jsx` (`import { logoSrc }` or `<Logo />`). All are stored
locally.
The remaining `*-ref*` images in `src/assets/` are design-reference screenshots;
they are not imported anywhere and are never bundled into the build.

## Run (Windows PowerShell)

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api → 127.0.0.1:8100)
```

Bash/macOS/Linux:

```bash
cd frontend
npm install
npm run dev
```

Production build check:

```powershell
npm run build
npm run preview
```

## Security status UI

Settings → **Security Status (live)** shows real backend values from
`/api/system/crypto-status`: Authentication LOCAL, Database SQLITE,
Network OFFLINE/LOCAL, KEM ML-KEM-768, Signature ML-DSA-65,
Ledger LOCAL VERIFIED (or VERIFICATION FAILED), External Cloud NONE.
If the classical fallback is active it says `PQC NOT AVAILABLE` with a
`DEVELOPMENT FALLBACK ONLY` banner — never a fake PQC badge.
