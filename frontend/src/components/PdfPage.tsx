/**
 * 单页 PDF 渲染：把 pdf.js PDFDocumentProxy 的某一页 render 到 canvas，
 * 上面叠加该页相关的差异高亮框，点击高亮触发回调。
 */
import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import type { Diff } from "@/types";

interface Props {
  pdf: PDFDocumentProxy | null;
  pageNumber: number;            // 1-based
  side: "orig" | "scan";
  diffs: Diff[];                 // 该侧、该页相关的所有差异
  activeDiffId: number | null;
  onSelectDiff: (id: number) => void;
  scale?: number;                // canvas 渲染 scale，默认 1.5
}

export default function PdfPage({
  pdf, pageNumber, side, diffs, activeDiffId, onSelectDiff, scale = 1.5,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [pageSize, setPageSize] = useState({ w: 0, h: 0, pw: 0, ph: 0 });

  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;

    (async () => {
      try {
        const page = await pdf.getPage(pageNumber);
        if (cancelled) return;
        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await page.render({ canvasContext: ctx, viewport, canvas }).promise;
        if (cancelled) return;
        const orig = page.getViewport({ scale: 1 });
        setPageSize({
          w: viewport.width, h: viewport.height,
          pw: orig.width, ph: orig.height,
        });
      } catch (e) {
        console.error("render page", pageNumber, e);
      }
    })();

    return () => { cancelled = true; };
  }, [pdf, pageNumber, scale]);

  // 滚动到激活的差异（如果该差异在本页）
  useEffect(() => {
    if (!activeDiffId || !wrapperRef.current) return;
    const el = wrapperRef.current.querySelector<HTMLElement>(`[data-diff-id="${activeDiffId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [activeDiffId]);

  return (
    <div ref={wrapperRef} className="pdf-canvas-wrapper">
      <canvas ref={canvasRef} />
      {pageSize.pw > 0 && diffs.map((d) => {
        const bbox = side === "orig" ? d.orig_bbox : d.scan_bbox;
        if (!bbox) return null;
        const [x0, y0, x1, y1] = bbox;
        // bbox 单位是 PDF pt，pageSize.pw/ph 是原始 pt
        const left = (x0 / pageSize.pw) * 100;
        const top = (y0 / pageSize.ph) * 100;
        const width = ((x1 - x0) / pageSize.pw) * 100;
        const height = ((y1 - y0) / pageSize.ph) * 100;
        const isActive = activeDiffId === d.id;
        return (
          <div
            key={d.id}
            data-diff-id={d.id}
            className={`diff-hl diff-hl-${d.category} ${isActive ? "active" : ""}`}
            style={{
              left: `${left}%`,
              top: `${top}%`,
              width: `${Math.max(width, 0.5)}%`,
              height: `${Math.max(height, 0.5)}%`,
            }}
            title={`#${d.seq_no} [${d.category}] ${d.orig_text || "—"} → ${d.scan_text || "—"}`}
            onClick={(e) => { e.stopPropagation(); onSelectDiff(d.id); }}
          />
        );
      })}
    </div>
  );
}
