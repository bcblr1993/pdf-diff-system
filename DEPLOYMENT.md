# 内网部署与运维手册

面向运维：在企业内网 Linux 服务器一键启动 + 日常维护。

---

## 1. 服务器要求

| 资源 | 最低 | 推荐 |
|---|---|---|
| CPU | 4 核 | 8 核 |
| 内存 | 8 GB | 16 GB |
| 磁盘 | 50 GB | 200 GB SSD |
| OS | Linux x86_64（任意主流发行版）| Debian 12 / Ubuntu 22.04 / CentOS 8 |
| 软件 | Docker 24+ + Docker Compose v2 | 同左 |

OCR 阶段 RAM 峰值约 1-1.5 GB/页，建议 worker 限制 4 GB。

---

## 2. 首次安装

```bash
# 1. clone 仓库
git clone https://github.com/bcblr1993/pdf-diff-system.git /opt/pdf-diff
cd /opt/pdf-diff

# 2. 准备环境变量
cp .env.example .env
vim .env   # 必改：SECRET_KEY、POSTGRES_PASSWORD、INITIAL_ADMIN_PASSWORD

# 3. 一键起服务（生产配置）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. 健康检查
bash scripts/health-check.sh
```

服务起来后：

| 入口 | URL |
|---|---|
| Web 前端 | `http://<服务器IP>:8080` |
| Swagger | `http://<服务器IP>:8080/docs`（开发模式开放，生产建议反代关闭）|

首次登录用 `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD`（默认 `admin/admin123`），**进系统第一时间改密码**。

---

## 3. 必改的环境变量

`.env` 关键项：

```bash
# === 安全 ===
SECRET_KEY=<openssl rand -hex 32 的输出>      # JWT 签名密钥，必须随机
ALLOW_REGISTRATION=false                       # 关闭自助注册（默认就是 false）

# === 数据库 ===
POSTGRES_USER=pdfdiff
POSTGRES_PASSWORD=<强密码>                     # 切勿用默认 pdfdiff
POSTGRES_DB=pdfdiff
POSTGRES_HOST=postgres                         # 容器内固定为 postgres，不改
POSTGRES_PORT=5432

# === 初始管理员（仅首次启动生效）===
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=<强密码>
INITIAL_ADMIN_NAME=管理员

# === 性能（按服务器 CPU 核数调）===
API_WORKERS=4                                  # 建议 CPU 核数 / 2

# === CORS（如果前端独立部署在别的域名）===
CORS_ORIGINS=https://pdf-diff.company.local
```

---

## 4. 反向代理（HTTPS）

生产环境强烈建议套 Nginx + Let's Encrypt 终结 HTTPS。示例：

```nginx
# /etc/nginx/sites-available/pdf-diff
upstream pdf_diff_backend {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name pdf-diff.company.local;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name pdf-diff.company.local;

    ssl_certificate     /etc/letsencrypt/live/pdf-diff.company.local/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pdf-diff.company.local/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    client_max_body_size 200m;

    location / {
        proxy_pass http://pdf_diff_backend;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 升级
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 长任务（OCR）超时
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

申请证书：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d pdf-diff.company.local
```

---

## 5. 日常运维

### 5.1 巡检（建议每日 cron）

```bash
# 添加到 /etc/cron.daily/pdf-diff-check
#!/bin/bash
cd /opt/pdf-diff
bash scripts/health-check.sh >> /var/log/pdf-diff-check.log 2>&1 || \
  mail -s "PDF Diff 巡检异常" ops@company.com < /var/log/pdf-diff-check.log
```

### 5.2 备份（建议每日凌晨）

```bash
# /etc/cron.d/pdf-diff-backup
0 2 * * * root cd /opt/pdf-diff && bash scripts/backup.sh /backup/pdf-diff/
# 保留最近 30 天
0 3 * * * root find /backup/pdf-diff/ -maxdepth 1 -mtime +30 -type d -exec rm -rf {} \;
```

备份内容：
- `db.sql.gz`：完整 Postgres dump（用户/任务/差异/审核记录）
- `storage.tar.gz`：PDF 原文件 + Word 原文件 + OCR 缓存
- `meta.json`：备份元信息（时间/git revision）

### 5.3 恢复

```bash
cd /opt/pdf-diff
bash scripts/restore.sh /backup/pdf-diff/20260528-020000
# 会提示输入 yes 确认，会停 api/worker → 恢复 → 重启
```

### 5.4 看日志

```bash
# 实时跟踪
docker compose logs -f api worker

# 最近 200 行
docker compose logs --tail 200 api

# 指定时间段
docker compose logs --since 1h api worker | grep -i error

# 日志已设 10MB × 10 文件轮转
ls -lh $(docker inspect --format='{{.LogPath}}' pdf-diff-api-1)
```

