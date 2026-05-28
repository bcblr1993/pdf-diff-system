import type { ReactNode } from "react";

interface Props {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  /** 极简线条插画，传 SVG 元素 */
  illustration?: ReactNode;
}

/**
 * 通用空状态：极简线稿插画 + 描述 + 操作。
 * 不用第三方插画，纯 SVG 几何，保持风格一致。
 */
export function EmptyState({ icon, title, description, action, illustration }: Props) {
  return (
    <div className="text-center py-16 px-6 anim-fade-in">
      <div className="inline-block mb-5 text-fg-muted">
        {illustration ?? <DefaultIllustration />}
      </div>
      {icon && <div className="mb-3 inline-flex text-fg-muted">{icon}</div>}
      <h3 className="font-display text-[1.25rem] tracking-tightest text-fg"
          style={{ fontVariationSettings: '"opsz" 24, "SOFT" 40' }}>
        {title}
      </h3>
      {description && (
        <p className="mt-2 text-[13px] text-fg-muted max-w-xs mx-auto leading-relaxed">
          {description}
        </p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

function DefaultIllustration() {
  return (
    <svg width="120" height="80" viewBox="0 0 120 80" fill="none">
      {/* 两份重叠的文档 */}
      <rect
        x="22"
        y="14"
        width="56"
        height="52"
        rx="3"
        stroke="currentColor"
        strokeWidth="1.3"
        opacity="0.35"
      />
      <rect
        x="34"
        y="22"
        width="56"
        height="52"
        rx="3"
        stroke="currentColor"
        strokeWidth="1.3"
        fill="var(--bg-elevated)"
      />
      <line x1="40" y1="34" x2="78" y2="34" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
      <line x1="40" y1="42" x2="70" y2="42" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
      <line x1="40" y1="50" x2="80" y2="50" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
      <line x1="40" y1="58" x2="62" y2="58" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
      {/* 差异色点 */}
      <circle cx="82" cy="42" r="2" fill="var(--accent)" />
    </svg>
  );
}
