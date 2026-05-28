import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/api/client";
import { Loader2, AlertCircle } from "lucide-react";
import type { Diff } from "@/types";

interface Props {
  cid: number;
  side: "orig" | "scan";
  diffs: Diff[];
  activeDiffId: number | null;
  onDiffClick?: (d: Diff) => void;
}

const CATEGORY_BG: Record<string, string> = {
  replace: "bg-yellow-200/70",
  delete: "bg-red-200/70",
  insert: "bg-green-200/70",
  handwritten: "bg-green-200/70",
  stamp_covered: "bg-gray-200",
  moved: "bg-blue-100",
};

/**
 * Word 文档视图：纯文本并排展示，按段落渲染，差异 token 在文本上 inline 高亮。
 *
 * 因为 Word 没有物理坐标，使用 bbox.y 作为"段落索引 × 20"反推 para_idx，
 * 然后在该段落文本上根据字符内容做局部匹配着色。
 */
export default function DocxViewer({ cid, side, diffs, activeDiffId, onDiffClick }: Props) {
  const [paragraphs, setParagraphs] = useState<string[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const paraRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    setParagraphs(null);
    setErr(null);
    api
      .get<{ paragraphs: string[] }>(`/api/comparisons/${cid}/${side}/text.json`)
      .then((r) => setParagraphs(r.data.paragraphs))
      .catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [cid, side]);

  // 把差异按 para_idx 分组：bbox 的 y 坐标 / 20 = para_idx
  const diffsByPara = useMemo(() => {
    const map = new Map<number, Diff[]>();
    for (const d of diffs) {
      const bbox = side === "orig" ? d.orig_bbox : d.scan_bbox;
      const text = side === "orig" ? d.orig_text : d.scan_text;
      if (!bbox || !text) continue;
      const paraIdx = Math.round(bbox[1] / 20);
      if (!map.has(paraIdx)) map.set(paraIdx, []);
      map.get(paraIdx)!.push(d);
    }
    return map;
  }, [diffs, side]);

  // active diff 自动滚动到段落
  useEffect(() => {
    if (!activeDiffId || !paragraphs) return;
    const target = diffs.find((d) => d.id === activeDiffId);
    if (!target) return;
    const bbox = side === "orig" ? target.orig_bbox : target.scan_bbox;
    if (!bbox) return;
    const paraIdx = Math.round(bbox[1] / 20);
    const el = paraRefs.current[paraIdx];
    if (el && containerRef.current) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [activeDiffId, diffs, paragraphs, side]);

  if (err) {
    return (
      <div className="h-full flex items-center justify-center text-red-600 text-sm gap-2">
        <AlertCircle className="w-4 h-4" /> 加载失败：{err}
      </div>
    );
  }
  if (!paragraphs) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500 text-sm gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> 加载 Word 文本...
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full overflow-auto bg-white">
      <div className="max-w-3xl mx-auto p-6 text-sm leading-relaxed">
        {paragraphs.map((text, idx) => (
          <ParagraphLine
            key={idx}
            text={text}
            idx={idx}
            diffs={diffsByPara.get(idx) || []}
            activeDiffId={activeDiffId}
            onDiffClick={onDiffClick}
            innerRef={(el) => (paraRefs.current[idx] = el)}
          />
        ))}
      </div>
    </div>
  );
}

/** 单个段落，差异 token 在文本里 inline 着色。 */
function ParagraphLine({
  text, idx, diffs, activeDiffId, onDiffClick, innerRef,
}: {
  text: string;
  idx: number;
  diffs: Diff[];
  activeDiffId: number | null;
  onDiffClick?: (d: Diff) => void;
  innerRef: (el: HTMLDivElement | null) => void;
}) {
  // 没差异：直接渲染
  if (diffs.length === 0) {
    return (
      <div ref={innerRef} data-para={idx} className="py-1 px-2 hover:bg-gray-50 rounded">
        <span className="text-gray-400 text-xs mr-2 inline-block w-8 text-right select-none">
          {idx + 1}
        </span>
        <span className="text-gray-800">{text || <em className="text-gray-300">（空）</em>}</span>
      </div>
    );
  }

  // 有差异：split 后再拼，每个 diff token 用 mark 包裹
  const segments = splitByDiffs(text, diffs);

  return (
    <div
      ref={innerRef}
      data-para={idx}
      className="py-1 px-2 hover:bg-gray-50 rounded"
    >
      <span className="text-gray-400 text-xs mr-2 inline-block w-8 text-right select-none">
        {idx + 1}
      </span>
      {segments.map((seg, i) => {
        if (!seg.diff) return <span key={i} className="text-gray-800">{seg.text}</span>;
        const cls = CATEGORY_BG[seg.diff.category] || "bg-orange-200/60";
        const active = seg.diff.id === activeDiffId;
        return (
          <span
            key={i}
            className={`${cls} px-0.5 rounded cursor-pointer transition-all ${
              active ? "ring-2 ring-blue-500 ring-offset-1" : "hover:brightness-95"
            }`}
            onClick={() => onDiffClick?.(seg.diff!)}
            title={`#${seg.diff.seq_no} ${seg.diff.category}`}
          >
            {seg.text}
          </span>
        );
      })}
    </div>
  );
}

type Segment = { text: string; diff: Diff | null };

/** 把段落文本按 diff 的 orig_text/scan_text 拆分着色。
 * 简单策略：每个 diff 在文本里 indexOf 第一次出现的位置着色。
 * 多个 diff 重叠时按出现先后排序，重叠区域取最早一个。
 */
function splitByDiffs(text: string, diffs: Diff[]): Segment[] {
  if (!text) {
    // 段落本身为空，但有 insert 差异 → 整段标绿（手写填空）
    const nonEmpty = diffs.find((d) => d.scan_text || d.orig_text);
    if (nonEmpty) {
      return [{ text: (nonEmpty.scan_text || nonEmpty.orig_text), diff: nonEmpty }];
    }
    return [{ text: "（空）", diff: null }];
  }

  // 收集所有 (start, end, diff) 命中区间
  type Range = { start: number; end: number; diff: Diff };
  const ranges: Range[] = [];
  for (const d of diffs) {
    const needle = d.orig_text || d.scan_text || "";
    if (!needle) continue;
    const idx = text.indexOf(needle);
    if (idx >= 0) {
      ranges.push({ start: idx, end: idx + needle.length, diff: d });
    } else {
      // 没匹配上：把它当作"段落级"差异，附加到末尾
      ranges.push({ start: text.length, end: text.length, diff: d });
    }
  }
  ranges.sort((a, b) => a.start - b.start);

  const segs: Segment[] = [];
  let cursor = 0;
  for (const r of ranges) {
    if (r.start > cursor) {
      segs.push({ text: text.slice(cursor, r.start), diff: null });
    }
    if (r.end > r.start) {
      segs.push({ text: text.slice(r.start, r.end), diff: r.diff });
      cursor = Math.max(cursor, r.end);
    } else {
      // 零长度（没匹配到）→ 末尾标记
      segs.push({ text: ` [${r.diff.category}]`, diff: r.diff });
    }
  }
  if (cursor < text.length) {
    segs.push({ text: text.slice(cursor), diff: null });
  }
  return segs;
}
