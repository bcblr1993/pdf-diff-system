/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // 直接映射到 CSS 变量，所有 token 可在 tailwind 中用
        bg: {
          DEFAULT: "var(--bg)",
          elevated: "var(--bg-elevated)",
          subtle: "var(--bg-subtle)",
          tint: "var(--bg-tint)",
        },
        fg: {
          DEFAULT: "var(--fg)",
          muted: "var(--fg-muted)",
          subtle: "var(--fg-subtle)",
        },
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          soft: "var(--accent-soft)",
          "soft-fg": "var(--accent-soft-fg)",
        },
        critical: {
          DEFAULT: "var(--critical)",
          soft: "var(--critical-soft)",
          "soft-fg": "var(--critical-soft-fg)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          soft: "var(--warning-soft)",
          "soft-fg": "var(--warning-soft-fg)",
        },
        info: {
          DEFAULT: "var(--info)",
          soft: "var(--info-soft)",
          "soft-fg": "var(--info-soft-fg)",
        },
        success: {
          DEFAULT: "var(--success)",
          soft: "var(--success-soft)",
          "soft-fg": "var(--success-soft-fg)",
        },
      },
      fontFamily: {
        display: ['"Fraunces Variable"', '"Songti SC"', '"STSong"', "serif"],
        sans: ['"Geist Sans"', "-apple-system", '"PingFang SC"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', '"SF Mono"', '"Menlo"', "ui-monospace", "monospace"],
      },
      letterSpacing: {
        tightest: "-0.025em",
        edit: "-0.011em",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      transitionTimingFunction: {
        ease: "cubic-bezier(0.22, 1, 0.36, 1)",
        "ease-out": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      animation: {
        "fade-in": "fade-in 0.28s cubic-bezier(0.16, 1, 0.3, 1) both",
        "slide-in": "slide-in 0.32s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
    },
  },
  plugins: [],
};
