import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { toast } from "sonner";
import {
  Trash2, ChevronLeft, ChevronRight, RefreshCw, Plus, Search,
  FileText, CheckCircle2, Clock, AlertCircle, Loader2,
} from "lucide-react";
import { listComparisons, deleteComparison } from "@/api/endpoints";
import { fmtAgo, REVIEW_STATUS_LABEL } from "@/lib/utils";
import type { ComparisonStatus, ReviewStatus, ComparisonBrief } from "@/types";
import { errMsg } from "@/api/client";
import { EmptyState } from "@/components/EmptyState";
import { ComparisonCardSkeleton } from "@/components/Skeleton";

export default function ComparisonList() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<ComparisonStatus | "">("");
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus | "">("");
  const [mineOnly, setMineOnly] = useState(false);
  const [search, setSearch] = useState("");

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["comparisons", page, status, reviewStatus, mineOnly],
    queryFn: () =>
      listComparisons({
        page,
        page_size: 20,
        ...(status ? { status } : {}),
        ...(reviewStatus ? { review_status: reviewStatus } : {}),
        ...(mineOnly ? { mine_only: true } : {}),
      }),
    refetchInterval: (q) => {
      const items = (q.state.data as any)?.items as any[] | undefined;
      return items?.some((x) => x.status === "running" || x.status === "pending") ? 3000 : false;
    },
  });

  const delMut = useMutation({
    mutationFn: deleteComparison,
    onSuccess: () => {
      toast.success("已删除");
      qc.invalidateQueries({ queryKey: ["comparisons"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const items = (data?.items || []).filter((it) =>
    search ? it.title.toLowerCase().includes(search.toLowerCase()) : true
  );
  const total = data?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="max-w-[88rem] mx-auto px-5 py-8">
      {/* 页头 */}
      <div className="flex items-end justify-between mb-7">
        <div>
          <div className="text-[11px] tracking-[0.2em] uppercase text-fg-muted mb-1.5">Workspace</div>
          <h1 className="font-display text-[2rem] leading-none tracking-tightest text-fg"
              style={{ fontVariationSettings: '"opsz" 36, "SOFT" 40' }}>
            对比任务
          </h1>
          <p className="text-[13px] text-fg-muted mt-2 tabular-nums">
            共 <strong className="text-fg font-medium">{total}</strong> 个 ·
            处理中 <strong className="text-fg font-medium">
              {(data?.items || []).filter((x) => x.status === "running" || x.status === "pending").length}
            </strong>
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()} className="btn-secondary" disabled={isFetching}>
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} /> 刷新
          </button>
          <Link to="/new" className="btn-primary">
            <Plus className="w-3.5 h-3.5" /> 新建对比
          </Link>
        </div>
      </div>

      {/* 过滤栏 */}
      <div className="card p-2 mb-4 flex gap-2 items-center text-sm flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-muted pointer-events-none" />
          <input
            placeholder="搜索任务标题…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input !pl-8 !h-8 !text-[13px] border-transparent !bg-transparent"
          />
        </div>
        <FilterPill label="状态" value={status} onChange={(v) => { setStatus(v as any); setPage(1); }}
          options={[
            ["", "全部"],
            ["pending", "等待中"],
            ["running", "处理中"],
            ["done", "已完成"],
            ["failed", "失败"],
          ]}
        />
        <FilterPill label="审核" value={reviewStatus} onChange={(v) => { setReviewStatus(v as any); setPage(1); }}
          options={[
            ["", "全部"],
            ["not_started", "未审核"],
            ["in_review", "审核中"],
            ["completed", "审核完成"],
          ]}
        />
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
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <ComparisonCardSkeleton key={i} />)}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title={search ? "没有匹配的任务" : "还没有任何对比任务"}
          description={search ? "试试别的关键字" : "上传一份原件和扫描件，开始第一次审核。"}
          action={!search && (
            <Link to="/new" className="btn-primary">
              <Plus className="w-3.5 h-3.5" /> 新建对比
            </Link>
          )}
        />
      ) : (
        <div className="space-y-2 stagger">
          {items.map((it) => (
            <CompCard key={it.id} item={it} onOpen={() => nav(`/comparisons/${it.id}`)}
              onDelete={() => { if (confirm("确认删除该任务？")) delMut.mutate(it.id); }} />
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6 text-[13px]">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="btn-ghost !h-8 disabled:opacity-30">
            <ChevronLeft className="w-3.5 h-3.5" /> 上一页
          </button>
          <span className="text-fg-muted tabular-nums px-2">第 {page} 页 · 共 {totalPages} 页</span>
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="btn-ghost !h-8 disabled:opacity-30">
            下一页 <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

/** 卡片：单行 horizontal layout，hover 强调 */
function CompCard({ item, onOpen, onDelete }: {
  item: ComparisonBrief; onOpen: () => void; onDelete: () => void;
}) {
  const s = item.summary_json;
  return (
    <article
      onClick={onOpen}
      className="card card-hover px-4 py-3 flex items-center gap-4 group"
    >
      {/* 编号 + 类型图标 */}
      <div className="w-12 text-right shrink-0">
        <div className="text-[10px] tracking-[0.15em] uppercase text-fg-subtle leading-none">No.</div>
        <div className="font-mono text-[14px] text-fg-muted leading-tight mt-0.5">{String(item.id).padStart(3, "0")}</div>
      </div>

      <FileText className="w-4 h-4 text-fg-subtle shrink-0" />

      {/* 标题 + 元信息 */}
      <div className="flex-1 min-w-0">
        <h3 className="text-[14px] font-medium truncate group-hover:text-accent transition-colors">
          {item.title || "(无标题)"}
        </h3>
        <div className="flex items-center gap-3 mt-1 text-[11.5px] text-fg-muted tabular-nums">
          <span>{fmtAgo(item.created_at)}</span>
          <span className="text-fg-subtle">·</span>
          <span>{REVIEW_STATUS_LABEL[item.review_status as keyof typeof REVIEW_STATUS_LABEL]}</span>
        </div>
      </div>

      {/* 状态 */}
      <StatusChip status={item.status} pct={item.progress_pct} />

      {/* 差异统计 */}
      {s ? (
        <div className="flex items-center gap-3 px-3 border-l border-border tabular-nums">
          <Stat n={s.real} label="真实" />
          <Stat n={s.critical} label="关键" critical />
          <Stat n={s.insert + s.handwritten} label="新增" />
          <Stat n={s.delete} label="删除" />
        </div>
      ) : (
        <div className="w-32 text-center text-[12px] text-fg-subtle italic">
          {item.status === "running" ? `处理中 ${item.progress_pct}%` : "等待开始"}
        </div>
      )}

      {/* 操作 */}
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="btn-ghost !h-8 !w-8 !p-0 opacity-0 group-hover:opacity-100 hover:!text-critical"
        title="删除任务"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </article>
  );
}

function Stat({ n, label, critical }: { n: number; label: string; critical?: boolean }) {
  return (
    <div className="text-center min-w-[34px]">
      <div className={`text-[14px] font-medium leading-none tabular-nums ${
        critical && n > 0 ? "text-critical" : n > 0 ? "text-fg" : "text-fg-subtle"
      }`}>
        {critical && n > 0 && <span className="star mr-0.5">★</span>}{n}
      </div>
      <div className="text-[10px] text-fg-subtle mt-1 tracking-wide">{label}</div>
    </div>
  );
}

function StatusChip({ status, pct }: { status: string; pct: number }) {
  const config: Record<string, { icon: React.ReactNode; label: string; cls: string }> = {
    pending: { icon: <Clock className="w-3 h-3" />, label: "等待", cls: "badge-pending" },
    running: { icon: <Loader2 className="w-3 h-3 animate-spin" />, label: `${pct}%`, cls: "badge-running" },
    done: { icon: <CheckCircle2 className="w-3 h-3" />, label: "完成", cls: "badge-done" },
    failed: { icon: <AlertCircle className="w-3 h-3" />, label: "失败", cls: "badge-failed" },
  };
  const c = config[status] || config.pending;
  return (
    <span className={`badge ${c.cls} !text-[10.5px] tracking-wide`}>
      {c.icon} {c.label}
    </span>
  );
}

function FilterPill({
  label, value, onChange, options,
}: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <div className="inline-flex items-center gap-1.5 px-2.5 h-8 rounded-md hover:bg-bg-subtle transition-colors">
      <span className="text-[11px] text-fg-muted">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-transparent text-[13px] outline-none cursor-pointer font-medium"
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>{l}</option>
        ))}
      </select>
    </div>
  );
}
