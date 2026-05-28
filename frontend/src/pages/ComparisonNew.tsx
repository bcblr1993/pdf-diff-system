import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  Upload, FileText, X, Settings, AlertTriangle, ArrowLeftRight, Layers, Plus, Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { createComparison, createBatch } from "@/api/endpoints";
import { errMsg } from "@/api/client";
import { fmtBytes } from "@/lib/utils";

type Mode = "single" | "batch";

export default function ComparisonNew() {
  const nav = useNavigate();
  const [mode, setMode] = useState<Mode>("single");
  const [title, setTitle] = useState("");
  const [orig, setOrig] = useState<File | null>(null);
  const [scan, setScan] = useState<File | null>(null);
  const [scans, setScans] = useState<File[]>([]);
  const [dpi, setDpi] = useState(200);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const singleMut = useMutation({
    mutationFn: createComparison,
    onSuccess: (r) => {
      toast.success(`已创建任务 #${r.id}`);
      nav(`/comparisons/${r.id}`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const batchMut = useMutation({
    mutationFn: createBatch,
    onSuccess: (r) => {
      toast.success(`已创建批量任务 #${r.id}，共 ${r.total} 个子对比`);
      nav(`/batches/${r.id}`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  function submit() {
    if (mode === "single") {
      if (!orig || !scan) {
        toast.error("请上传两份 PDF");
        return;
      }
      singleMut.mutate({
        title: title || `${orig.name} vs ${scan.name}`,
        orig, scan, dpi,
      });
    } else {
      if (!orig) {
        toast.error("请上传原件 PDF");
        return;
      }
      if (scans.length === 0) {
        toast.error("请上传至少 1 份扫描件");
        return;
      }
      batchMut.mutate({
        title: title || `${orig.name} → ${scans.length} 份扫描件`,
        orig, scans, dpi,
      });
    }
  }

  const pending = singleMut.isPending || batchMut.isPending;

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-xl font-semibold mb-1">新建对比任务</h1>
      <p className="text-sm text-fg-muted mb-3">
        上传原件与对方版本，系统自动对比并产出差异清单。
      </p>
      <div className="flex items-center gap-2 mb-4 text-[11.5px]">
        <span className="text-fg-subtle tracking-wide">支持格式：</span>
        <span className="badge badge-insert font-mono">.pdf</span>
        <span className="badge badge-insert font-mono">.docx</span>
        <span className="text-fg-subtle">·</span>
        <span className="text-fg-subtle">单份 ≤ 100MB</span>
      </div>

      {/* 模式切换 */}
      <div className="card p-1 mb-4 inline-flex gap-1">
        <button
          onClick={() => setMode("single")}
          className={`px-3.5 py-2 rounded text-sm font-medium transition-colors inline-flex items-center gap-1.5 ${
            mode === "single"
              ? "bg-accent text-white shadow-sm"
              : "text-fg-muted hover:bg-bg-subtle"
          }`}
        >
          <FileText className="w-3.5 h-3.5" /> 单对比
        </button>
        <button
          onClick={() => setMode("batch")}
          className={`px-3.5 py-2 rounded text-sm font-medium transition-colors inline-flex items-center gap-1.5 ${
            mode === "batch"
              ? "bg-accent text-white shadow-sm"
              : "text-fg-muted hover:bg-bg-subtle"
          }`}
        >
          <Layers className="w-3.5 h-3.5" /> 批量对比
          <span className="text-[10.5px] opacity-70 ml-0.5">1 × N</span>
        </button>
      </div>

      <div className="card p-3 mb-4 bg-amber-50 border-amber-200 flex items-start gap-2 text-sm">
        <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
        <div className="text-amber-900 leading-relaxed">
          <strong>注意上传位置：</strong>
          「原件」放<strong>电子矢量版</strong>（文字可复制的 PDF 或 Word）；
          「扫描件」放<strong>对方返回版</strong>（盖章扫描 PDF 或对方修改后的 Word）。
          支持两份都是 PDF / 两份都是 Word / PDF×Word 任意组合；位置放反会导致结果完全异常。
        </div>
      </div>

      <div className="space-y-4">
        <div className="card p-4">
          <label className="label">任务标题（可选）</label>
          <input
            className="input"
            placeholder={mode === "single"
              ? "例如：江苏中广核 V2.0 采购合同 - 2026"
              : "例如：服务器采购合同 - 6 家盖章版"}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        {mode === "single" ? (
          <div className="grid grid-cols-[1fr_auto_1fr] gap-3 items-stretch">
            <DropZone label="① 原件（电子版）" hint="PDF 或 Word（文字可复制）" file={orig} onChange={setOrig} />
            <div className="flex items-center">
              <button
                onClick={() => { const a = orig; setOrig(scan); setScan(a); }}
                className="btn btn-secondary !h-10 !w-10 !p-0"
                title="交换两侧文件"
                disabled={!orig && !scan}
              >
                <ArrowLeftRight className="w-4 h-4" />
              </button>
            </div>
            <DropZone label="② 对方版本" hint="盖章扫描 PDF 或对方修改后的 Word" file={scan} onChange={setScan} />
          </div>
        ) : (
          <>
            <DropZone label="① 原件（电子版，1 份）" hint="PDF 或 Word；所有对方版本都与该原件对比" file={orig} onChange={setOrig} />
            <MultiDropZone label="② 对方版本（多份）" files={scans} onChange={setScans} />
          </>
        )}

        <div className="card p-4">
          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className="text-sm text-fg-muted hover:text-fg inline-flex items-center gap-1.5 transition-colors"
          >
            <Settings className="w-3.5 h-3.5" /> 高级设置
            <span className="text-fg-subtle text-[10px]">{showAdvanced ? "▲" : "▼"}</span>
          </button>
          {showAdvanced && (
            <div className="mt-3 grid grid-cols-2 gap-4">
              <div>
                <label className="label">OCR DPI</label>
                <select className="input" value={dpi} onChange={(e) => setDpi(Number(e.target.value))}>
                  <option value={150}>150（最快）</option>
                  <option value={200}>200（推荐）</option>
                  <option value={250}>250</option>
                  <option value={300}>300（最准）</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">越高越准但越慢。小字密集场景建议 300。</p>
              </div>
            </div>
          )}
        </div>

        <div className="flex gap-2 justify-end">
          <button onClick={() => nav(-1)} className="btn-secondary">取消</button>
          <button onClick={submit} className="btn-primary" disabled={pending}>
            <Upload className="w-3.5 h-3.5" />
            {pending ? "上传中..." : (mode === "single" ? "开始对比" : `开始批量对比（${scans.length} 份）`)}
          </button>
        </div>
      </div>
    </div>
  );
}

function DropZone({
  label, hint, file, onChange,
}: { label: string; hint: string; file: File | null; onChange: (f: File | null) => void }) {
  const [drag, setDrag] = useState(false);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f && (f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf") || f.name.toLowerCase().endsWith(".docx"))) {
      onChange(f);
    } else {
      toast.error("请上传 PDF 或 Word (.docx) 文件");
    }
  }

  return (
    <div className="card p-4">
      <label className="label">{label}</label>
      {file ? (
        <div className="border border-gray-200 rounded p-3 bg-gray-50 flex items-center gap-3">
          <FileText className="w-8 h-8 text-blue-600 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm truncate">{file.name}</div>
            <div className="text-xs text-gray-500">{fmtBytes(file.size)}</div>
          </div>
          <button onClick={() => onChange(null)} className="text-gray-400 hover:text-gray-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <label
          className={`block border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
            drag ? "border-blue-500 bg-blue-50" : "border-gray-300 bg-gray-50 hover:bg-gray-100"
          }`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
        >
          <Upload className="w-8 h-8 mx-auto text-gray-400 mb-2" />
          <div className="text-sm text-fg">拖拽或点击选择文件</div>
          <div className="text-[10.5px] text-fg-subtle mt-0.5 font-mono">.pdf · .docx</div>
          <div className="text-xs text-gray-400 mt-1">{hint}</div>
          <input
            type="file" className="hidden" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(e) => onChange(e.target.files?.[0] ?? null)}
          />
        </label>
      )}
    </div>
  );
}

function MultiDropZone({
  label, files, onChange,
}: { label: string; files: File[]; onChange: (f: File[]) => void }) {
  const [drag, setDrag] = useState(false);

  function addFiles(newFiles: FileList | File[] | null) {
    if (!newFiles) return;
    const arr = Array.from(newFiles).filter((f) =>
      f.type === "application/pdf" || /\.(pdf|docx)$/i.test(f.name)
    );
    if (arr.length === 0) {
      toast.error("请上传 PDF 或 Word (.docx) 文件");
      return;
    }
    // 去重（按 name + size）
    const map = new Map(files.map((f) => [`${f.name}_${f.size}`, f]));
    for (const f of arr) map.set(`${f.name}_${f.size}`, f);
    onChange([...map.values()]);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    addFiles(e.dataTransfer.files);
  }

  function removeAt(idx: number) {
    onChange(files.filter((_, i) => i !== idx));
  }

  return (
    <div className="card p-4">
      <label className="label flex items-center justify-between">
        <span>{label}</span>
        {files.length > 0 && <span className="text-xs text-gray-500">{files.length} 份</span>}
      </label>

      <label
        className={`block border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
          drag ? "border-blue-500 bg-blue-50" : "border-gray-300 bg-gray-50 hover:bg-gray-100"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
      >
        <Plus className="w-6 h-6 mx-auto text-gray-400 mb-1" />
        <div className="text-sm text-fg">拖拽或点击添加多份文件</div>
        <div className="text-[10.5px] text-fg-subtle mt-0.5 font-mono">.pdf · .docx</div>
        <div className="text-[11px] text-fg-subtle mt-1">支持多选；单次最多 50 份</div>
        <input
          type="file" multiple className="hidden" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }}
        />
      </label>

      {files.length > 0 && (
        <ul className="mt-3 space-y-1">
          {files.map((f, i) => (
            <li key={`${f.name}_${f.size}_${i}`}
                className="flex items-center gap-2 px-2 py-1.5 rounded border border-gray-200 bg-gray-50 text-sm">
              <FileText className="w-4 h-4 text-blue-600 shrink-0" />
              <span className="flex-1 truncate">{f.name}</span>
              <span className="text-xs text-gray-500">{fmtBytes(f.size)}</span>
              <button onClick={() => removeAt(i)} className="text-gray-400 hover:text-red-600">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
