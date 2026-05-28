/**
 * 主题：当前只支持浅色（深色对比度不理想，已下线 UI 切换）。
 * 保留文件以备日后开关再启用，强制移除 .dark class + 清掉历史本地存储。
 */
if (typeof window !== "undefined") {
  document.documentElement.classList.remove("dark");
  try {
    localStorage.removeItem("pdfdiff-theme");
  } catch {
    /* noop */
  }
}

export {};
