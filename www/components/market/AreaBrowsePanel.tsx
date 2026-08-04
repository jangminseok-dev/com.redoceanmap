"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, Trophy } from "lucide-react";
import { fetchAreaShowcase, fetchRecommendations } from "@/lib/api";
import { useUIStore } from "@/lib/uiStore";
import { formatMoney } from "./overlay/format";

const quarterLabel = (yq: number | null) =>
  yq ? `${String(yq).slice(0, 4)}년 ${String(yq).slice(4)}분기` : "";

/**
 * 상권을 아직 고르지 않았을 때의 자료 패널.
 *
 * 예전에는 "지도에서 상권을 선택하거나 채팅으로 추천받으면 통계가 표시됩니다" 한 줄이었다.
 * 그 자리에 홈에서 내린 두 목록(최근 추천 이력 · 자치구별 1위 상권)을 놓는다 —
 * 홈은 물어보는 자리 하나로 비우고, 데이터는 그 데이터를 쓰는 화면에서 보여준다.
 */
export default function AreaBrowsePanel({ onSelect }: { onSelect: (trdarCode: string) => void }) {
  const user = useUIStore((s) => s.user);

  const recentQ = useQuery({
    queryKey: ["recent-recommendations"],
    queryFn: () => fetchRecommendations(8),
    enabled: !!user, // 내 이력이라 로그인 필요 — 비로그인은 조회 자체를 걸지 않는다
  });
  // 쇼케이스는 공개 엔드포인트다(비로그인도 그대로 실행). 분기 단위로만 바뀌므로 길게 잡는다.
  const showcaseQ = useQuery({
    queryKey: ["area-showcase"],
    queryFn: fetchAreaShowcase,
    staleTime: 1000 * 60 * 60,
  });
  const showcase = showcaseQ.data;

  const seen = new Set<string>();
  const recent = (recentQ.data ?? [])
    .filter((r) => !seen.has(r.trdar_name) && seen.add(r.trdar_name))
    .slice(0, 4);

  return (
    <div className="p-4 flex flex-col gap-6">
      {recent.length > 0 && (
        <section>
          <h3 className="flex items-center gap-1.5 text-xs font-semibold text-foreground-muted uppercase tracking-wide mb-2">
            <Clock size={13} strokeWidth={2} />
            최근 추천받은 상권
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2">
            {recent.map((area) => (
              <button
                key={area.id}
                type="button"
                onClick={() => onSelect(String(area.trdar_code))}
                className="text-left bg-surface border border-border rounded-xl p-3 hover:border-brand/40 transition-colors"
              >
                <div className="text-sm font-semibold truncate">{area.trdar_name}</div>
                <p className="mt-0.5 text-xs text-foreground-muted truncate">
                  {area.district_name} · {area.category}
                </p>
                <p className="mt-1.5 text-xs text-foreground/80 leading-snug line-clamp-2">
                  {area.reason}
                </p>
              </button>
            ))}
          </div>
        </section>
      )}

      <section>
        <h3 className="flex items-center gap-1.5 text-xs font-semibold text-foreground-muted uppercase tracking-wide mb-2">
          <Trophy size={13} strokeWidth={2} />
          자치구별 점포당 매출 1위
        </h3>

        {/* 무엇을 센 숫자인지, 무엇이 아닌지를 목록 위에 먼저 적는다 */}
        {showcase && (
          <p className="mb-2.5 text-xs text-foreground-muted leading-relaxed">
            {quarterLabel(showcase.yearQuarter)} 집계 · 점포 {showcase.minStoreCount}개 이상 · 자치구당 1곳.
            업종 구성이 달라 창업 예상 매출이 아니고, 앞으로의 성과를 예측하지 않습니다.
          </p>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-2">
          {showcaseQ.isPending &&
            Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="skeleton h-[104px] rounded-xl" />
            ))}

          {(showcase?.rows ?? []).map((area, i) => (
            <button
              key={area.trdarCode}
              type="button"
              onClick={() => onSelect(String(area.trdarCode))}
              className="text-left bg-surface border border-border rounded-xl p-3 hover:border-brand/40 transition-colors"
            >
              <div className="flex items-baseline gap-1.5">
                <span className="text-xs tabular-nums text-foreground-muted">{i + 1}</span>
                <span className="text-sm font-semibold truncate">{area.trdarName}</span>
              </div>
              <p className="mt-0.5 mb-1.5 text-xs text-foreground-muted truncate">
                {area.districtName} · {area.divisionName}
              </p>
              <p className="text-data-l tabular-nums">{formatMoney(area.salesPerStore)}</p>
              <p className="text-xs text-foreground-muted tabular-nums">
                점포당 · 점포 {area.storeCount.toLocaleString()}개
              </p>
            </button>
          ))}
        </div>

        {/* 1위가 점포당 19억대(도매시장)라 맥락 없이 두면 "창업하면 그만큼 번다"로 읽힌다 */}
        {showcase && showcase.divisionMedians.length > 0 && (
          <p className="mt-2.5 text-xs text-foreground-muted leading-relaxed">
            상권 유형별 점포당 매출 중앙값 —{" "}
            {showcase.divisionMedians
              .map(
                (m) =>
                  `${m.divisionName} ${m.areaCount.toLocaleString()}곳 ${formatMoney(m.medianSalesPerStore)}`,
              )
              .join(" · ")}
          </p>
        )}
      </section>
    </div>
  );
}
