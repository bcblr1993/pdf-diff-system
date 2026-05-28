#!/usr/bin/env bash
# 备份：导出 Postgres + 打包 storage 卷
# 用法：bash scripts/backup.sh [备份目录]
#   默认目录：./backups/<时间戳>/
#
# 产出：
#   db.sql.gz       Postgres 全库 dump（含数据）
#   storage.tar.gz  PDF/Word 原始文件 + OCR 缓存
#   meta.json       备份元信息（时间、容器版本、文件大小）
set -euo pipefail

BACKUP_ROOT="${1:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${BACKUP_ROOT}/${STAMP}"

_read_env() { grep -E "^${1}=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'; }
PG_USER="${POSTGRES_USER:-$(_read_env POSTGRES_USER)}"
PG_USER="${PG_USER:-pdfdiff}"
PG_DB="${POSTGRES_DB:-$(_read_env POSTGRES_DB)}"
PG_DB="${PG_DB:-pdfdiff}"

PG_CONTAINER="$(docker compose ps -q postgres 2>/dev/null || true)"
if [[ -z "${PG_CONTAINER}" ]]; then
  echo "❌ postgres 容器未运行，请先 docker compose up -d"
  exit 1
fi

mkdir -p "${DEST}"

echo "📦 备份目标：${DEST}"
echo "─────────────────────────────────────"

# 1) 数据库
echo "[1/3] 导出 Postgres..."
docker exec "${PG_CONTAINER}" pg_dump -U "${PG_USER}" -d "${PG_DB}" --clean --if-exists \
  | gzip > "${DEST}/db.sql.gz"
DB_SIZE=$(du -h "${DEST}/db.sql.gz" | awk '{print $1}')
echo "  ✓ db.sql.gz (${DB_SIZE})"

# 2) 文件存储 + OCR 缓存（从 named volume 直接打包）
echo "[2/3] 打包 storage 卷..."
PROJECT_NAME="$(basename "$(pwd)")"  # docker compose 默认 project = 当前目录名
docker run --rm \
  -v "${PROJECT_NAME}_storage:/data/storage:ro" \
  -v "${PROJECT_NAME}_cache:/data/cache:ro" \
  -v "$(cd "${DEST}" && pwd):/backup" \
  alpine \
  sh -c 'tar czf /backup/storage.tar.gz -C /data storage cache'
STO_SIZE=$(du -h "${DEST}/storage.tar.gz" 2>/dev/null | awk '{print $1}' || echo "N/A")
echo "  ✓ storage.tar.gz (${STO_SIZE})"

# 3) 元信息
echo "[3/3] 生成 meta.json..."
GIT_REV="$(git -C "$(dirname "$0")/.." rev-parse --short HEAD 2>/dev/null || echo unknown)"
cat > "${DEST}/meta.json" <<EOF
{
  "backup_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "git_revision": "${GIT_REV}",
  "postgres_user": "${PG_USER}",
  "postgres_db": "${PG_DB}",
  "db_size": "${DB_SIZE}",
  "storage_size": "${STO_SIZE}"
}
EOF
echo "  ✓ meta.json"

echo
echo "✅ 备份完成：${DEST}"
echo "   恢复命令：bash scripts/restore.sh ${DEST}"
