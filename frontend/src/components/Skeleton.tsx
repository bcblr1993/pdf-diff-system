/**
 * 骨架屏组件。用 CSS class .skeleton（在 index.css 定义 shimmer 动画）。
 */
interface Props {
  className?: string;
  /** 圆形头像 / 圆形点 */
  circle?: boolean;
}

export function Skeleton({ className = "", circle }: Props) {
  return (
    <div
      className={`skeleton ${circle ? "rounded-full" : ""} ${className}`}
      aria-hidden
    />
  );
}

/** 一组任务卡片骨架（列表 loading 态用）*/
export function ComparisonCardSkeleton() {
  return (
    <div className="card p-4 flex items-center gap-4">
      <Skeleton className="w-6 h-6 rounded" />
      <div className="flex-1 space-y-2.5">
        <Skeleton className="h-3.5 w-3/5" />
        <Skeleton className="h-3 w-2/5" />
      </div>
      <Skeleton className="h-5 w-16 rounded-md" />
      <Skeleton className="h-8 w-24 rounded" />
    </div>
  );
}

/** 一行表格骨架 */
export function RowSkeleton({ cols = 5 }: { cols?: number }) {
  return (
    <div className="grid gap-3 px-4 py-3 border-b border-border" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={i} className="h-3" />
      ))}
    </div>
  );
}
