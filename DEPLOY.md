# Deployment quick reference

## Render (backend) - Web Service
- Root Directory: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/health`
- Env vars:
  - `PYTHON_VERSION` = `3.12.7`
  - `SAKSHYA_APP_ENV` = `production`
  - `SAKSHYA_MASTER_PASSWORD` = (new strong password)
  - `SAKSHYA_CORS_ORIGINS` = `https://YOUR-APP.vercel.app` (no trailing slash)
  - `SAKSHYA_STORAGE_DIR` = (persistent disk mount path, if you attach a disk)
- Seed demo data (needs Render Shell): `python scripts/seed.py`

## Vercel (frontend)
- Root Directory: `frontend`
- Env var: `VITE_API_BASE_URL` = `https://YOUR-SERVICE.onrender.com/api`
- `frontend/vercel.json` rewrites all paths to index.html (needed for client-side routes).
