import { format, formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale/zh-CN";
import type { DiffCategory, DiffSeverity } from "@/types";

export function fmtTime(s: string | null | undefined) {
  if (!s) return "—";
  try { return format(new Date(s), "yyyy-MM-dd HH:mm"); } catch { return s; }
}

export function fmtAgo(s: string | null | undefined) {
  if (!s) return "—";
  try {
    return formatDistanceToNow(new Date(s), { locale: zhCN, addSuffix: true });
  } catch { return s; }
}

export function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export const CATEGORY_LABEL: Record<DiffCategory, string> = {
  replace: "修改",
  delete: "删除",
  insert: "新增",
  handwritten: "手写填空",
  stamp_covered: "章遮挡",
  moved: "位置移动",
};

export const SEVERITY_LABEL: Record<DiffSeverity, string> = {
  critical: "关键",
  normal: "普通",
  info: "信息",
};

export const STATUS_LABEL = {
  pending: "等待中",
  running: "处理中",
  done: "已完成",
  failed: "失败",
};

export const REVIEW_STATUS_LABEL = {
  not_started: "未审核",
  in_review: "审核中",
  completed: "审核完成",
};

export const PHASE_LABEL: Record<string, string> = {
  starting: "启动中",
  extracting: "抽取原件",
  ocr: "OCR 识别",
  stamp: "检测红章",
  diffing: "差异比对",
  saving: "保存结果",
  done: "完成",
  failed: "失败",
};
