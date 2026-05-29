import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import {
  ArrowLeft, Layers, FileText, AlertTriangle, CheckCircle2, Clock, Download, RefreshCw,
} from "lucide-react";
import { getBatch, downloadBatchExport } from "@/api/endpoints";
import { errMsg } from "@/api/client";
import { fmtTime, STATUS_LABEL, REVIEW_STATUS_LABEL } from "@/lib/utils";

const BATCH_STATUS_LABEL = {
  pending: "等待中",
  running: "处理中",
  done: "已完成",
  partial: "部分失败",
  failed: "全部失败",
};
const BATCH_STATUS_BADGE = {
  pending: "badge-pending",
  running: "badge-running",
  done: "badge-done",
  partial: "badge-partial",
  failed: "badge-failed",
};

export default function BatchDetail() {
  const { id } = useParams<{ id: string }>();
  const bid = Number(id);
  const nav = useNavigate();
  const [exporting, setExporting] = useState(false);

  const { data: batch, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["batch", bid],
    queryFn: () => getBatch(bid),
    refetchInterval: (q) => {
      const d: any = q.state.data;
      return d && (d.status === "running" || d.status === "pending") ? 3000 : false;
    },
  });

  async function handleExport() {
    setExporting(true);
    try {
      const fname = await downloadBatchExport(bid);
      toast.success(`已导出 ${fname}`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setExporting(false);
    }
  }

  if (isLoading) return <div className="p-8 text-center text-fg-muted text-sm">加载中…</div>;
  if (!batch) {
    return (
      <div className="max-w-md mx-auto py-20 text-center anim-fade-in">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-critical-soft mb-4">
          <AlertTriangle className="w-5 h-5 text-critical" />
        </div>
        <h2 className="font-display text-xl mb-2 tracking-tightest">批量任务不存在</h2>
        <p className="text-sm text-fg-muted mb-5">可能已被删除或链接错误。</p>
        <button onClick={() => nav("/batches")} className="btn-secondary">
          <ArrowLeft className="w-3.5 h-3.5" /> 返回列表
        </button>
      </div>
    );
  }

  const progressPct = batch.total > 0
    ? Math.round(((batch.completed + batch.failed) / batch.total) * 100)
    : 0;

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* 顶部信息卡 */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => nav("/batches")} className="btn-secondary !py-1 !px-2">
          <ArrowLeft className="w-3.5 h-3.5" />
        </button>
        <Layers className="w-5 h-5 text-accent" />
        <div className="flex-1 min-w-0">
          <div className="font-medium text-lg truncate">{batch.title}</div>
          <div className="text-xs text-fg-muted">
            #{batch.id} · 创建于 {fmtTime(batch.created_at)}
            {batch.completed_at && <> · 完成于 {fmtTime(batch.completed_at)}</>}
          </div>
        </div>
        <span className={`badge ${BATCH_STATUS_BADGE[batch.status]}`}>
          {BATCH_STATUS_LABEL[batch.status]}
        </span>
        <button onClick={() => refetch()} className="btn-secondary !py-1.5" disabled={isFetching}>
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
        </button>
        <button onClick={handleExport} className="btn-secondary !py-1.5" disabled={exporting}>
          <Download className="w-3.5 h-3.5" /> {exporting ? "导出中..." : "导出汇总 Excel"}
        </button>
      </div>

      {/* 原件信息 */}
      <div className="card p-4 mb-4">
        <div className="text-[11px] tracking-wide uppercase text-fg-muted mb-1.5">原件</div>
        <div className="flex items-center gap-3">
          <FileText className="w-6 h-6 text-accent" />
          <div className="flex-1">
            <div className="font-medium text-sm">{batch.orig_file.original_name || "(未命名)"}</div>
            <div className="text-xs text-fg-muted tabular-nums">
              {batch.orig_file.page_count} 页 · SHA1 <code className="font-mono">{batch.orig_file.sha1.slice(0, 12)}…</code>
            </div>
          </div>
        </div>
      </div>

      {/* 进度条 */}
      <div className="card p-4 mb-4">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="font-medium">总进度</span>
          <span className="text-fg-muted tabular-nums">
            {batch.completed + batch.failed} / {batch.total} · {progressPct}%
          </span>
        </div>
        <div className="w-full h-2 bg-bg-tint rounded overflow-hidden">
          <div className="h-full bg-accent transition-all duration-500"
               style={{ width: `${progressPct}%` }} />
        </div>
        <div className="flex gap-4 mt-2 text-xs">
          <span className="inline-flex items-center gap-1 text-success-soft-fg">
            <CheckCircle2 className="w-3 h-3" /> 完成 {batch.completed}
          </span>
          {batch.failed > 0 && (
            <span className="inline-flex items-center gap-1 text-critical-soft-fg">
              <AlertTriangle className="w-3 h-3" /> 失败 {batch.failed}
            </span>
          )}
          <span className="inline-flex items-center gap-1 text-fg-muted">
            <Clock className="w-3 h-3" /> 处理中 {batch.total - batch.completed - batch.failed}
          </span>
        </div>
      </div>

      {/* 子任务卡片 */}
      <h2 className="text-lg font-medium mb-3">子对比任务（{batch.comparisons.length}）</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {batch.comparisons.map((c) => {
          const s = c.summary_json;
          return (
            <Link
              key={c.id}
              to={`/comparisons/${c.id}`}
              className="card card-hover p-3 group"
            >
              <div className="flex items-center gap-2 mb-2">
                <FileText className="w-4 h-4 text-fg-subtle shrink-0" />
                <div className="font-medium text-sm truncate flex-1 group-hover:text-accent transition-colors">
                  {c.title.replace(batch.title + " ", "")}
                </div>
                <StatusBadge status={c.status} />
              </div>
              {c.status === "done" && s ? (
                <div className="grid grid-cols-3 gap-1 text-xs">
                  <Stat label="真实" value={s.real} color="text-warning-soft-fg" />
                  <Stat label="★关键" value={s.critical} color={s.critical > 0 ? "text-critical font-bold" : "text-fg-subtle"} />
                  <Stat label="审核" value={REVIEW_STATUS_LABEL[c.review_status as keyof typeof REVIEW_STATUS_LABEL].replace("审核", "")} color="text-accent" />
                </div>
              ) : c.status === "failed" ? (
                <div className="text-xs text-critical">处理失败</div>
              ) : (
                <div className="flex items-center gap-2 text-xs text-fg-muted">
                  <Clock className="w-3 h-3" />
                  {c.progress_phase || c.status} · {c.progress_pct}%
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "badge-pending",
    running: "badge-running",
    done: "badge-done",
    failed: "badge-failed",
  };
  return (
    <span className={`badge ${map[status]}`}>
      {STATUS_LABEL[status as keyof typeof STATUS_LABEL]}
    </span>
  );
}

function Stat({ label, value, color }: { label: string; value: any; color: string }) {
  return (
    <div className="flex flex-col items-center bg-bg-subtle rounded py-1">
      <span className={`text-sm font-medium tabular-nums ${color}`}>{value ?? "—"}</span>
      <span className="text-[10px] text-fg-muted">{label}</span>
    </div>
  );
}
