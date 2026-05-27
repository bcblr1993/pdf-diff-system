import axios, { AxiosError } from "axios";
import { useAuthStore } from "@/stores/auth";

export const api = axios.create({
  baseURL: "/",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError<{ detail?: string }>) => {
    if (err.response?.status === 401) {
      const detail = err.response.data?.detail || "登录已过期";
      useAuthStore.getState().logout();
      // 不强行 reload，让路由守卫处理跳登录
      if (location.pathname !== "/login") {
        location.href = `/login?msg=${encodeURIComponent(detail)}`;
      }
    }
    return Promise.reject(err);
  }
);

export function errMsg(err: unknown): string {
  if (axios.isAxiosError(err)) {
    return err.response?.data?.detail || err.message || "请求失败";
  }
  return (err as Error)?.message || "未知错误";
}
