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
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr] bg-bg">
      <Toaster richColors position="top-center" />

      {/* 左侧装饰面板 */}
      <aside className="hidden lg:flex relative overflow-hidden flex-col justify-between p-12 noise-bg"
             style={{ background: "var(--fg)", color: "var(--bg)" }}>
        {/* 装饰：浮动文档 */}
        <DecorativeDocs />

        {/* 品牌 */}
        <div className="relative z-10 flex items-center gap-3" style={{ color: "var(--bg)" }}>
          <LogoMark size={32} />
          <div>
            <div className="font-display text-2xl font-semibold leading-none"
                 style={{ fontVariationSettings: '"opsz" 24, "SOFT" 50' }}>
              Diff
            </div>
            <div className="text-[10px] tracking-[0.22em] uppercase mt-1.5 opacity-60">
              审核工作台
            </div>
          </div>
        </div>

        {/* 大字标语 */}
        <div className="relative z-10 max-w-md">
          <h1 className="font-display text-[3.2rem] leading-[1.05] font-light tracking-tightest"
              style={{ fontVariationSettings: '"opsz" 144, "SOFT" 100, "WONK" 1' }}>
            把每一处<br />
            <span className="italic font-normal" style={{ color: "var(--accent)" }}>不同</span>
            <span className="opacity-50">{" "}</span>
            <br />都看得见
          </h1>
          <p className="mt-7 text-[13px] leading-[1.7] opacity-60 max-w-sm">
            PDF、Word 双轨字符流对比。原件直抽 + 扫描件 OCR + 章遮挡识别 + 块位移配对，
            自动产出可审核的差异清单。
          </p>
        </div>

        {/* 底部小字 */}
        <div className="relative z-10 flex items-center justify-between text-[11px] opacity-40 tabular-nums">
          <span>v1.0 · {new Date().getFullYear()}</span>
          <span className="font-mono">localhost:8080</span>
        </div>
      </aside>

      {/* 右侧表单 */}
      <main className="flex flex-col items-center justify-center p-6 sm:p-12 relative">
        {/* 手机端 logo */}
        <div className="lg:hidden absolute top-6 left-6 flex items-center gap-2">
          <LogoMark size={20} />
          <span className="font-display font-semibold text-lg leading-none">Diff</span>
        </div>

        <div className="w-full max-w-[360px] anim-fade-in">
          <div className="mb-10">
            <div className="text-xs tracking-[0.18em] uppercase text-fg-muted mb-2.5">
              登录
            </div>
            <h2 className="font-display text-[2rem] leading-tight tracking-tightest"
                style={{ fontVariationSettings: '"opsz" 36, "SOFT" 40' }}>
              欢迎回来
            </h2>
            <p className="text-sm text-fg-muted mt-2">
              使用账号登录，开始审核今天的合同。
            </p>
          </div>

          {msg && (
            <div className="mb-5 p-3 rounded-md text-[13px] border anim-slide-in"
                 style={{
                   background: "var(--warning-soft)",
                   color: "var(--warning-soft-fg)",
                   borderColor: "color-mix(in oklch, var(--warning) 25%, transparent)",
                 }}>
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
              <div className="flex items-center justify-between mb-1.5">
                <label className="label !mb-0">密码</label>
              </div>
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

          {/* 默认账号提示 */}
          <div className="mt-8 p-3.5 rounded-md border border-border bg-bg-subtle/40 flex items-start gap-2.5">
            <KeyRound className="w-3.5 h-3.5 mt-0.5 text-fg-muted shrink-0" />
            <div className="text-[12px] leading-relaxed text-fg-muted">
              首次部署默认账号 <code className="font-mono text-fg">admin / admin123</code>，
              登录后请在「集成」页改密码，并妥善保管。
            </div>
          </div>
        </div>

        <div className="absolute bottom-6 left-0 right-0 text-center text-[11px] text-fg-subtle">
          © {new Date().getFullYear()} Diff 审核工作台 · 内网部署
        </div>
      </main>
    </div>
  );
}

/** 左侧装饰：浮动文档（subtle）+ 网格线 */
function DecorativeDocs() {
  return (
    <>
      {/* 网格底纹 */}
      <div
        className="absolute inset-0 opacity-[0.06] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(to right, currentColor 1px, transparent 1px), linear-gradient(to bottom, currentColor 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />
      {/* 浮动文档 1 */}
      <div
        className="absolute top-[18%] right-[18%] w-44 h-56 rounded border opacity-[0.18] -rotate-6"
        style={{
          borderColor: "currentColor",
          background:
            "repeating-linear-gradient(0deg, transparent 0, transparent 12px, currentColor 12px, currentColor 13px)",
          backgroundClip: "padding-box",
        }}
      />
      {/* 浮动文档 2 */}
      <div
        className="absolute top-[22%] right-[26%] w-44 h-56 rounded border opacity-[0.28] rotate-3"
        style={{
          borderColor: "currentColor",
          background:
            "repeating-linear-gradient(0deg, transparent 0, transparent 12px, currentColor 12px, currentColor 13px)",
        }}
      />
      {/* 差异色斑点 */}
      <div
        className="absolute top-[34%] right-[34%] w-12 h-2.5 rounded-sm opacity-90"
        style={{ background: "var(--accent)" }}
      />
      <div
        className="absolute top-[40%] right-[28%] w-8 h-2.5 rounded-sm opacity-90"
        style={{ background: "var(--critical)" }}
      />
      <div
        className="absolute top-[46%] right-[40%] w-6 h-2.5 rounded-sm opacity-80"
        style={{ background: "var(--warning)" }}
      />

      {/* 底部光晕 */}
      <div
        className="absolute -bottom-32 -left-32 w-[480px] h-[480px] rounded-full opacity-20 pointer-events-none blur-3xl"
        style={{ background: "var(--accent)" }}
      />
    </>
  );
}
