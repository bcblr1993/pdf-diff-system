import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { LogOut, Plus, Layers, Key, ChevronDown, Palette as PaletteIcon, Check } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useAuthStore } from "@/stores/auth";
import { usePaletteStore, PALETTE_META, type Palette } from "@/stores/palette";
import { LogoMark, Wordmark } from "@/components/Logo";

export default function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const isDetail = /^\/(comparisons|batches)\/\d+/.test(location.pathname);

  return (
    <div className="min-h-screen flex flex-col bg-bg text-fg">
      <Toaster
        richColors
        position="top-center"
        toastOptions={{
          style: {
            background: "var(--bg-elevated)",
            color: "var(--fg)",
            border: "1px solid var(--border)",
            fontFamily: "var(--font-sans)",
          },
        }}
      />
      <Header isDetail={isDetail} user={user} onLogout={handleLogout} />
      <main className="flex-1 anim-fade-in">
        <Outlet />
      </main>
    </div>
  );
}

function Header({ isDetail, user, onLogout }: { isDetail: boolean; user: any; onLogout: () => void }) {
  const location = useLocation();
  return (
    <header
      className="sticky top-0 z-30 border-b border-border bg-bg-elevated/85 backdrop-blur-md"
      style={{ borderColor: "var(--border)" }}
    >
      <div className={`mx-auto px-5 ${isDetail ? "max-w-none" : "max-w-[88rem]"}`}>
        <div className="h-[52px] flex items-center gap-6">
          {/* 品牌 */}
          <Link
            to="/"
            className="flex items-center gap-2.5 text-fg hover:opacity-80 transition-opacity"
            style={{ color: "var(--fg)" }}
          >
            <LogoMark size={22} />
            <Wordmark className="hidden sm:inline-flex" />
          </Link>

          <div className="h-5 w-px bg-border" />

          {/* 主导航 */}
          <nav className="flex-1 flex items-center gap-0.5">
            <NavLink to="/" active={location.pathname === "/" || location.pathname.startsWith("/comparisons")}>
              任务列表
            </NavLink>
            <NavLink to="/batches" active={location.pathname.startsWith("/batches")} icon={<Layers className="w-3.5 h-3.5" />}>
              批量任务
            </NavLink>
            <NavLink to="/new" active={location.pathname === "/new"} icon={<Plus className="w-3.5 h-3.5" />}>
              新建对比
            </NavLink>
            {user?.role === "admin" && (
              <NavLink
                to="/integrations"
                active={location.pathname.startsWith("/integrations")}
                icon={<Key className="w-3.5 h-3.5" />}
              >
                集成
              </NavLink>
            )}
          </nav>

          {/* 右侧 */}
          <div className="flex items-center gap-1">
            <PaletteMenu />
            {user && <UserMenu user={user} onLogout={onLogout} />}
          </div>
        </div>
      </div>
    </header>
  );
}

function NavLink({
  to, active, icon, children,
}: { to: string; active: boolean; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className="relative inline-flex items-center gap-1.5 px-3 h-[52px] text-[13px] font-medium transition-colors group"
      style={{ color: active ? "var(--fg)" : "var(--fg-muted)" }}
    >
      {icon}
      {children}
      <span
        className="absolute left-2 right-2 -bottom-px h-px transition-all"
        style={{
          background: active ? "var(--fg)" : "transparent",
          opacity: active ? 1 : 0,
        }}
      />
    </Link>
  );
}

function PaletteMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const palette = usePaletteStore((s) => s.palette);
  const setPalette = usePaletteStore((s) => s.setPalette);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="btn btn-ghost !h-9 !w-9 !p-0"
        title="配色风格"
        aria-label="配色风格"
      >
        <PaletteIcon className="w-4 h-4" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 w-64 card !rounded-lg overflow-hidden anim-slide-in z-40">
          <div className="px-3 py-2 border-b border-border">
            <div className="text-[11px] tracking-[0.16em] uppercase text-fg-muted">配色风格</div>
          </div>
          {(Object.keys(PALETTE_META) as Palette[]).map((p) => {
            const m = PALETTE_META[p];
            const active = palette === p;
            return (
              <button
                key={p}
                onClick={() => { setPalette(p); setOpen(false); }}
                className="w-full text-left px-3 py-2.5 flex items-center gap-3 hover:bg-bg-subtle transition-colors"
              >
                <span
                  className="w-7 h-7 rounded-full shrink-0 border"
                  style={{
                    background: m.sample,
                    borderColor: "color-mix(in oklch, black 12%, transparent)",
                  }}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium leading-tight">{m.label}</div>
                  <div className="text-[11px] text-fg-muted mt-0.5">{m.desc}</div>
                </div>
                {active && <Check className="w-3.5 h-3.5 text-accent shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function UserMenu({ user, onLogout }: { user: any; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  const initial = (user.display_name || user.username || "?").trim().slice(0, 1).toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 h-9 pl-1.5 pr-2.5 rounded-md transition-colors hover:bg-bg-subtle"
      >
        <div
          className="w-6 h-6 rounded-full grid place-items-center text-[11px] font-semibold text-white"
          style={{ background: "var(--fg)" }}
        >
          {initial}
        </div>
        <span className="text-[13px] hidden md:block">{user.display_name || user.username}</span>
        <ChevronDown className="w-3.5 h-3.5 text-fg-muted" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 w-56 card !rounded-lg overflow-hidden anim-slide-in">
          <div className="px-3 py-2.5 border-b border-border">
            <div className="text-[13px] font-medium">{user.display_name || user.username}</div>
            <div className="text-[11px] text-fg-muted mt-0.5 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />
              {user.role === "admin" ? "管理员" : "审核员"} · {user.username}
            </div>
          </div>
          <button
            onClick={onLogout}
            className="w-full text-left px-3 py-2 text-[13px] flex items-center gap-2 hover:bg-bg-subtle transition-colors text-fg-muted"
          >
            <LogOut className="w-3.5 h-3.5" /> 登出
          </button>
        </div>
      )}
    </div>
  );
}
