#!/usr/bin/env bash
# 巡检脚本：一次性输出所有关键指标，定时任务 / 报警可解析。
# 用法：bash scripts/health-check.sh
# 退出码：0 全部正常 / 1 有问题
set -euo pipefail

_read_env() { grep -E "^${1}=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'; }
POSTGRES_USER="${POSTGRES_USER:-$(_read_env POSTGRES_USER)}"
POSTGRES_DB="${POSTGRES_DB:-$(_read_env POSTGRES_DB)}"
API_URL="${API_URL:-http://localhost:8000}"
ISSUES=0

echo "═══ PDF Diff 系统巡检 $(date '+%F %T') ═══"
echo

# 1) 容器健康
echo "[容器状态]"
docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>&1
echo

# 2) API 健康
echo "[API 健康]"
HEALTH=$(curl -s --max-time 5 "${API_URL}/api/health" || echo "{}")
echo "  ${HEALTH}"
if ! echo "${HEALTH}" | grep -q '"status":"ok"'; then
  echo "  ❌ API 健康检查失败"
  ISSUES=$((ISSUES + 1))
fi
echo

# 3) DB 状态
echo "[数据库]"
PG_CONTAINER="$(docker compose ps -q postgres)"
if [[ -n "${PG_CONTAINER}" ]]; then
  USERS=$(docker exec "${PG_CONTAINER}" psql -U "${POSTGRES_USER:-pdfdiff}" -d "${POSTGRES_DB:-pdfdiff}" -tAc "SELECT count(*) FROM users" 2>/dev/null || echo "?")
  CMPS=$(docker exec "${PG_CONTAINER}" psql -U "${POSTGRES_USER:-pdfdiff}" -d "${POSTGRES_DB:-pdfdiff}" -tAc "SELECT count(*) FROM comparisons" 2>/dev/null || echo "?")
  STUCK=$(docker exec "${PG_CONTAINER}" psql -U "${POSTGRES_USER:-pdfdiff}" -d "${POSTGRES_DB:-pdfdiff}" -tAc "SELECT count(*) FROM comparisons WHERE status='running' AND started_at < NOW() - INTERVAL '10 minutes'" 2>/dev/null || echo "?")
  echo "  用户数: ${USERS} · 对比任务: ${CMPS} · 卡死任务(>10min): ${STUCK}"
  if [[ "${STUCK}" != "0" && "${STUCK}" != "?" ]]; then
    echo "  ⚠ 有 ${STUCK} 个 running 状态超过 10 分钟，可能 worker 卡死"
    ISSUES=$((ISSUES + 1))
  fi
fi
echo

# 4) Redis 队列
echo "[Redis 任务队列]"
REDIS_CONTAINER="$(docker compose ps -q redis)"
if [[ -n "${REDIS_CONTAINER}" ]]; then
  QLEN=$(docker exec "${REDIS_CONTAINER}" redis-cli LLEN "rq:queue:comparisons" 2>/dev/null || echo "0")
  echo "  待处理队列长度: ${QLEN}"
  if [[ "${QLEN}" -gt 10 ]]; then
    echo "  ⚠ 队列积压超过 10 个任务"
    ISSUES=$((ISSUES + 1))
  fi
fi
echo

# 5) 磁盘
echo "[存储磁盘]"
for vol in pdf-diff_storage pdf-diff_cache pdf-diff_pgdata; do
  SIZE=$(docker run --rm -v ${vol}:/data alpine du -sh /data 2>/dev/null | awk '{print $1}' || echo "?")
  printf "  %-22s %s\n" "${vol}:" "${SIZE}"
done
echo

if [[ ${ISSUES} -eq 0 ]]; then
  echo "✅ 全部检查通过"
  exit 0
else
  echo "❌ 发现 ${ISSUES} 个问题，请处理"
  exit 1
fi
