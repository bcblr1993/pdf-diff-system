import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast, Toaster } from "sonner";
import { ArrowRight, KeyRound, Loader2 } from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import { login, getMe } from "@/api/endpoints";
import { errMsg } from "@/api/client";
import { LogoMark } from "@/components/Logo";

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
    <div className="min-h-screen flex items-center justify-center p-6 bg-bg">
      <Toaster richColors position="top-center" />

      <div className="w-full max-w-[400px] anim-fade-in">
        {/* 品牌 */}
        <div className="flex items-center gap-3 mb-10 justify-center">
          <LogoMark size={28} />
          <div>
            <div
              className="font-display text-2xl font-semibold leading-none"
              style={{ fontVariationSettings: '"opsz" 24, "SOFT" 40' }}
            >
              Diff
            </div>
            <div className="text-[10px] tracking-[0.22em] uppercase mt-1.5 text-fg-muted">
              审核工作台
            </div>
          </div>
        </div>

        {/* 表单卡片 */}
        <div className="card p-8">
          <div className="mb-6">
            <div className="text-xs tracking-[0.18em] uppercase text-fg-muted mb-2">
              登录
            </div>
            <h2
              className="font-display text-[1.75rem] leading-tight tracking-tightest"
              style={{ fontVariationSettings: '"opsz" 36, "SOFT" 40' }}
            >
              欢迎回来
            </h2>
            <p className="text-sm text-fg-muted mt-1.5">
              使用账号登录，开始审核今天的合同。
            </p>
          </div>

          {msg && (
            <div
              className="mb-5 p-3 rounded-md text-[13px] border anim-slide-in"
              style={{
                background: "#fef3c7",
                color: "#92400e",
                borderColor: "#fde68a",
              }}
            >
              {msg}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">账号</label>
              <input
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="用户名"
                autoFocus
                required
              />
            </div>
            <div>
              <label className="label">密码</label>
              <input
                className="input font-mono"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
            <button
              type="submit"
              className="btn-primary w-full !h-10 mt-2"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> 验证中
                </>
              ) : (
                <>
                  登录 <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* 默认账号提示 */}
        <div
          className="mt-4 p-3 rounded-md border flex items-start gap-2.5"
          style={{ background: "var(--bg-subtle)", borderColor: "var(--border)" }}
        >
          <KeyRound className="w-3.5 h-3.5 mt-0.5 text-fg-muted shrink-0" />
          <div className="text-[12px] leading-relaxed text-fg-muted">
            首次部署默认账号 <code className="font-mono text-fg">admin / admin123</code>，
            登录后请在「集成」页改密码，并妥善保管。
          </div>
        </div>

        <div className="mt-8 text-center text-[11px] text-fg-subtle">
          © {new Date().getFullYear()} Diff 审核工作台 · 内网部署
        </div>
      </div>
    </div>
  );
}
