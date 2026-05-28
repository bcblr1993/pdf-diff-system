import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Palette = "classic" | "editorial";

export const PALETTE_META: Record<Palette, { label: string; desc: string; sample: string }> = {
  classic: {
    label: "经典蓝",
    desc: "稳重熟悉，适合大多数审核场景",
    sample: "oklch(0.55 0.20 255)",
  },
  editorial: {
    label: "墨绿编辑",
    desc: "克制专业，编辑工作站风",
    sample: "oklch(0.42 0.075 165)",
  },
};

interface PaletteState {
  palette: Palette;
  setPalette: (p: Palette) => void;
}

function apply(p: Palette) {
  document.documentElement.dataset.palette = p;
}

export const usePaletteStore = create<PaletteState>()(
  persist(
    (set) => ({
      palette: "classic",
      setPalette: (p) => {
        apply(p);
        set({ palette: p });
      },
    }),
    {
      name: "pdfdiff-palette",
      onRehydrateStorage: () => (state) => {
        if (state) apply(state.palette);
      },
    }
  )
);

// 首次加载立刻应用
if (typeof window !== "undefined") {
  const stored = localStorage.getItem("pdfdiff-palette");
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      apply(parsed?.state?.palette || "classic");
    } catch {
      apply("classic");
    }
  } else {
    apply("classic");
  }
}
