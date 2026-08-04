"use client";

import type { AreaStatsDetail, QuarterStat } from "@/lib/types";

// series 마지막 분기(최신) 점포 팩트 + 변화지표 요약
// 율(%)과 절대 건수를 함께 — 어느 한쪽만으론 규모를 오독한다.
function rateWithCount(rate: number | null, count: number | null): string {
  if (rate === null) return "—";
  return count !== null ? `${rate}% (${count}개)` : `${rate}%`;
}

export default function StorePanel({
  series,
  latest,
}: {
  series: QuarterStat[];
  latest: AreaStatsDetail["latest"];
}) {
  const recent = [...series].reverse().find((q) => q.storeCount !== null);

  const stats: [string, string][] = recent
    ? [
        ["영업 점포", `${recent.storeCount}개`],
        // 같은 업종 경쟁 강도 — 창업 판단에 직결된다
        ["동일 업종", recent.similarIndustryCount !== null ? `${recent.similarIndustryCount}개` : "—"],
        ["프랜차이즈", recent.franchiseCount !== null ? `${recent.franchiseCount}개` : "—"],
        // 율만 보여주면 소규모 상권에서 오독한다("3개 중 1개 = 33%") — 건수를 병기한다
        ["개업률", rateWithCount(recent.openingRate, recent.openingCount)],
        ["폐업률", rateWithCount(recent.closureRate, recent.closureCount)],
      ]
    : [];

  return (
    <div className="flex flex-col gap-2">
      {stats.length > 0 ? (
        <div className="grid grid-cols-2 gap-2">
          {stats.map(([label, value]) => (
            <div key={label} className="bg-surface border border-border rounded-lg px-3 py-2.5">
              <div className="text-xs text-foreground-muted">{label}</div>
              <div className="text-sm font-semibold mt-0.5">{value}</div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-foreground-muted">점포 데이터가 없습니다.</p>
      )}

      {(latest.changeIndicator || latest.operatingMonthsAvg !== null) && (
        <div className="bg-surface border border-border rounded-lg px-3 py-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-foreground-muted">상권 변화</span>
            {latest.changeIndicator && (
              <span className="text-xs font-medium px-1.5 py-0.5 rounded-md border border-brand/30 bg-brand/5 text-brand">
                {latest.changeIndicator}
              </span>
            )}
          </div>
          {latest.operatingMonthsAvg !== null && (
            <p className="text-sm font-semibold mt-1">
              평균 운영 {Math.round(latest.operatingMonthsAvg)}개월
              {latest.regionOperatingMonthsAvg !== null && (
                <span className="text-xs font-normal text-foreground-muted">
                  {" "}
                  · 시도 평균 {Math.round(latest.regionOperatingMonthsAvg)}개월
                </span>
              )}
            </p>
          )}
          {/* 생존 중 점포의 영업개월만으론 "얼마 만에 닫는가"를 알 수 없다 */}
          {latest.closureMonthsAvg !== null && (
            <p className="text-xs text-foreground-muted mt-0.5">
              폐업 점포는 평균 {Math.round(latest.closureMonthsAvg)}개월 만에 닫음
              {latest.regionClosureMonthsAvg !== null && (
                <> · 시도 평균 {Math.round(latest.regionClosureMonthsAvg)}개월</>
              )}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
