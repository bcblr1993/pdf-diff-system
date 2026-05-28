/**
 * 单侧 PDF 多页渲染容器。负责加载文档、渲染每一页（虚拟滚动暂略，全部渲染）。
 */
import { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import type { PDFDocumentProxy } from "pdfjs-dist";
import PdfPage from "./PdfPage";
import type { Diff } from "@/types";
import { useAuthStore } from "@/stores/auth";

// 配置 pdf.js worker（固定路径，避开 nginx 对 .mjs 的 MIME 与 Vite hash 问题）
pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

interface Props {
  url: string;
  side: "orig" | "scan";
  diffs: Diff[];
  activeDiffId: number | null;
  onSelectDiff: (id: number) => void;
  pageScrollAnchor: { side: string; page: number; ts: number } | null;
}

export default function PdfDocument({
  url, side, diffs, activeDiffId, onSelectDiff, pageScrollAnchor,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    (async () => {
      try {
        const task = pdfjsLib.getDocument({
          url,
          httpHeaders: token ? { Authorization: `Bearer ${token}` } : {},
        });
        const doc = await task.promise;
        if (cancelled) return;
        setPdf(doc);
        setNumPages(doc.numPages);
      } catch (e: any) {
        if (!cancelled) setErr(e?.message || "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [url, token]);

  // 响应跳转锚点：把对应页滚到视口
  useEffect(() => {
    if (!pageScrollAnchor || pageScrollAnchor.side !== side) return;
    const pageEl = containerRef.current?.querySelector<HTMLElement>(
      `[data-page="${pageScrollAnchor.page}"]`
    );
    if (pageEl) pageEl.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [pageScrollAnchor, side]);

  // 按页号分组差异，避免每页扫整个数组
  const diffsByPage = new Map<number, Diff[]>();
  for (const d of diffs) {
    const p = side === "orig" ? d.orig_page : d.scan_page;
    if (p < 0) continue;
    const arr = diffsByPage.get(p) || [];
    arr.push(d);
    diffsByPage.set(p, arr);
  }

  if (loading) return <div className="p-8 text-center text-fg-muted text-sm">加载 PDF 中…</div>;
  if (err) return <div className="p-8 text-center text-red-600">{err}</div>;

  return (
    <div ref={containerRef} className="space-y-3 p-2">
      {Array.from({ length: numPages }, (_, i) => i).map((i) => {
        const pageDiffs = diffsByPage.get(i) || [];
        return (
          <div key={i} data-page={i} className="space-y-1">
            <div className="text-xs text-fg-subtle px-1 tabular-nums">
              {side === "orig" ? "原件" : "扫描件"} · P{i + 1} / {numPages}
              {pageDiffs.length > 0 && <span className="ml-2">· {pageDiffs.length} 处差异</span>}
            </div>
            <PdfPage
              pdf={pdf}
              pageNumber={i + 1}
              side={side}
              diffs={pageDiffs}
              activeDiffId={activeDiffId}
              onSelectDiff={onSelectDiff}
            />
          </div>
        );
      })}
    </div>
  );
}
