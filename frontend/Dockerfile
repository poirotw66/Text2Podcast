# --- Build stage --------------------------------------------------------------
FROM node:22-slim AS build

WORKDIR /app

# Dependencies in their own layer, cached separately from source changes.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked into the built JS at build time (Vite inlines import.meta.env.* during
# the build, it cannot be changed at container start like a normal server env
# var). Override with `--build-arg VITE_API_URL=https://api.example.com` for
# anything other than local docker-compose use. See src/services/api.ts.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# --- Serve stage ----------------------------------------------------------
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
