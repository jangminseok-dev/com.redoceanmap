"use client";

import { useState } from "react";
import type { AreaDetail } from "@/lib/types";

type SortKey = "monthlySales" | "salesPerStore";

const won = (v: number | null) => {
  if (v == null) return "—";
  if (v >= 100_000_000) return `${(v / 100_000_000).toFixed(1)}억`;
  return `${Math.round(v / 10_000).toLocaleString()}만`;
};

/**
 * 상권 안 업종 랭킹 — estimated_sales가 상권 × 업종으로 적재돼 있는데
 * 지금까지 매출 최대 업종 1개만 쓰고 나머지(중앙 11개·최대 53개)를 버렸다.
 *
 * 매출 1위와 점포당 매출 1위는 자주 다르다("카페 46곳 경쟁 vs 분식 3곳").
 * 그래서 정렬 축을 둘 다 둔다.
 */
export default function ServiceRankingSection({
  ranking,
  currentCode,
  onSelect,
}: {
  ranking: AreaDetail["serviceRanking"];
  currentCode: string | null;
  onSelect?: (code: string) => void;
}) {
  const [sort, setSort] = useState<SortKey>("monthlySales");
  if (!ranking.length) return null;

  const rows = [...ranking].sort((a, b) => (b[sort] ?? -1) - (a[sort] ?? -1));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-1">
        {(
          [
            ["monthlySales", "매출순"],
            ["salesPerStore", "점포당 매출순"],
          ] as [SortKey, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setSort(key)}
            className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${
              sort === key ? "bg-brand/10 text-brand" : "text-foreground-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="flex flex-col gap-1">
        {rows.map((r) => {
          const active = r.code === currentCode;
          return (
            <button
              key={r.code}
              onClick={() => onSelect?.(r.code)}
              disabled={!onSelect}
              className={`grid grid-cols-[1fr_auto_auto] items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors ${
                active ? "bg-brand/10" : "hover:bg-foreground/5"
              } ${onSelect ? "" : "cursor-default"}`}
            >
              <span className="text-xs font-medium truncate">
                {r.name}
                {r.storeCount !== null && (
                  <span className="text-foreground-muted font-normal"> · {r.storeCount}곳</span>
                )}
              </span>
              <span className="text-xs tabular-nums text-foreground-muted">
                {won(sort === "monthlySales" ? r.monthlySales : r.salesPerStore)}원
              </span>
              <span
                className={`text-[11px] tabular-nums w-12 text-right ${
                  r.salesQoq == null
                    ? "text-foreground-muted"
                    : r.salesQoq > 0
                      ? "text-emerald-600"
                      : "text-rose-600"
                }`}
              >
                {r.salesQoq == null ? "—" : `${r.salesQoq > 0 ? "+" : ""}${r.salesQoq}%`}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
