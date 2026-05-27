// 与后端 schema 对齐的 TypeScript 类型

export type ComparisonStatus = "pending" | "running" | "done" | "failed";
export type ReviewStatus = "not_started" | "in_review" | "completed";
export type UserRole = "admin" | "reviewer";
export type DiffCategory =
  | "replace"
  | "delete"
  | "insert"
  | "handwritten"
  | "stamp_covered"
  | "moved";
export type DiffSeverity = "critical" | "normal" | "info";
export type ReviewAction = "confirmed" | "ignored" | null;

export interface User {
  id: number;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface FileBrief {
  id: number;
  sha1: string;
  original_name: string;
  page_count: number | null;
  size_bytes: number;
}

export interface ComparisonSummary {
  total: number;
  real: number;
  critical: number;
  replace: number;
  delete: number;
  insert: number;
  handwritten: number;
  stamp_covered: number;
  moved: number;
  footer: number;
}

export interface ComparisonBrief {
  id: number;
  title: string;
  created_by: number | null;
  status: ComparisonStatus;
  review_status: ReviewStatus;
  progress_pct: number;
  progress_phase: string;
  summary_json: ComparisonSummary | null;
  created_at: string;
  completed_at: string | null;
}

export interface ComparisonDetail extends ComparisonBrief {
  orig_file: FileBrief;
  scan_file: FileBrief;
  settings_json: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  review_completed_by: number | null;
  review_completed_at: string | null;
}

export interface Diff {
  id: number;
  seq_no: number;
  category: DiffCategory;
  severity: DiffSeverity;
  orig_page: number;
  scan_page: number;
  orig_text: string;
  scan_text: string;
  orig_bbox: [number, number, number, number] | null;
  scan_bbox: [number, number, number, number] | null;
  context: string;
  is_footer: boolean;
  review_action: ReviewAction;
  review_note: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ─── 批量任务 ───────────────────────────────────────
export type BatchStatus = "pending" | "running" | "done" | "partial" | "failed";

export interface BatchBrief {
  id: number;
  title: string;
  created_by: number | null;
  status: BatchStatus;
  total: number;
  completed: number;
  failed: number;
  created_at: string;
  completed_at: string | null;
}

export interface BatchDetail extends BatchBrief {
  orig_file: FileBrief;
  comparisons: ComparisonBrief[];
}

export interface ProgressEvent {
  phase: string;
  pct: number;
  status?: string;
  message?: string;
}
