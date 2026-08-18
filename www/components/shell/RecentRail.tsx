"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRecentStore, type RecentItem } from "@/lib/uiStore";

const ROUTE_OF_TYPE: Record<RecentItem["type"], string> = {
  stock: "/stock",
  market: "/market",
};

function hrefOf(item: RecentItem): string {
  return item.type === "stock"
    ? `/stock?symbol=${encodeURIComponent(item.id)}`
    : `/market?trdar=${item.id}`;
}

/**
 * 레일 "최근" 스택 — 최근 본 종목/상권 마크 최대 3개(핸드오프 §공통 셸).
 * 워크스페이스를 떠나도 레일에 남아 한 번에 돌아간다(레퍼런스 토스증권 우측 레일).
 *
 * localStorage persist 스토어라 서버 렌더와 첫 클라이언트 값이 다르다 —
 * 마운트 후에만 그린다(hydration 어긋남 방지).
 */
export default function RecentRail() {
  const pathname = usePathname();
  const items = useRecentStore((s) => s.items);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted || items.length === 0) return null;

  return (
    <div className="w-full flex flex-col items-center gap-1.5 pt-2">
      <span aria-hidden className="w-8 h-px bg-border" />
      <span className="text-xs text-foreground-muted">최근</span>
      {items.map((item, i) => {
        // 방문이 스택 갱신이므로 "그 워크스페이스에 있는 동안의 items[0]" = 지금 보는 항목
        const current = i === 0 && !!pathname?.startsWith(ROUTE_OF_TYPE[item.type]);
        return (
          <Link
            key={`${item.type}:${item.id}`}
            href={hrefOf(item)}
            title={item.label}
            aria-current={current ? "true" : undefined}
            className={`grid place-items-center w-[34px] h-[34px] rounded-full bg-accent text-[13px] font-bold transition-colors hover:bg-border/70 ${
              current ? "shadow-[0_0_0_1.5px_var(--brand)] text-brand" : "text-foreground"
            }`}
          >
            {item.label.trim().charAt(0) || "?"}
          </Link>
        );
      })}
    </div>
  );
}
