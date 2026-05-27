import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Upload, FileText, X, Settings, AlertTriangle, ArrowLeftRight } from "lucide-react";
import { toast } from "sonner";
import { createComparison } from "@/api/endpoints";
import { errMsg } from "@/api/client";
import { fmtBytes } from "@/lib/utils";

export default function ComparisonNew() {
  const nav = useNavigate();
  const [title, setTitle] = useState("");
  const [orig, setOrig] = useState<File | null>(null);
  const [scan, setScan] = useState<File | null>(null);
  const [dpi, setDpi] = useState(200);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const m = useMutation({
    mutationFn: createComparison,
    onSuccess: (r) => {
      toast.success(`已创建任务 #${r.id}`);
      nav(`/comparisons/${r.id}`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  function submit() {
    if (!orig || !scan) {
      toast.error("请上传两份 PDF");
      return;
    }
    m.mutate({
      title: title || `${orig.name} vs ${scan.name}`,
      orig, scan, dpi,
    });
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-xl font-semibold mb-1">新建对比任务</h1>
      <p className="text-sm text-gray-500 mb-6">上传一份原件（电子矢量 PDF）和一份扫描件（盖章扫描 PDF），系统会自动 OCR 和对比。</p>

      <div className="card p-3 mb-4 bg-amber-50 border-amber-200 flex items-start gap-2 text-sm">
        <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
        <div className="text-amber-900">
          <strong>注意上传位置：</strong>
          <span className="ml-1">「原件」放<strong>电子矢量版</strong>（文字可复制选中的 PDF）；「扫描件」放<strong>盖章扫描版</strong>（图像 PDF）。位置放反会导致结果完全异常。</span>
        </div>
      </div>

      <div className="space-y-4">
        <div className="card p-4">
          <label className="label">任务标题（可选）</label>
          <input
            className="input"
            placeholder="例如：江苏中广核 V2.0 采购合同 - 2026"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-[1fr_auto_1fr] gap-3 items-stretch">
          <DropZone label="① 原件 PDF（电子版）" hint="文字可选可复制" file={orig} onChange={setOrig} />
          <div className="flex items-center">
            <button
              onClick={() => { const a = orig; setOrig(scan); setScan(a); }}
              className="btn-secondary !p-2"
              title="交换两侧文件"
              disabled={!orig && !scan}
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>
          <DropZone label="② 扫描件 PDF（盖章版）" hint="盖章后扫描的图像 PDF" file={scan} onChange={setScan} />
        </div>

        <div className="card p-4">
          <button onClick={() => setShowAdvanced((v) => !v)} className="text-sm text-gray-600 inline-flex items-center gap-1">
            <Settings className="w-3.5 h-3.5" /> 高级设置
            <span className="text-gray-400">{showAdvanced ? "▲" : "▼"}</span>
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
          <button onClick={submit} className="btn-primary" disabled={m.isPending || !orig || !scan}>
            <Upload className="w-3.5 h-3.5" />
            {m.isPending ? "上传中..." : "开始对比"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DropZone({
  label, hint, file, onChange,
}: {
  label: string;
  hint: string;
  file: File | null;
  onChange: (f: File | null) => void;
}) {
  const [drag, setDrag] = useState(false);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f && f.type === "application/pdf") onChange(f);
    else toast.error("请上传 PDF 文件");
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
          <div className="text-sm text-gray-600">拖拽或点击选择 PDF</div>
          <div className="text-xs text-gray-400 mt-1">{hint}</div>
          <input
            type="file" className="hidden" accept="application/pdf"
            onChange={(e) => onChange(e.target.files?.[0] ?? null)}
          />
        </label>
      )}
    </div>
  );
}
