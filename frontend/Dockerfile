FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_BASE_PATH=/fruelage
ARG NEXT_PUBLIC_API_URL=/fruelage
ARG NEXT_PUBLIC_WS_URL=wss://riegel-troisdorf.de/fruelage/ws
ARG INTERNAL_API_URL=http://backend:8000
ENV NEXT_BASE_PATH=$NEXT_BASE_PATH
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV INTERNAL_API_URL=$INTERNAL_API_URL
RUN mkdir -p public && npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
