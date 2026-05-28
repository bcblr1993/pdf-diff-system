/**
 * 自绘 Logo Mark：两个错位重叠的矩形（暗示两份文档对比），
 * 配 Fraunces 衬线 wordmark。完全 SVG + CSS，无图片依赖。
 */
export function LogoMark({ size = 24, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Diff 文档审核"
    >
      {/* 后文档 */}
      <rect
        x="7"
        y="6"
        width="18"
        height="22"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.5"
        fill="none"
        opacity="0.4"
      />
      {/* 前文档（错位）*/}
      <rect
        x="4"
        y="3"
        width="18"
        height="22"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.5"
        fill="var(--bg)"
      />
      {/* 文档线条（差异感）*/}
      <line x1="8" y1="9" x2="18" y2="9" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
      <line x1="8" y1="13" x2="15" y2="13" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
      {/* 差异标记圆点 */}
      <circle cx="20" cy="13" r="1.4" fill="var(--critical)" />
      <line x1="8" y1="17" x2="17" y2="17" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
      <line x1="8" y1="21" x2="13" y2="21" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <div className={`inline-flex items-baseline gap-2 ${className}`}>
      <span
        className="font-display font-semibold text-[1.05rem] leading-none"
        style={{ fontVariationSettings: '"opsz" 14, "SOFT" 30' }}
      >
        Diff
      </span>
      <span className="text-[10px] tracking-[0.18em] uppercase text-fg-muted leading-none">
        审核工作台
      </span>
    </div>
  );
}
