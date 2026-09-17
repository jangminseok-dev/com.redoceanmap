"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAreaScore } from "@/lib/api";
import type { AreaScoreDetail, ScoreComponent } from "@/lib/types";

// 5단계를 방향 토큰 2개(up/down)로 표현한다 — 주황 같은 새 색을 만들지 않기 위해(DESIGN.md §7)
// 텍스트는 방향만 말하고, 강약은 배경 농도가 맡는다. 단계 이름이 라벨로 이미 적혀 있으므로
// 색이 5단계를 혼자 구분할 필요는 없다.
const GRADE_STYLE: Record<string, string> = {
  우수: "text-up bg-up-weak border-up/20",
  양호: "text-up bg-up-weak/50 border-up/10",
  보통: "text-foreground bg-surface border-border",
  주의: "text-down bg-down-weak/50 border-down/10",
  위험: "text-down bg-down-weak border-down/20",
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
          <p className="text-xs text-foreground-muted mt-0.5">
            향후 1년 폐업률을 가르는 종합점수 · 50점 = 서울 중앙 상권
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
        <span className="text-xs text-foreground-muted">
          상권 전체 매출 추이 <span className="opacity-60">(전 업종 합계)</span>
        </span>
        <span className="flex gap-1">
          {(["yoy", "qoq"] as const).map((b) => (
            <button
              key={b}
              onClick={() => setBasis(b)}
              className={`px-1.5 py-0.5 rounded-md text-xs font-medium ${
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
      <p className="text-xs text-foreground-muted mt-1 tabular-nums">
        최근 {points[points.length - 1].yearQuarter} {rates[rates.length - 1] > 0 ? "+" : ""}
        {rates[rates.length - 1]}%
      </p>
    </div>
  );
}

// 단위가 축마다 다르다 — 폐업률은 최근 4분기 %, 지속성은 평균 영업 개월, 매출은 점포당 월 만원.
const FORMAT: Record<ScoreComponent["key"], (v: number) => string> = {
  closure_stability: (v) => `${v.toFixed(1)}%`,
  persistence: (v) => `${v.toFixed(0)}개월`,
  sales_level: (v) => `${Math.round(v).toLocaleString()}만원`,
};

function ComponentBar({ component: c }: { component: ScoreComponent }) {
  const signed = FORMAT[c.key] ?? ((v: number) => v.toFixed(1));
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-foreground-muted">{c.name}</span>
        {/* 점수만 보여주면 근거가 사라진다 — 응답에 실려 오던 실수치를 되돌려 준다 */}
        <span className="flex items-baseline gap-1.5">
          <span className="text-foreground-muted tabular-nums">
            {signed(c.value)} <span className="opacity-60">vs 서울 중앙 {signed(c.benchmark)}</span>
          </span>
          {/* 방향을 색으로 명시 — "47.9점"만 보면 평균 이상처럼 읽힌다(2026-08-31 테스트).
              ±5점 안쪽은 평균권이라 중립색 유지 */}
          <span
            title="50점 = 서울 중앙 상권"
            className={`font-semibold tabular-nums ${
              c.score >= 55 ? "text-up" : c.score <= 45 ? "text-down" : ""
            }`}
          >
            {c.score}
          </span>
        </span>
      </div>
      <div className="relative mt-1 h-1.5 rounded-full bg-border/60 overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-brand/70"
          style={{ width: `${c.score}%` }}
        />
        {/* 50점 = 서울 중앙 상권 기준선 */}
        <div className="absolute inset-y-0 left-1/2 w-px bg-foreground-muted/50" />
      </div>
    </div>
  );
}
