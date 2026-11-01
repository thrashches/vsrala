FROM node:22-alpine AS build

WORKDIR /app
COPY app/package.json app/package-lock.json ./
RUN npm ci
COPY app/ ./
RUN npm run build

FROM alpine:3.20
RUN apk add --no-cache bash
COPY --from=build /app/dist /opt/spa
COPY landing /opt/landing
COPY docker-publish.sh /docker-publish.sh
RUN chmod +x /docker-publish.sh
CMD ["/docker-publish.sh"]
