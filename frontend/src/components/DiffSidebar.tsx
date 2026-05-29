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

  // 关键字段差异（v11 字段层，context 带「【关键字段」前缀）单独成组置顶
  const { fieldDiffs, otherDiffs } = useMemo(() => {
    const field: Diff[] = [];
    const other: Diff[] = [];
    for (const d of filtered) {
      if ((d.context || "").startsWith("【关键字段")) field.push(d);
      else other.push(d);
    }
    return { fieldDiffs: field, otherDiffs: other };
  }, [filtered]);

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
    <div className="flex flex-col h-full bg-bg-elevated">
      {/* 筛选器 */}
      <div className="border-b border-border p-3 space-y-2.5">
        <label className="inline-flex items-center gap-2 cursor-pointer text-[12px] text-fg-muted">
          <input type="checkbox" checked={includeNoise}
                 onChange={(e) => onIncludeNoiseChange(e.target.checked)}
                 className="accent-fg w-3.5 h-3.5" />
          <span>显示噪声（位移 / 页脚 / 单字）</span>
        </label>
        <div className="flex flex-wrap gap-1">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => {
                const s = new Set(catFilter);
                if (s.has(c)) s.delete(c); else s.add(c);
                setCatFilter(s);
              }}
              className={`badge cursor-pointer transition-all ${
                catFilter.has(c)
                  ? `badge-${c}`
                  : "bg-bg-tint text-fg-muted hover:bg-bg-subtle"
              }`}
            >
              {CATEGORY_LABEL[c]}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1 text-[12px]">
          <span className="text-fg-subtle mr-1.5">审核:</span>
          {(["all", "yes", "no"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setReviewedFilter(v)}
              className={`badge cursor-pointer transition-all ${
                reviewedFilter === v ? "bg-fg text-bg" : "bg-bg-tint text-fg-muted"
              }`}
            >
              {v === "all" ? "全部" : v === "yes" ? "已审" : "未审"}
            </button>
          ))}
          <span className="ml-auto text-fg-subtle tabular-nums">
            {filtered.length} <span className="text-fg-subtle/60">/ {diffs.length}</span>
          </span>
        </div>
      </div>

      {/* 列表 */}
      <div ref={listRef} className="flex-1 overflow-y-auto">
        {filtered.length === 0 && (
          <div className="p-10 text-center text-fg-subtle text-[13px]">无符合条件的差异</div>
        )}

        {/* 关键字段组（置顶强调） */}
        {fieldDiffs.length > 0 && (
          <>
            <div className="sticky top-0 z-10 flex items-center gap-1.5 px-3 py-1.5 bg-critical-soft border-b border-border">
              <span className="star text-[12px]">★</span>
              <span className="text-[11px] font-semibold text-critical-soft-fg tracking-wide">
                关键字段差异
              </span>
              <span className="text-[10.5px] text-critical-soft-fg/70 tabular-nums ml-auto">
                {fieldDiffs.length} 项
              </span>
            </div>
            {fieldDiffs.map((d) => (
              <DiffRow
                key={d.id}
                d={d}
                active={d.id === activeDiffId}
                onClick={() => onSelect(d.id)}
                onReview={(action) => review(d.id, action)}
                emphasize
              />
            ))}
          </>
        )}

        {/* 其他差异组 */}
        {fieldDiffs.length > 0 && otherDiffs.length > 0 && (
          <div className="px-3 py-1.5 bg-bg-subtle border-b border-border text-[11px] font-medium text-fg-muted tracking-wide">
            其他差异 <span className="text-fg-subtle tabular-nums">{otherDiffs.length} 项</span>
          </div>
        )}
        {otherDiffs.map((d) => (
          <DiffRow
            key={d.id}
            d={d}
            active={d.id === activeDiffId}
            onClick={() => onSelect(d.id)}
            onReview={(action) => review(d.id, action)}
          />
        ))}
      </div>

      {/* 快捷键提示 */}
      <div className="border-t border-border bg-bg-subtle px-3 py-2 text-[11px] text-fg-muted flex items-center gap-3 flex-wrap">
        <span className="inline-flex items-center gap-1"><span className="kbd">↑</span><span className="kbd">↓</span> 切换</span>
        <span className="inline-flex items-center gap-1"><span className="kbd">Y</span> 确认</span>
        <span className="inline-flex items-center gap-1"><span className="kbd">N</span> 忽略</span>
        <span className="inline-flex items-center gap-1"><span className="kbd">U</span> 撤销</span>
      </div>
    </div>
  );
}

