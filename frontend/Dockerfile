FROM node:24-bookworm-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN test -n "$NEXT_PUBLIC_API_BASE_URL" && npm run build

FROM node:24-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
RUN groupadd --gid 10001 researchnest \
    && useradd --uid 10001 --gid researchnest --create-home researchnest
COPY --from=build --chown=researchnest:researchnest /app/package.json /app/package-lock.json ./
COPY --from=build --chown=researchnest:researchnest /app/node_modules ./node_modules
COPY --from=build --chown=researchnest:researchnest /app/.next ./.next
COPY --from=build --chown=researchnest:researchnest /app/next.config.mjs ./next.config.mjs
USER 10001:10001
EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0"]
