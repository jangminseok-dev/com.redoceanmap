"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useThemeStore } from "@/lib/uiStore";

/**
 * 테마 토글 — 레일 하단(variant="rail")과 더보기 시트(variant="row")에 놓인다.
 *
 * 서버는 항상 라이트로 렌더하고 실제 테마는 첫 페인트 전 인라인 스크립트가 정하므로,
 * 마운트 전에는 아이콘·라벨을 그리지 않는다(자리만 유지) — hydration 어긋남 방지.
 */
export default function ThemeToggle({ variant }: { variant: "rail" | "row" }) {
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const dark = mounted && theme === "dark";
  const Icon = dark ? Sun : Moon;
  const label = dark ? "라이트" : "다크";

  if (variant === "row") {
    return (
      <button
        type="button"
        onClick={toggleTheme}
        className="flex items-center gap-3 px-2 py-3 rounded-xl text-sm hover:bg-accent transition-colors"
      >
        <Icon size={17} strokeWidth={1.75} className={mounted ? "text-brand" : "invisible"} />
        {mounted ? `${label} 테마` : "테마"}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      title={mounted ? `${label} 테마로 전환` : undefined}
      className="w-full flex flex-col items-center gap-1 py-2.5 rounded-xl text-foreground-muted hover:bg-accent hover:text-foreground transition-colors"
    >
      <Icon size={20} strokeWidth={1.75} className={mounted ? "" : "invisible"} />
      <span className="text-xs">{mounted ? label : "테마"}</span>
    </button>
  );
}
