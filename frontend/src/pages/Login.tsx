import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast, Toaster } from "sonner";
import { useAuthStore } from "@/stores/auth";
import { login, getMe } from "@/api/endpoints";
import { errMsg } from "@/api/client";

export default function Login() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const setToken = useAuthStore((s) => s.setToken);
  const setUser = useAuthStore((s) => s.setUser);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [loading, setLoading] = useState(false);

  const msg = params.get("msg");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const { access_token } = await login(username, password);
      setToken(access_token);
      const me = await getMe();
      setUser(me);
      toast.success(`欢迎回来，${me.display_name}`);
      navigate("/");
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50">
      <Toaster richColors position="top-center" />
      <div className="card w-[400px] p-8">
        <div className="text-center mb-6">
          <div className="text-2xl font-bold text-gray-900">PDF 差异对比系统</div>
          <div className="text-sm text-gray-500 mt-1">合同审核工作台</div>
        </div>
        {msg && (
          <div className="mb-4 p-2 bg-amber-50 border border-amber-200 text-amber-800 rounded text-sm">
            {msg}
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">用户名</label>
            <input
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
            />
          </div>
          <div>
            <label className="label">密码</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn-primary w-full justify-center" disabled={loading}>
            {loading ? "登录中..." : "登录"}
          </button>
        </form>
      </div>
    </div>
  );
}
