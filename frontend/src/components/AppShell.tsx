import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { LogOut, FileSearch, Plus, Layers } from "lucide-react";
import { useAuthStore } from "@/stores/auth";

export default function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const isDetail = /^\/comparisons\/\d+/.test(location.pathname);

  return (
    <div className="min-h-screen flex flex-col">
      <Toaster richColors position="top-center" />
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
        <div className={`mx-auto px-4 ${isDetail ? "max-w-none" : "max-w-7xl"}`}>
          <div className="h-14 flex items-center gap-4">
            <Link to="/" className="flex items-center gap-2 font-semibold text-gray-900">
              <FileSearch className="w-5 h-5 text-blue-600" />
              <span>PDF 差异对比</span>
            </Link>
            <nav className="flex-1 flex gap-1 ml-6">
              <Link to="/" className={`px-3 py-1.5 rounded text-sm hover:bg-gray-100 ${
                location.pathname === "/" || location.pathname.startsWith("/comparisons")
                  ? "text-blue-600 font-medium" : "text-gray-700"
              }`}>
                任务列表
              </Link>
              <Link to="/batches" className={`px-3 py-1.5 rounded text-sm hover:bg-gray-100 inline-flex items-center gap-1 ${
                location.pathname.startsWith("/batches") ? "text-blue-600 font-medium" : "text-gray-700"
              }`}>
                <Layers className="w-3.5 h-3.5" /> 批量任务
              </Link>
              <Link to="/new" className="px-3 py-1.5 rounded text-sm text-gray-700 hover:bg-gray-100 inline-flex items-center gap-1">
                <Plus className="w-3.5 h-3.5" /> 新建
              </Link>
            </nav>
            {user && (
              <div className="flex items-center gap-3 text-sm">
                <span className="text-gray-600">
                  {user.display_name}
                  <span className="ml-1 text-xs text-gray-400">({user.role === "admin" ? "管理员" : "审核员"})</span>
                </span>
                <button onClick={handleLogout} className="btn-secondary !py-1 !px-2">
                  <LogOut className="w-3.5 h-3.5" /> 登出
                </button>
              </div>
            )}
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
