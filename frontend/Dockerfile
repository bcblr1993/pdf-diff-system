# 多阶段：build → nginx 静态服务
FROM node:20-alpine AS build

ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com

WORKDIR /app
COPY package*.json ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

# ── runtime ────────────────────────────────────
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
