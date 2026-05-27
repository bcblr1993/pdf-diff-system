import { api } from "./client";
import type {
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
