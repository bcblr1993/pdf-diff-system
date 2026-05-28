#!/usr/bin/env bash
# 恢复：从 backup.sh 产出的目录恢复 DB + storage。
# 用法：bash scripts/restore.sh <备份目录>
#
# ⚠ 危险：会覆盖现有数据库与文件存储。
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "用法：bash scripts/restore.sh <备份目录>"
  exit 1
fi
SRC="$1"
[[ -d "${SRC}" ]] || { echo "❌ 目录不存在：${SRC}"; exit 1; }
[[ -f "${SRC}/db.sql.gz" ]] || { echo "❌ 缺少 db.sql.gz"; exit 1; }

_read_env() { grep -E "^${1}=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'; }
PG_USER="${POSTGRES_USER:-$(_read_env POSTGRES_USER)}"
PG_USER="${PG_USER:-pdfdiff}"
PG_DB="${POSTGRES_DB:-$(_read_env POSTGRES_DB)}"
PG_DB="${PG_DB:-pdfdiff}"

cat "${SRC}/meta.json" 2>/dev/null || echo "（无 meta.json）"
echo
read -p "⚠ 即将覆盖现有数据，输入 yes 继续：" CONFIRM
[[ "${CONFIRM}" == "yes" ]] || { echo "已取消"; exit 1; }

echo "停止 api / worker 避免脏写..."
docker compose stop api worker

# 1) 恢复数据库
echo "[1/2] 恢复 Postgres..."
PG_CONTAINER="$(docker compose ps -q postgres)"
gunzip -c "${SRC}/db.sql.gz" \
  | docker exec -i "${PG_CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" --quiet
echo "  ✓ 数据库恢复完成"

# 2) 恢复存储卷
if [[ -f "${SRC}/storage.tar.gz" ]]; then
  echo "[2/2] 恢复 storage 卷..."
  # 先停掉 api（已停），用临时容器挂卷展开
  docker run --rm \
    -v pdf-diff_storage:/data/storage \
    -v pdf-diff_cache:/data/cache \
    -v "$(cd "$(dirname "${SRC}")" && pwd)/$(basename "${SRC}")":/backup \
    alpine \
    sh -c 'rm -rf /data/storage/* /data/cache/* && tar xzf /backup/storage.tar.gz -C /data'
  echo "  ✓ 存储恢复完成"
fi

echo "重启服务..."
docker compose up -d api worker

echo "✅ 恢复完成"
