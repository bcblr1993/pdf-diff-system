import { api } from "./client";
import type {
  BatchBrief,
  BatchDetail,
  BatchStatus,
  ComparisonBrief,
  ComparisonDetail,
  Diff,
  DiffCategory,
  DiffSeverity,
  Page,
  ReviewAction,
  ReviewStatus,
  ComparisonStatus,
  User,
} from "@/types";

// ─── Auth ───────────────────────────────────────────
export async function login(username: string, password: string) {
  const { data } = await api.post<{ access_token: string; token_type: string }>(
    "/api/auth/login",
    { username, password }
  );
  return data;
}

export async function getMe() {
  const { data } = await api.get<User>("/api/auth/me");
  return data;
}

// ─── Comparisons ────────────────────────────────────
export async function listComparisons(params: {
  page?: number;
  page_size?: number;
  status?: ComparisonStatus;
  review_status?: ReviewStatus;
  mine_only?: boolean;
}) {
  const { data } = await api.get<Page<ComparisonBrief>>("/api/comparisons", { params });
  return data;
}

export async function getComparison(id: number) {
  const { data } = await api.get<ComparisonDetail>(`/api/comparisons/${id}`);
  return data;
}

export async function createComparison(args: {
  title: string;
  orig: File;
  scan: File;
  dpi?: number;
}) {
  const fd = new FormData();
  fd.append("title", args.title);
  fd.append("orig", args.orig);
  fd.append("scan", args.scan);
  if (args.dpi) fd.append("dpi", String(args.dpi));
  const { data } = await api.post<{ id: number; status: ComparisonStatus }>(
    "/api/comparisons",
    fd,
    { headers: { "Content-Type": "multipart/form-data" }, timeout: 5 * 60_000 }
  );
  return data;
}

export async function deleteComparison(id: number) {
  await api.delete(`/api/comparisons/${id}`);
}

// ─── Diffs ──────────────────────────────────────────
export async function listDiffs(
  cid: number,
  params: {
    page?: number;
    page_size?: number;
    category?: DiffCategory[];
    severity?: DiffSeverity[];
    reviewed?: boolean;
    include_noise?: boolean;
  } = {}
) {
  const { data } = await api.get<Page<Diff>>(`/api/comparisons/${cid}/diffs`, {
    params,
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function updateDiffReview(diffId: number, body: {
  review_action: ReviewAction | null;
  review_note?: string | null;
}) {
  const { data } = await api.patch<Diff>(`/api/diffs/${diffId}`, body);
  return data;
}

export async function completeReview(cid: number) {
  const { data } = await api.post<{ message: string }>(
    `/api/comparisons/${cid}/review/complete`
  );
  return data;
}

// ─── 文件 URL ────────────────────────────────────────
export function pdfUrl(cid: number, side: "orig" | "scan") {
  const token = (window as any).__token || "";
  return `/api/comparisons/${cid}/${side}.pdf${token ? `?_=${Date.now()}` : ""}`;
}

// ─── 批量任务 ────────────────────────────────────────
export async function listBatches(params: {
  page?: number;
  page_size?: number;
  status?: BatchStatus;
  mine_only?: boolean;
}) {
  const { data } = await api.get<Page<BatchBrief>>("/api/batches", { params });
  return data;
}

export async function getBatch(id: number) {
  const { data } = await api.get<BatchDetail>(`/api/batches/${id}`);
  return data;
}

export async function createBatch(args: {
  title: string;
  orig: File;
  scans: File[];
  dpi?: number;
}) {
  const fd = new FormData();
  fd.append("title", args.title);
  fd.append("orig", args.orig);
  for (const s of args.scans) fd.append("scans", s);
  if (args.dpi) fd.append("dpi", String(args.dpi));
  const { data } = await api.post<{ id: number; total: number; comparison_ids: number[] }>(
    "/api/batches", fd,
    { headers: { "Content-Type": "multipart/form-data" }, timeout: 10 * 60_000 }
  );
  return data;
}

export async function deleteBatch(id: number) {
  await api.delete(`/api/batches/${id}`);
}

// ─── 导出 ────────────────────────────────────────────
export type ExportFormat = "xlsx" | "html" | "pdf";

export async function downloadExport(cid: number, format: ExportFormat, opts: {
  include_noise?: boolean;
} = {}) {
  const params = format === "html" && opts.include_noise ? "?include_noise=true" : "";
  return _doDownload(`/api/comparisons/${cid}/export.${format}${params}`, `comparison-${cid}.${format}`);
}

export async function downloadBatchExport(bid: number) {
  return _doDownload(`/api/batches/${bid}/export.xlsx`, `batch-${bid}.xlsx`);
}

async function _doDownload(url: string, fallbackName: string) {
  const res = await api.get(url, {
    responseType: "blob",
    timeout: 120_000,
  });
  // 从 Content-Disposition 提取文件名
  const disp: string = res.headers["content-disposition"] || "";
  let filename = fallbackName;
  const m = disp.match(/filename\*=UTF-8''([^;]+)/);
  if (m) {
    try { filename = decodeURIComponent(m[1]); } catch { /* ignore */ }
  } else {
    const m2 = disp.match(/filename="?([^";]+)"?/);
    if (m2) filename = m2[1];
  }
  const blob = new Blob([res.data]);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return filename;
}
