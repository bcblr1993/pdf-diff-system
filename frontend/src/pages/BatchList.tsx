import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Layers, Trash2, ChevronLeft, ChevronRight, RefreshCw, Plus } from "lucide-react";
import { listBatches, deleteBatch } from "@/api/endpoints";
import { fmtAgo } from "@/lib/utils";
import type { BatchStatus } from "@/types";
import { errMsg } from "@/api/client";

const STATUS_LABEL: Record<BatchStatus, string> = {
  pending: "等待中",
  running: "处理中",
  done: "已完成",
  partial: "部分失败",
  failed: "全部失败",
};
const STATUS_COLOR: Record<BatchStatus, string> = {
  pending: "bg-gray-100 text-gray-700",
  running: "bg-blue-100 text-blue-800",
  done: "bg-green-100 text-green-800",
  partial: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
};

export default function BatchList() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<BatchStatus | "">("");
  const [mineOnly, setMineOnly] = useState(false);

  const { data, isFetching, refetch } = useQuery({
    queryKey: ["batches", page, status, mineOnly],
    queryFn: () =>
      listBatches({
        page,
        page_size: 20,
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
    onSuccess: () => {
      toast.success("已删除");
      qc.invalidateQueries({ queryKey: ["batches"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const items = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold inline-flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-600" /> 批量对比任务
          </h1>
          <p className="text-sm text-gray-500 mt-1">共 {total} 个批量任务</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()} className="btn-secondary" disabled={isFetching}>
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} /> 刷新
          </button>
          <Link to="/new" className="btn-primary"><Plus className="w-3.5 h-3.5" /> 新建批量</Link>
        </div>
      </div>

      <div className="card p-3 mb-4 flex gap-3 flex-wrap items-center text-sm">
        <select className="input !w-auto" value={status}
                onChange={(e) => { setStatus(e.target.value as BatchStatus | ""); setPage(1); }}>
          <option value="">全部状态</option>
          <option value="pending">等待中</option>
          <option value="running">处理中</option>
          <option value="done">已完成</option>
          <option value="partial">部分失败</option>
          <option value="failed">全部失败</option>
        </select>
        <label className="inline-flex items-center gap-1.5">
          <input type="checkbox" checked={mineOnly}
                 onChange={(e) => { setMineOnly(e.target.checked); setPage(1); }} />
          <span>仅看我创建的</span>
        </label>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
            <tr>
              <th className="px-4 py-2 text-left">#</th>
              <th className="px-4 py-2 text-left">标题</th>
              <th className="px-4 py-2 text-left">状态</th>
              <th className="px-4 py-2 text-left">进度</th>
              <th className="px-4 py-2 text-left">创建</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !isFetching && (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-gray-400">
                  暂无批量任务，<Link to="/new" className="text-blue-600 hover:underline">创建第一个</Link>
                </td>
              </tr>
            )}
            {items.map((it) => (
              <tr key={it.id} className="border-t hover:bg-gray-50 cursor-pointer"
                  onClick={() => nav(`/batches/${it.id}`)}>
                <td className="px-4 py-3 text-gray-500">#{it.id}</td>
                <td className="px-4 py-3 font-medium text-gray-900">{it.title || "(无标题)"}</td>
                <td className="px-4 py-3">
                  <span className={`badge ${STATUS_COLOR[it.status]}`}>{STATUS_LABEL[it.status]}</span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-1.5 bg-gray-100 rounded overflow-hidden">
                      <div className="h-1.5 bg-blue-600"
                           style={{ width: `${it.total ? ((it.completed + it.failed) / it.total) * 100 : 0}%` }} />
                    </div>
                    <span className="text-xs text-gray-600">
                      {it.completed + it.failed} / {it.total}
                      {it.failed > 0 && <span className="text-red-600 ml-1">（{it.failed} 失败）</span>}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">{fmtAgo(it.created_at)}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={(e) => { e.stopPropagation(); if (confirm("确认删除批量任务（含所有子对比）？")) delMut.mutate(it.id); }}
                    className="btn-danger !py-1 !px-2"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 mt-4 text-sm">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                  className="btn-secondary disabled:opacity-40">
            <ChevronLeft className="w-3.5 h-3.5" /> 上一页
          </button>
          <span className="text-gray-500">{page} / {totalPages}</span>
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                  className="btn-secondary disabled:opacity-40">
            下一页 <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