### 5.5 升级

```bash
cd /opt/pdf-diff
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
bash scripts/health-check.sh
```

迁移自动跑（api 启动时 alembic upgrade head），但**升级前先备份**：

```bash
bash scripts/backup.sh /backup/pdf-diff/before-upgrade-$(date +%Y%m%d)
```

### 5.6 重启单服务

```bash
docker compose restart worker      # 仅 worker
docker compose restart api         # 仅 api
docker compose restart             # 全部
```

---

## 6. 性能调优

### 6.1 OCR 并发

默认只有 1 个 worker 进程。多核服务器可起多个：

```yaml
# docker-compose.prod.yml 加
  worker:
    deploy:
      replicas: 3   # 起 3 个 worker 实例并行处理
```

每个 worker 单独消耗 ~1.5 GB RAM 高峰，按服务器内存算。

### 6.2 OCR 缓存预热

同一份文件多次处理（多人对比同一份原件）只在首次 OCR，缓存命中后秒级。**不要清 `cache/` 卷**。

### 6.3 数据库索引

已建索引（`comparisons.status` / `diffs.comparison_id` / `diffs.severity`）通常够用。任务数 > 10 万时考虑加分区：

```sql
-- 按月分区 diffs 表
CREATE TABLE diffs_2026_05 PARTITION OF diffs FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

---

## 7. 故障排查

### Q1：上传文件后任务一直 pending

→ Worker 死了，看日志：
```bash
docker compose logs worker | tail -50
docker compose restart worker
```

如果 worker 反复重启，可能是 `cache/` 目录权限：
```bash
docker exec pdf-diff-worker-1 ls -la /data/cache
# 应是 root:root 可写
```

### Q2：任务 status=failed，error_message 是 "ImportError"

→ 镜像内某依赖缺失。**重新 build**：
```bash
docker compose build --no-cache api worker
docker compose up -d --force-recreate api worker
```

### Q3：PDF Viewer 显示 "Failed to fetch worker"

→ 前端 nginx MIME 配置错误。检查：
```bash
curl -I http://localhost:8080/pdf.worker.min.mjs | grep content-type
# 应是 application/javascript
```

### Q4：上传 50MB 以上 PDF 报 413

→ 修改 nginx 反代 `client_max_body_size`：
```nginx
http {
    client_max_body_size 200m;
}
```
前端容器内 nginx 已设 `100m`，反代也要同步。

### Q5：数据库连接耗尽

→ 默认 SQLAlchemy 连接池 5+10。高并发可加：
```python
# backend/app/db/base.py
engine = create_engine(url, pool_size=20, max_overflow=20)
```

### Q6：磁盘满了

→ 检查并清理：
```bash
docker system df               # 看 Docker 总体占用
docker system prune -a         # 删未使用 image
du -sh /var/lib/docker/volumes/pdf-diff_*
```

OCR 缓存可手动清旧：
```bash
docker exec pdf-diff-worker-1 find /data/cache -mtime +90 -delete
```

---

## 8. 安全清单

部署后**必做**：

- [ ] `SECRET_KEY` 换成 32 字节随机串
- [ ] `INITIAL_ADMIN_PASSWORD` 登录后立即在前端改
- [ ] `POSTGRES_PASSWORD` 不是默认 `pdfdiff`
- [ ] HTTPS 已配置，HTTP 跳转到 HTTPS
- [ ] 防火墙只放行 80/443，不暴露 5432/6379/8000
- [ ] 备份脚本已加 cron，备份目录在独立分区/网盘
- [ ] 日志已挂载到独立目录，避免根分区被打爆
- [ ] Swagger 在生产建议加 nginx auth 或 IP 白名单（默认开放）
- [ ] API Key 不要随便给第三方，吊销渠道清晰

---

## 9. 监控接入

简单方案：用 `health-check.sh` + cron + 邮件告警（见 5.1）。

完整方案接入 Prometheus：

```yaml
# docker-compose.prod.yml 加
  api:
    environment:
      ENABLE_METRICS: "true"   # 暴露 /metrics 端点（需扩展实现）
```

或者用 Loki + Grafana 聚合 docker JSON 日志。

---

## 10. 联系与支持

- 算法/算法准确性问题：见仓库 `backend/pipeline/diff.py` 注释
- 系统使用：见 `README.md`
- 开发约定：见 `CLAUDE.md`
- API 文档：`http://<服务器>:8080/docs`
- GitHub：https://github.com/bcblr1993/pdf-diff-system
