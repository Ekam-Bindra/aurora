# AURORA web image. Build context is the repo root.
FROM node:20-alpine

WORKDIR /app
RUN corepack enable

# Copy workspace manifests first for better layer caching.
COPY package.json pnpm-workspace.yaml turbo.json ./
COPY packages/config/package.json ./packages/config/package.json
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --filter "@aurora/web..."

# Copy sources and build.
COPY packages/config ./packages/config
COPY apps/web ./apps/web
RUN pnpm --filter @aurora/web build

EXPOSE 3000
CMD ["pnpm", "--filter", "@aurora/web", "start"]
