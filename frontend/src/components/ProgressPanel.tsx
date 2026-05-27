/**
 * 任务进度面板（处理中显示）。包含 WebSocket 实时进度。
 */
import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import { PHASE_LABEL } from "@/lib/utils";

interface Props {
  comparisonId: number;
  initialPhase: string;
  initialPct: number;
  onDone: () => void;
}

export default function ProgressPanel({ comparisonId, initialPhase, initialPct, onDone }: Props) {
  const token = useAuthStore((s) => s.token);
  const [phase, setPhase] = useState(initialPhase);
  const [pct, setPct] = useState(initialPct);
  const [message, setMessage] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${location.host}/ws/comparisons/${comparisonId}/progress?token=${token}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d.phase) setPhase(d.phase);
        if (typeof d.pct === "number") setPct(d.pct);
        if (d.message) setMessage(d.message);
        if (d.phase === "done") {
          setTimeout(onDone, 500);
        } else if (d.phase === "failed") {
          setTimeout(onDone, 1500);
        }
      } catch {}
    };
    ws.onerror = () => {/* 忽略，靠轮询兜底 */};
    return () => { try { ws.close(); } catch {} };
  }, [comparisonId, token]);

  return (
    <div className="card p-6 max-w-2xl mx-auto mt-12">
      <div className="flex items-center gap-3 mb-4">
        <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
        <div className="font-medium">正在处理对比任务 #{comparisonId}</div>
      </div>
      <div className="text-sm text-gray-600 mb-2">
        当前阶段：<span className="font-medium text-gray-900">{PHASE_LABEL[phase] || phase}</span>
        {message && <span className="text-gray-500 ml-2">— {message}</span>}
      </div>
      <div className="w-full h-2 bg-gray-100 rounded overflow-hidden">
        <div
          className="h-2 bg-blue-600 transition-all duration-500"
          style={{ width: `${Math.max(2, pct)}%` }}
        />
      </div>
      <div className="text-right text-xs text-gray-500 mt-1">{pct}%</div>
      <div className="mt-6 text-xs text-gray-500">
        首次处理一份新扫描件需要 30-60 秒做 OCR。后续相同文件秒级返回。
      </div>
    </div>
  );
}
