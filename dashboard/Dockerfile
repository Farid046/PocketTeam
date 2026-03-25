FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm audit --audit-level=high
RUN npm run build

FROM node:20-alpine
WORKDIR /app
RUN apk add --no-cache wget \
    && addgroup -g 1001 -S dashboard && adduser -u 1001 -S dashboard -G dashboard
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json /app/package-lock.json ./
RUN npm ci --omit=dev && chown -R dashboard:dashboard /app
USER dashboard
EXPOSE 3847
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s \
  CMD wget -qO- http://localhost:3847/api/v1/health || exit 1
CMD ["node", "dist/server/index.js"]
