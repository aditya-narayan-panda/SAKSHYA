import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev-server only: proxies /api to the locally-running FastAPI backend so
// `npm run dev` works standalone without Docker/Nginx. The Docker deployment
// uses its own Nginx proxy (docker/nginx.conf) instead of this file.
// Backend default port is 8100 (see backend/main.py).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
    },
  },
});
