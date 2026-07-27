"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchAreaScore } from "@/lib/api";
import type { ScoreComponent } from "@/lib/types";

const GRADE_STYLE: Record<string, string> = {
  우수: "text-red-600 bg-red-50 border-red-200",
  양호: "text-orange-600 bg-orange-50 border-orange-200",
  보통: "text-foreground bg-surface border-border",
  주의: "text-blue-600 bg-blue-50 border-blue-200",
  위험: "text-blue-700 bg-blue-50 border-blue-300",
};

// 상권 종합점수 카드 — /market/trdar/{code}/score. 산출 근거 팩트가 없으면 렌더 생략.
export default function AreaScoreCard({ trdarCode }: { trdarCode: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["area-score", trdarCode],
    queryFn: () => fetchAreaScore(trdarCode),
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
