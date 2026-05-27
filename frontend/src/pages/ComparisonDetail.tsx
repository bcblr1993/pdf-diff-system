import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, ArrowLeft, FileText, AlertTriangle } from "lucide-react";
import {
  getComparison, listDiffs, completeReview, pdfUrl,
} from "@/api/endpoints";
import { errMsg } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import PdfDocument from "@/components/PdfDocument";
import DiffSidebar from "@/components/DiffSidebar";
import ProgressPanel from "@/components/ProgressPanel";
import { fmtTime, REVIEW_STATUS_LABEL } from "@/lib/utils";

export default function ComparisonDetail() {
  const { id } = useParams<{ id: string }>();
  const cid = Number(id);
  const nav = useNavigate();
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  const [activeDiffId, setActiveDiffId] = useState<number | null>(null);
  const [includeNoise, setIncludeNoise] = useState(false);
  const [scrollAnchor, setScrollAnchor] = useState<{ side: string; page: number; ts: number } | null>(null);

  const cmpQ = useQuery({
    queryKey: ["comparison", cid],
    queryFn: () => getComparison(cid),
    refetchInterval: (q) => {
      const d: any = q.state.data;
      return d && (d.status === "running" || d.status === "pending") ? 3000 : false;
    },
  });

  const diffsQ = useQuery({
    queryKey: ["diffs", cid, includeNoise],
    queryFn: () => listDiffs(cid, { page_size: 1000, include_noise: includeNoise }),
    enabled: cmpQ.data?.status === "done",
  });

  const completeMut = useMutation({
    mutationFn: () => completeReview(cid),
    onSuccess: () => {
      toast.success("审核已完成");
      qc.invalidateQueries({ queryKey: ["comparison", cid] });
      qc.invalidateQueries({ queryKey: ["diffs"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const cmp = cmpQ.data;
  const diffs = useMemo(() => diffsQ.data?.items || [], [diffsQ.data]);

  // 当 active 改变时，记录滚动锚点
  useEffect(() => {
    if (!activeDiffId) return;
    const d = diffs.find((x) => x.id === activeDiffId);
    if (!d) return;
    // 让两侧 PDF 都跳到该差异所在页
    const origPage = d.orig_page >= 0 ? d.orig_page : d.scan_page;
    const scanPage = d.scan_page >= 0 ? d.scan_page : d.orig_page;
    setScrollAnchor({ side: "both", page: origPage, ts: Date.now() });
    // 拆成两步推不同 side 锚点
    setTimeout(() => {
      setScrollAnchor({ side: "orig", page: origPage, ts: Date.now() });
      setTimeout(() => setScrollAnchor({ side: "scan", page: scanPage, ts: Date.now() + 1 }), 50);
    }, 0);
  }, [activeDiffId]);

  if (cmpQ.isLoading) return <div className="p-8 text-center text-gray-500">加载中...</div>;
  if (cmpQ.error || !cmp) {
    return (
      <div className="p-8 text-center">
        <div className="text-red-600 mb-2">加载失败</div>
        <button onClick={() => nav("/")} className="btn-secondary"><ArrowLeft className="w-3.5 h-3.5" /> 返回列表</button>
      </div>
    );
  }

  // 仍在处理中
  if (cmp.status === "pending" || cmp.status === "running") {
    return (
      <div>
        <Toolbar cmp={cmp} onBack={() => nav("/")} />
        <ProgressPanel
          comparisonId={cid}
          initialPhase={cmp.progress_phase}
          initialPct={cmp.progress_pct}
          onDone={() => qc.invalidateQueries({ queryKey: ["comparison", cid] })}
        />
      </div>
    );
  }

  if (cmp.status === "failed") {
    return (
      <div>
        <Toolbar cmp={cmp} onBack={() => nav("/")} />
        <div className="card max-w-2xl mx-auto mt-12 p-6">
          <div className="flex items-center gap-2 text-red-600 mb-3">
            <AlertTriangle className="w-5 h-5" />
            <span className="font-semibold">任务处理失败</span>
          </div>
          <pre className="text-xs text-gray-700 bg-gray-50 p-3 rounded whitespace-pre-wrap">{cmp.error_message}</pre>
        </div>
      </div>
    );
  }

  const origPdfUrl = `/api/comparisons/${cid}/orig.pdf`;
  const scanPdfUrl = `/api/comparisons/${cid}/scan.pdf`;

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 56px)" }}>
      <Toolbar cmp={cmp} onBack={() => nav("/")} onComplete={() => {
        if (confirm("确认结束审核？未审核的条目将被自动归为 ignored")) completeMut.mutate();
      }} />
      <div className="flex-1 grid grid-cols-[1fr_400px] overflow-hidden">
        <div className="grid grid-cols-2 overflow-hidden border-r border-gray-200">
          <div className="overflow-y-auto bg-gray-100">
            <PdfDocument
              url={origPdfUrl}
              side="orig"
              diffs={diffs}
              activeDiffId={activeDiffId}
              onSelectDiff={setActiveDiffId}
              pageScrollAnchor={scrollAnchor}
            />
          </div>
          <div className="overflow-y-auto bg-gray-100 border-l border-gray-200">
            <PdfDocument
              url={scanPdfUrl}
              side="scan"
              diffs={diffs}
              activeDiffId={activeDiffId}
              onSelectDiff={setActiveDiffId}
              pageScrollAnchor={scrollAnchor}
            />
          </div>
        </div>
        <div className="bg-white overflow-hidden">
          {diffsQ.isLoading ? (
            <div className="p-8 text-center text-gray-500">加载差异中...</div>
          ) : (
            <DiffSidebar
              diffs={diffs}
              activeDiffId={activeDiffId}
              onSelect={setActiveDiffId}
              comparisonId={cid}
              includeNoise={includeNoise}
              onIncludeNoiseChange={setIncludeNoise}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function Toolbar({ cmp, onBack, onComplete }: { cmp: any; onBack: () => void; onComplete?: () => void }) {
  const s = cmp.summary_json;
  return (
    <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center gap-4">
      <button onClick={onBack} className="btn-secondary !py-1 !px-2">
        <ArrowLeft className="w-3.5 h-3.5" />
      </button>
      <FileText className="w-4 h-4 text-gray-400" />
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{cmp.title}</div>
        <div className="text-xs text-gray-500">
          #{cmp.id} · 创建于 {fmtTime(cmp.created_at)} · {REVIEW_STATUS_LABEL[cmp.review_status as keyof typeof REVIEW_STATUS_LABEL]}
        </div>
      </div>
      {s && (
        <div className="flex gap-2 text-xs">
          <Stat label="真实差异" value={s.real} color="bg-orange-100 text-orange-800" />
          <Stat label="关键" value={s.critical} color="bg-red-600 text-white" star />
          <Stat label="新增" value={s.insert + s.handwritten} color="bg-green-100 text-green-800" />
          <Stat label="删除" value={s.delete} color="bg-red-100 text-red-800" />
          <Stat label="修改" value={s.replace} color="bg-yellow-100 text-yellow-800" />
          <Stat label="章遮挡" value={s.stamp_covered} color="bg-gray-200 text-gray-700" />
        </div>
      )}
      {cmp.status === "done" && cmp.review_status !== "completed" && onComplete && (
        <button onClick={onComplete} className="btn-primary !py-1.5">
          <CheckCircle2 className="w-3.5 h-3.5" /> 完成审核
        </button>
      )}
      {cmp.review_status === "completed" && (
        <span className="badge bg-green-600 text-white">✓ 已审核</span>
      )}
    </div>
  );
}

function Stat({ label, value, color, star }: { label: string; value: number; color: string; star?: boolean }) {
  return (
    <div className="flex flex-col items-center min-w-[44px]">
      <span className={`badge ${color}`}>
        {star && "★"}{value}
      </span>
      <span className="text-[10px] text-gray-500 mt-0.5">{label}</span>
    </div>
  );
}
