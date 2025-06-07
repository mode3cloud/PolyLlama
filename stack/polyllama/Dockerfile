# ======= Build stages for Next.js app
FROM node:20-slim AS node-base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0

RUN npm install -g corepack@latest
RUN corepack enable
RUN corepack install -g pnpm@latest

# Development dependencies
FROM node-base AS dev-deps
WORKDIR /app
COPY ./ui/package.json ./ui/pnpm-lock.yaml ./ui/.npmrc ./
RUN pnpm install --frozen-lockfile

# Production build
FROM node-base AS prod-deps
WORKDIR /app
COPY ./ui/package.json ./ui/pnpm-lock.yaml ./ui/.npmrc ./
RUN pnpm install --frozen-lockfile

FROM prod-deps AS build
WORKDIR /app
COPY ./ui ./
RUN pnpm run build
RUN pnpm install --prod --frozen-lockfile

# ======= Nginx with OpenResty
FROM openresty/openresty:alpine AS nginx-base

# Install additional packages needed
RUN apk add --no-cache curl jq nodejs npm supervisor

# Install lua-resty-http module
RUN apk add --no-cache git \
    && cd /tmp \
    && git clone https://github.com/ledgetech/lua-resty-http.git \
    && cd lua-resty-http \
    && cp -r lib/resty/* /usr/local/openresty/lualib/resty/ \
    && rm -rf /tmp/lua-resty-http

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Create directories
RUN mkdir -p /usr/share/nginx/html/ui /app /var/log/supervisor

# ======= Development stage
FROM nginx-base AS development

# Install pnpm in the container
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN npm install -g corepack@latest && corepack enable && corepack install -g pnpm@latest

# Copy node modules from dev-deps stage
COPY --from=dev-deps /app/node_modules /app/node_modules

# Copy nginx configs
COPY proxy_params.conf /etc/nginx/proxy_params.conf
COPY model_router.lua /etc/nginx/model_router.lua

# Copy supervisord config for development
COPY supervisord-dev.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /app
ENV NODE_ENV=development
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 11434 3000

# Start supervisor which will run both nginx and pnpm dev
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

# ======= Production stage
FROM nginx-base AS production

# Install pnpm in the production container
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN npm install -g corepack@latest && corepack enable && corepack install -g pnpm@latest

# Copy production build files
COPY --from=build /app/node_modules /app/node_modules
COPY --from=build /app/.next /app/.next
COPY --from=build /app/package.json /app/pnpm-lock.yaml /app/next.config.js /app/
# Create empty public directory if it doesn't exist
RUN mkdir -p /app/public

# Copy nginx configs
COPY proxy_params.conf /etc/nginx/proxy_params.conf
COPY model_router.lua /etc/nginx/model_router.lua

# Copy supervisord config for production
COPY supervisord-prod.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 11434

# Start supervisor which will run both nginx and node
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]