function DiffRow({
  d, active, onClick, onReview, emphasize,
}: {
  d: Diff;
  active: boolean;
  onClick: () => void;
  onReview: (action: ReviewAction | null) => void;
  emphasize?: boolean;
}) {
  const [showNote, setShowNote] = useState(false);
  const page = d.scan_page >= 0 ? d.scan_page : d.orig_page;
  const leftBar =
    d.review_action === "confirmed" ? "border-l-[3px] border-l-critical" :
    d.review_action === "ignored" ? "border-l-[3px] border-l-fg-subtle opacity-50" :
    emphasize ? "border-l-[3px] border-l-critical/40" :
    "border-l-[3px] border-l-transparent";

  // 关键字段行：从 context「【关键字段·合同金额（大写）·删除】」提取字段名
  const fieldLabel = emphasize
    ? (d.context.match(/【关键字段·([^·】]+)/)?.[1] ?? "关键字段")
    : null;

  return (
    <div
      data-row-id={d.id}
      className={`px-3 py-2.5 cursor-pointer transition-all border-b border-border/60 ${leftBar} ${
        active ? "bg-accent-soft/50" : emphasize ? "bg-critical-soft/30 hover:bg-critical-soft/50" : "hover:bg-bg-subtle"
      }`}
      onClick={onClick}
    >
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-[10.5px] text-fg-subtle font-mono tabular-nums">#{String(d.seq_no).padStart(3, '0')}</span>
        {fieldLabel ? (
          <span className="badge badge-critical">★ {fieldLabel}</span>
        ) : (
          <>
            <span className={`badge badge-${d.category}`}>{CATEGORY_LABEL[d.category]}</span>
            {d.severity === "critical" && <span className="badge badge-critical">★ 关键</span>}
          </>
        )}
        <span className="text-[10.5px] text-fg-muted ml-auto tabular-nums">P{page + 1}</span>
      </div>
      <div className="space-y-1 text-[12px] font-mono leading-relaxed">
        {d.orig_text && (
          <div className="text-critical-soft-fg">
            <span className="text-fg-subtle inline-block w-3">原</span> {d.orig_text.length > 50 ? d.orig_text.slice(0, 50) + "…" : d.orig_text}
          </div>
        )}
        {d.scan_text && (
          <div className="text-success-soft-fg">
            <span className="text-fg-subtle inline-block w-3">{emphasize ? "新" : "扫"}</span> {d.scan_text.length > 50 ? d.scan_text.slice(0, 50) + "…" : d.scan_text}
          </div>
        )}
        {/* 关键字段行不重复显示 context（已在 badge 体现），普通行显示 */}
        {d.context && !emphasize && (
          <div className="text-fg-subtle text-[10.5px] truncate mt-1">{d.context}</div>
        )}
        {d.review_note && (
          <div className="text-fg-muted italic text-[11.5px] mt-1 pl-3 border-l border-border">💬 {d.review_note}</div>
        )}
      </div>
      {active && (
        <div className="mt-2.5 flex gap-1.5 anim-fade-in" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => onReview(d.review_action === "confirmed" ? null : "confirmed")}
            className={`inline-flex items-center gap-1 px-2 h-7 rounded text-[11.5px] font-medium transition-all border ${
              d.review_action === "confirmed"
                ? "bg-critical text-white border-critical"
                : "bg-bg-elevated border-border hover:border-critical hover:text-critical"
            }`}
            title="快捷键 Y"
          >
            <Check className="w-3 h-3" /> 确认
          </button>
          <button
            onClick={() => onReview(d.review_action === "ignored" ? null : "ignored")}
            className={`inline-flex items-center gap-1 px-2 h-7 rounded text-[11.5px] font-medium transition-all border ${
              d.review_action === "ignored"
                ? "bg-fg-muted text-bg border-fg-muted"
                : "bg-bg-elevated border-border hover:border-fg-muted"
            }`}
            title="快捷键 N"
          >
            <X className="w-3 h-3" /> 忽略
          </button>
          <button
            onClick={() => setShowNote((v) => !v)}
            className="inline-flex items-center gap-1 px-2 h-7 rounded text-[11.5px] font-medium border bg-bg-elevated border-border hover:border-fg transition-all ml-auto"
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
