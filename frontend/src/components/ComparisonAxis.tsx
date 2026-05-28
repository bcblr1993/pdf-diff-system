import { useEffect, useState } from "react";

interface Props {
  /** 滚动容器 ref，用于读 scrollTop / scrollHeight，画进度小芯片 */
  origRef: React.RefObject<HTMLDivElement | null>;
  scanRef: React.RefObject<HTMLDivElement | null>;
}

/**
 * 中间对比轴：
 * - 1 px 主分隔线
 * - 顶部小标签「原件 ↔ 对方」
 * - 中部一条「位置指示器」（垂直进度条），随滚动同步移动
 *   两侧 ratio 不一致时会显示两条芯片，提示当前有错位（同步滚动会让它们贴合）
 */
export default function ComparisonAxis({ origRef, scanRef }: Props) {
  const [origPct, setOrigPct] = useState(0);
  const [scanPct, setScanPct] = useState(0);

  useEffect(() => {
    function read() {
      const o = origRef.current;
      const s = scanRef.current;
      if (o) {
        const max = Math.max(o.scrollHeight - o.clientHeight, 1);
        setOrigPct(Math.min(1, Math.max(0, o.scrollTop / max)));
      }
      if (s) {
        const max = Math.max(s.scrollHeight - s.clientHeight, 1);
        setScanPct(Math.min(1, Math.max(0, s.scrollTop / max)));
      }
    }
    const id = setInterval(read, 100);
    read();
    return () => clearInterval(id);
  }, [origRef, scanRef]);

  return (
    <div className="relative h-full select-none flex flex-col items-center bg-bg-subtle border-x border-border">
      {/* 顶部标签 */}
      <div className="pt-3 pb-1 text-[9px] tracking-[0.18em] uppercase text-fg-subtle leading-none">
        Diff
      </div>
      <div className="text-[9px] text-fg-subtle leading-none rotate-180" style={{ writingMode: "vertical-rl" }}>
        ↔
      </div>

      {/* 主轴 */}
      <div className="flex-1 w-full relative">
        {/* 中线 */}
        <div className="absolute left-1/2 -translate-x-px top-0 bottom-0 w-px bg-border" />

        {/* 刻度（每 10% 一个小记号） */}
        {Array.from({ length: 11 }).map((_, i) => (
          <div
            key={i}
            className="absolute left-1/2 -translate-x-1/2 w-[5px] h-px bg-border"
            style={{ top: `${i * 10}%` }}
          />
        ))}

        {/* 原件位置 chip（左侧三角） */}
        <PositionChip
          pct={origPct}
          side="left"
          color="var(--accent)"
          label="原"
        />
        {/* 扫描件位置 chip（右侧三角） */}
        <PositionChip
          pct={scanPct}
          side="right"
          color="var(--critical)"
          label="扫"
        />
      </div>

      {/* 底部 */}
      <div className="pb-2 text-[9px] tabular-nums text-fg-subtle leading-none">
        {Math.round(((origPct + scanPct) / 2) * 100)}%
      </div>
    </div>
  );
}

function PositionChip({
  pct, side, color, label,
}: { pct: number; side: "left" | "right"; color: string; label: string }) {
  return (
    <div
      className="absolute -translate-y-1/2 transition-[top] duration-150 ease-out flex items-center"
      style={{
        top: `${pct * 100}%`,
        [side]: 0,
        flexDirection: side === "left" ? "row" : "row-reverse",
      }}
    >
      {/* 小三角 */}
      <div
        className="w-0 h-0"
        style={{
          borderTop: "5px solid transparent",
          borderBottom: "5px solid transparent",
          ...(side === "left"
            ? { borderRight: `6px solid ${color}` }
            : { borderLeft: `6px solid ${color}` }),
        }}
      />
      {/* 标签 */}
      <span
        className="text-[9px] font-mono px-1 rounded-sm text-white"
        style={{ background: color }}
      >
        {label}
      </span>
    </div>
  );
}
