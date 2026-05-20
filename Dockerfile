# syntax=docker/dockerfile:1

# ---------- 前端构建 ----------
FROM node:22.22.0-alpine AS frontend-build

WORKDIR /build/game-hub

COPY game-hub/package.json game-hub/package-lock.json* ./

RUN npm ci

COPY game-hub/ ./

# 生产构建使用同源相对路径，由 nginx 将 /api/ 反代到后端
ENV VITE_API_BASE=

RUN npm run build

# ---------- 运行镜像 ----------
FROM python:3.8.11-slim-bullseye

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/data /var/log/supervisor /run/nginx

WORKDIR /app

COPY game-hub-end/requirements.txt ./game-hub-end/requirements.txt

RUN pip install --no-cache-dir -r game-hub-end/requirements.txt

COPY game-hub-end/ ./game-hub-end/

COPY --from=frontend-build /build/game-hub/dist /usr/share/nginx/html

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/supervisord.conf /etc/supervisor/supervisord.conf
COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && rm -f /etc/nginx/sites-enabled/default

ENV DATABASE_URL=sqlite:////app/data/game_hub.db

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
