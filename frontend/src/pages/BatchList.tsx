import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Layers, Trash2, ChevronLeft, ChevronRight, RefreshCw, Plus,
  CheckCircle2, AlertCircle, Clock, Loader2,
} from "lucide-react";
import { listBatches, deleteBatch } from "@/api/endpoints";
import { fmtAgo } from "@/lib/utils";
import type { BatchStatus } from "@/types";
import { errMsg } from "@/api/client";
import { EmptyState } from "@/components/EmptyState";

const STATUS_LABEL: Record<BatchStatus, string> = {
  pending: "等待中", running: "处理中", done: "已完成",
  partial: "部分失败", failed: "全部失败",
};

export default function BatchList() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<BatchStatus | "">("");
  const [mineOnly, setMineOnly] = useState(false);

  const { data, isFetching, refetch } = useQuery({
    queryKey: ["batches", page, status, mineOnly],
    queryFn: () => listBatches({
      page, page_size: 20,
      ...(status ? { status } : {}),
      ...(mineOnly ? { mine_only: true } : {}),
    }),
    refetchInterval: (q) => {
      const items = (q.state.data as any)?.items as any[] | undefined;
      return items?.some((x) => x.status === "running" || x.status === "pending") ? 3000 : false;
    },
  });

  const delMut = useMutation({
    mutationFn: deleteBatch,
    onSuccess: () => { toast.success("已删除"); qc.invalidateQueries({ queryKey: ["batches"] }); },
    onError: (e) => toast.error(errMsg(e)),
  });

  const items = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="max-w-[88rem] mx-auto px-5 py-8">
      {/* 页头 */}
      <div className="flex items-end justify-between mb-7">
        <div>
          <div className="text-[11px] tracking-[0.2em] uppercase text-fg-muted mb-1.5">Workspace</div>
          <h1 className="font-display text-[2rem] leading-none tracking-tightest text-fg inline-flex items-center gap-3"
              style={{ fontVariationSettings: '"opsz" 36, "SOFT" 40' }}>
            <Layers className="w-7 h-7 text-accent" /> 批量对比
          </h1>
          <p className="text-[13px] text-fg-muted mt-2 tabular-nums">
            共 <strong className="text-fg font-medium">{total}</strong> 个批量任务
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()} className="btn-secondary" disabled={isFetching}>
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} /> 刷新
          </button>
          <Link to="/new" className="btn-primary">
            <Plus className="w-3.5 h-3.5" /> 新建批量
          </Link>
        </div>
      </div>

      {/* 过滤栏 */}
      <div className="card p-2 mb-4 flex gap-2 items-center text-sm flex-wrap">
        <div className="inline-flex items-center gap-1.5 px-2.5 h-8">
          <span className="text-[11px] text-fg-muted">状态</span>
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value as BatchStatus | ""); setPage(1); }}
            className="bg-transparent text-[13px] outline-none cursor-pointer font-medium"
          >
            <option value="">全部</option>
            <option value="pending">等待中</option>
            <option value="running">处理中</option>
            <option value="done">已完成</option>
            <option value="partial">部分失败</option>
            <option value="failed">全部失败</option>
          </select>
        </div>
        <label className="inline-flex items-center gap-1.5 px-2 cursor-pointer text-[13px]">
          <input
            type="checkbox"
            checked={mineOnly}
            onChange={(e) => { setMineOnly(e.target.checked); setPage(1); }}
            className="accent-fg w-3.5 h-3.5"
          />
          <span className="text-fg-muted">仅我创建</span>
        </label>
      </div>

      {/* 列表 */}
      {items.length === 0 && !isFetching ? (
        <EmptyState
          title="还没有批量任务"
          description="批量对比适合：1 份原件模板对应 N 份对方回签版。"
          action={<Link to="/new" className="btn-primary"><Plus className="w-3.5 h-3.5" /> 新建批量</Link>}
        />
      ) : (
        <div className="space-y-2 stagger">
          {items.map((it) => (
            <BatchCard
              key={it.id}
              item={it}
              onOpen={() => nav(`/batches/${it.id}`)}
              onDelete={() => { if (confirm("确认删除批量任务（含所有子对比）？")) delMut.mutate(it.id); }}
            />
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6 text-[13px]">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-ghost !h-8 disabled:opacity-30"
          >
            <ChevronLeft className="w-3.5 h-3.5" /> 上一页
          </button>
          <span className="text-fg-muted tabular-nums px-2">第 {page} 页 · 共 {totalPages} 页</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="btn-ghost !h-8 disabled:opacity-30"
          >
            下一页 <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

function BatchCard({ item, onOpen, onDelete }: {
  item: any; onOpen: () => void; onDelete: () => void;
}) {
  const pct = item.total > 0 ? Math.round(((item.completed + item.failed) / item.total) * 100) : 0;
  return (
    <article onClick={onOpen} className="card card-hover px-4 py-3 flex items-center gap-4 group">
      <div className="w-12 text-right shrink-0">
        <div className="text-[10px] tracking-[0.15em] uppercase text-fg-subtle leading-none">No.</div>
        <div className="font-mono text-[14px] text-fg-muted leading-tight mt-0.5">
          {String(item.id).padStart(3, "0")}
        </div>
      </div>

      <Layers className="w-4 h-4 text-fg-subtle shrink-0" />

      {/* 标题 + 元信息 */}
      <div className="flex-1 min-w-0">
        <h3 className="text-[14px] font-medium truncate group-hover:text-accent transition-colors">
          {item.title || "(无标题)"}
        </h3>
        <div className="flex items-center gap-3 mt-1 text-[11.5px] text-fg-muted tabular-nums">
          <span>{fmtAgo(item.created_at)}</span>
          <span className="text-fg-subtle">·</span>
          <span>{item.total} 个子对比</span>
        </div>
      </div>

      {/* 状态 chip */}
      <StatusChip status={item.status} />

      {/* 进度条 */}
      <div className="flex items-center gap-2.5 px-3 border-l border-border min-w-[200px]">
        <div className="flex-1">
          <div className="flex items-center justify-between text-[11px] text-fg-muted tabular-nums mb-1">
            <span>{item.completed + item.failed} / {item.total}</span>
            <span className="font-medium text-fg">{pct}%</span>
          </div>
          <div className="w-full h-1.5 bg-bg-tint rounded overflow-hidden">
            <div
              className="h-full bg-accent transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          {item.failed > 0 && (
            <div className="mt-1 text-[10.5px] text-critical-soft-fg">
              <AlertCircle className="w-2.5 h-2.5 inline mr-0.5" />
              {item.failed} 失败
            </div>
          )}
        </div>
      </div>

      {/* 删除 */}
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="btn-ghost !h-8 !w-8 !p-0 opacity-0 group-hover:opacity-100 hover:!text-critical"
        title="删除批量任务"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </article>
  );
}

function StatusChip({ status }: { status: BatchStatus }) {
  const config: Record<BatchStatus, { icon: React.ReactNode; cls: string }> = {
    pending: { icon: <Clock className="w-3 h-3" />, cls: "badge-pending" },
    running: { icon: <Loader2 className="w-3 h-3 animate-spin" />, cls: "badge-running" },
    done: { icon: <CheckCircle2 className="w-3 h-3" />, cls: "badge-done" },
    partial: { icon: <AlertCircle className="w-3 h-3" />, cls: "badge-partial" },
    failed: { icon: <AlertCircle className="w-3 h-3" />, cls: "badge-failed" },
  };
  const c = config[status];
  return (
    <span className={`badge ${c.cls} !text-[10.5px] tracking-wide`}>
      {c.icon} {STATUS_LABEL[status]}
    </span>
  );
}
