/**
 * 差异侧栏：列表、筛选、键盘导航、审核操作。
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, X, MessageSquare, ChevronDown } from "lucide-react";
import { updateDiffReview } from "@/api/endpoints";
import { errMsg } from "@/api/client";
import { CATEGORY_LABEL } from "@/lib/utils";
import type { Diff, DiffCategory, DiffSeverity, ReviewAction } from "@/types";

interface Props {
  diffs: Diff[];
  activeDiffId: number | null;
  onSelect: (id: number) => void;
  comparisonId: number;
  includeNoise: boolean;
  onIncludeNoiseChange: (v: boolean) => void;
}

const CATEGORIES: DiffCategory[] = [
  "replace", "delete", "insert", "handwritten", "stamp_covered", "moved",
];

export default function DiffSidebar({
  diffs, activeDiffId, onSelect, comparisonId, includeNoise, onIncludeNoiseChange,
}: Props) {
  const qc = useQueryClient();
  const [catFilter, setCatFilter] = useState<Set<DiffCategory>>(new Set());
  const [sevFilter, setSevFilter] = useState<Set<DiffSeverity>>(new Set());
  const [reviewedFilter, setReviewedFilter] = useState<"all" | "yes" | "no">("all");
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    return diffs.filter((d) => {
      if (catFilter.size && !catFilter.has(d.category)) return false;
      if (sevFilter.size && !sevFilter.has(d.severity)) return false;
      if (reviewedFilter === "yes" && !d.review_action) return false;
      if (reviewedFilter === "no" && d.review_action) return false;
      return true;
    });
  }, [diffs, catFilter, sevFilter, reviewedFilter]);

  // 自动把激活条滚到可视区
  useEffect(() => {
    if (!activeDiffId || !listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(`[data-row-id="${activeDiffId}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [activeDiffId]);

  const reviewMut = useMutation({
    mutationFn: ({ id, action, note }: { id: number; action: ReviewAction | null; note?: string }) =>
      updateDiffReview(id, { review_action: action, review_note: note ?? null }),
    onSuccess: (d) => {
      qc.setQueryData(["diffs", comparisonId], (old: Diff[] | undefined) =>
        old ? old.map((x) => (x.id === d.id ? d : x)) : old
      );
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  function review(id: number, action: ReviewAction | null) {
    reviewMut.mutate({ id, action });
  }

  // 当前激活索引（在 filtered 中）
  const activeIdx = filtered.findIndex((d) => d.id === activeDiffId);

  // 键盘导航
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // 在 input/textarea 里不响应
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      if (e.key === "ArrowDown" || e.key === "j") {
        e.preventDefault();
        const next = filtered[Math.min(filtered.length - 1, activeIdx + 1)];
        if (next) onSelect(next.id);
      } else if (e.key === "ArrowUp" || e.key === "k") {
        e.preventDefault();
        const prev = filtered[Math.max(0, activeIdx - 1)];
        if (prev) onSelect(prev.id);
      } else if ((e.key === "y" || e.key === "Y") && activeDiffId) {
        e.preventDefault();
        review(activeDiffId, "confirmed");
      } else if ((e.key === "n" || e.key === "N") && activeDiffId) {
        e.preventDefault();
        review(activeDiffId, "ignored");
      } else if ((e.key === "u" || e.key === "U") && activeDiffId) {
        e.preventDefault();
        review(activeDiffId, null);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filtered, activeIdx, activeDiffId, comparisonId]);

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-gray-200 p-2 space-y-2 bg-white">
        <div className="flex items-center gap-1 text-xs">
          <label className="inline-flex items-center gap-1">
            <input type="checkbox" checked={includeNoise} onChange={(e) => onIncludeNoiseChange(e.target.checked)} />
            <span>显示噪声（位移/页脚/单字）</span>
          </label>
        </div>
        <div className="flex flex-wrap gap-1">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => {
                const s = new Set(catFilter);
                if (s.has(c)) s.delete(c); else s.add(c);
                setCatFilter(s);
              }}
              className={`badge cursor-pointer ${
                catFilter.has(c)
                  ? `badge-${c}`
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {CATEGORY_LABEL[c]}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-500">审核:</span>
          {(["all", "yes", "no"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setReviewedFilter(v)}
              className={`badge cursor-pointer ${
                reviewedFilter === v ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"
              }`}
            >
              {v === "all" ? "全部" : v === "yes" ? "已审" : "未审"}
            </button>
          ))}
          <span className="ml-auto text-gray-500">{filtered.length} / {diffs.length}</span>
        </div>
      </div>

      <div ref={listRef} className="flex-1 overflow-y-auto">
        {filtered.length === 0 && (
          <div className="p-8 text-center text-gray-400 text-sm">无符合条件的差异</div>
        )}
        {filtered.map((d) => (
          <DiffRow
            key={d.id}
            d={d}
            active={d.id === activeDiffId}
            onClick={() => onSelect(d.id)}
            onReview={(action) => review(d.id, action)}
          />
        ))}
      </div>

      <div className="border-t bg-gray-50 p-2 text-xs text-gray-500">
        快捷键：↑↓ 切换 · <kbd className="px-1 bg-white border rounded">Y</kbd> 确认 ·{" "}
        <kbd className="px-1 bg-white border rounded">N</kbd> 忽略 ·{" "}
        <kbd className="px-1 bg-white border rounded">U</kbd> 撤销
      </div>
    </div>
  );
}

function DiffRow({
  d, active, onClick, onReview,
}: {
  d: Diff;
  active: boolean;
  onClick: () => void;
  onReview: (action: ReviewAction | null) => void;
}) {
  const [showNote, setShowNote] = useState(false);
  const page = d.scan_page >= 0 ? d.scan_page : d.orig_page;
  return (
    <div
      data-row-id={d.id}
      className={`border-b border-gray-100 px-2 py-2 cursor-pointer transition-colors ${
        active ? "bg-blue-50" : "hover:bg-gray-50"
      } ${d.review_action === "confirmed" ? "border-l-4 border-l-red-500" :
         d.review_action === "ignored" ? "border-l-4 border-l-gray-400 opacity-60" : ""}`}
      onClick={onClick}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <span className="text-xs text-gray-400 font-mono">#{d.seq_no}</span>
        <span className={`badge badge-${d.category}`}>{CATEGORY_LABEL[d.category]}</span>
        {d.severity === "critical" && <span className="badge badge-critical">★ 关键</span>}
        <span className="text-xs text-gray-500 ml-auto">P{page + 1}</span>
      </div>
      <div className="space-y-1 text-xs font-mono">
        {d.orig_text && (
          <div className="text-red-700">
            <span className="text-gray-400">原</span> {d.orig_text.length > 50 ? d.orig_text.slice(0, 50) + "…" : d.orig_text}
          </div>
        )}
        {d.scan_text && (
          <div className="text-green-700">
            <span className="text-gray-400">扫</span> {d.scan_text.length > 50 ? d.scan_text.slice(0, 50) + "…" : d.scan_text}
          </div>
        )}
        {d.context && (
          <div className="text-gray-400 text-[10px] truncate">{d.context}</div>
        )}
        {d.review_note && (
          <div className="text-gray-600 italic">💬 {d.review_note}</div>
        )}
      </div>
      {active && (
        <div className="mt-2 flex gap-1" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => onReview(d.review_action === "confirmed" ? null : "confirmed")}
            className={`btn !py-1 !px-2 text-xs ${
              d.review_action === "confirmed" ? "bg-red-600 text-white border-red-600" : "bg-white border-gray-300"
            }`}
            title="Y: 确认"
          >
            <Check className="w-3 h-3" /> 确认
          </button>
          <button
            onClick={() => onReview(d.review_action === "ignored" ? null : "ignored")}
            className={`btn !py-1 !px-2 text-xs ${
              d.review_action === "ignored" ? "bg-gray-500 text-white border-gray-500" : "bg-white border-gray-300"
            }`}
            title="N: 忽略"
          >
            <X className="w-3 h-3" /> 忽略
          </button>
          <button
            onClick={() => setShowNote((v) => !v)}
            className="btn !py-1 !px-2 text-xs bg-white border-gray-300"
            title="批注"
          >
            <MessageSquare className="w-3 h-3" />
            {d.review_note ? "改" : "批注"}
          </button>
        </div>
      )}
      {active && showNote && (
        <NoteEditor d={d} onSave={(note) => { /* 用 PATCH 复用 review_action */ }} onClose={() => setShowNote(false)} />
      )}
    </div>
  );
}

function NoteEditor({ d, onClose }: { d: Diff; onSave: (n: string) => void; onClose: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState(d.review_note || "");
  const m = useMutation({
    mutationFn: (note: string) =>
      updateDiffReview(d.id, { review_action: d.review_action, review_note: note }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["diffs"] });
      toast.success("批注已保存");
      onClose();
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  return (
    <div className="mt-2" onClick={(e) => e.stopPropagation()}>
      <textarea
        className="input text-xs"
        rows={2}
        autoFocus
        placeholder="批注内容..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="flex gap-1 mt-1">
        <button onClick={() => m.mutate(text)} className="btn-primary !py-1 !px-2 text-xs">保存</button>
        <button onClick={onClose} className="btn-secondary !py-1 !px-2 text-xs">取消</button>
      </div>
    </div>
  );
}
