# SAKSHYA frontend — React/Vite, built locally, served by nginx.
# Build context is the repository root (see docker-compose.yml).
# VITE_API_BASE_URL is baked at build time: default /api (nginx proxy path).
# For `npm run dev` outside Docker the frontend/src/api.js localhost default
# (http://127.0.0.1:8100/api) is used instead — see frontend/.env.example.
FROM node:22-alpine AS build
WORKDIR /app
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
COPY frontend/package*.json ./
# npm ci installs exactly what package-lock.json resolved — reproducible
# builds on the demo machine (needs internet once at build time only).
RUN npm ci --no-audit --no-fund
COPY frontend/. .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx","-g","daemon off;"]
