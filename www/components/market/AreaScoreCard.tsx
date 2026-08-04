"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAreaScore } from "@/lib/api";
import type { AreaScoreDetail, ScoreComponent } from "@/lib/types";

const GRADE_STYLE: Record<string, string> = {
  우수: "text-red-600 bg-red-50 border-red-200",
  양호: "text-orange-600 bg-orange-50 border-orange-200",
  보통: "text-foreground bg-surface border-border",
  주의: "text-blue-600 bg-blue-50 border-blue-200",
  위험: "text-blue-700 bg-blue-50 border-blue-300",
};

// 상권 종합점수 카드 — /market/trdar/{code}/score. 산출 근거 팩트가 없으면 렌더 생략.
export default function AreaScoreCard({
  trdarCode,
  quarters = 8,
}: {
  trdarCode: string;
  quarters?: number;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["area-score", trdarCode, quarters],
    queryFn: () => fetchAreaScore(trdarCode, quarters),
    enabled: !!trdarCode,
  });

  if (isLoading) return <div className="skeleton h-28 rounded-xl" />;
  if (!data?.score) return null;

  const { total, grade, components } = data.score;
  const gradeStyle = GRADE_STYLE[grade] ?? GRADE_STYLE["보통"];

  return (
    <div className="bg-surface border border-border rounded-xl p-3.5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-2xl font-bold">
            {total}
            <span className="text-sm font-medium text-foreground-muted ml-0.5">점</span>
          </div>
          <p className="text-[11px] text-foreground-muted mt-0.5">
            서울 평균 대비 종합점수 · 50점 = 평균 수준
          </p>
        </div>
        <span className={`inline-flex px-2.5 py-1 rounded-full border text-xs font-semibold ${gradeStyle}`}>
          {grade}
        </span>
      </div>

      <div className="mt-3 flex flex-col gap-2">
        {components.map((c) => (
          <ComponentBar key={c.key} component={c} />
        ))}
      </div>
      <TrendStrip trend={data.trend} />
    </div>
  );
}

// 응답에 실려 오면서도 렌더러가 없어 버려지던 추이. 분모가 '전 업종 합계'라
// 업종 단위인 SalesTrendChart와 섞지 않고 여기서 따로 보여준다.
function TrendStrip({ trend }: { trend: AreaScoreDetail["trend"] }) {
  const [basis, setBasis] = useState<"yoy" | "qoq">("yoy");
  const points = trend.filter((p) => (basis === "yoy" ? p.salesYoy : p.salesQoq) !== null);
  if (points.length < 2) return null;
  const rates = points.map((p) => (basis === "yoy" ? p.salesYoy! : p.salesQoq!));
  const bound = Math.max(...rates.map(Math.abs), 1);

  return (
    <div className="mt-3 pt-3 border-t border-border">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px] text-foreground-muted">
          상권 전체 매출 추이 <span className="opacity-60">(전 업종 합계)</span>
        </span>
        <span className="flex gap-1">
          {(["yoy", "qoq"] as const).map((b) => (
            <button
              key={b}
              onClick={() => setBasis(b)}
              className={`px-1.5 py-0.5 rounded-md text-[10px] font-medium ${
                basis === b ? "bg-brand/10 text-brand" : "text-foreground-muted"
              }`}
            >
              {b === "yoy" ? "전년비" : "전분기비"}
            </button>
          ))}
        </span>
      </div>
      {/* 0을 가운데 둔 발산 막대 — 계절성이 큰 데이터라 전년비를 기본으로 둔다 */}
      <div className="flex items-end gap-0.5 h-10">
        {points.map((p, i) => {
          const rate = rates[i];
          const h = Math.max(2, (Math.abs(rate) / bound) * 100);
          return (
            <div
              key={p.yearQuarter}
              title={`${p.yearQuarter} ${rate > 0 ? "+" : ""}${rate}%`}
              className="flex-1 flex flex-col justify-center items-stretch h-full"
            >
              <div className="flex-1 flex items-end">
                {rate > 0 && <div className="w-full bg-emerald-500/60 rounded-t" style={{ height: `${h}%` }} />}
              </div>
              <div className="flex-1 flex items-start">
                {rate < 0 && <div className="w-full bg-rose-500/60 rounded-b" style={{ height: `${h}%` }} />}
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-foreground-muted mt-1 tabular-nums">
        최근 {points[points.length - 1].yearQuarter} {rates[rates.length - 1] > 0 ? "+" : ""}
        {rates[rates.length - 1]}%
      </p>
    </div>
  );
}

// 성장 축은 %(증감률), 건강도·지속성은 각각 %p·개월 — 단위가 달라 컴포넌트별로 붙인다.
const UNIT: Record<ScoreComponent["key"], string> = {
  sales_growth: "%",
  floating_growth: "%",
  store_health: "%p",
  persistence: "개월",
};

function ComponentBar({ component: c }: { component: ScoreComponent }) {
  const unit = UNIT[c.key] ?? "";
  const signed = (v: number) =>
    c.key.endsWith("_growth") || c.key === "store_health"
      ? `${v > 0 ? "+" : ""}${v.toFixed(1)}${unit}`
      : `${v.toFixed(1)}${unit}`;
  return (
    <div>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-foreground-muted">{c.name}</span>
        {/* 점수만 보여주면 근거가 사라진다 — 응답에 실려 오던 실수치를 되돌려 준다 */}
        <span className="flex items-baseline gap-1.5">
          <span className="text-foreground-muted tabular-nums">
            {signed(c.value)} <span className="opacity-60">vs 서울 {signed(c.benchmark)}</span>
          </span>
          <span className="font-semibold tabular-nums">{c.score}</span>
        </span>
      </div>
      <div className="relative mt-1 h-1.5 rounded-full bg-border/60 overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-brand/70"
          style={{ width: `${c.score}%` }}
        />
        {/* 50점 = 벤치마크 동률 기준선 */}
        <div className="absolute inset-y-0 left-1/2 w-px bg-foreground-muted/50" />
      </div>
    </div>
  );
}
