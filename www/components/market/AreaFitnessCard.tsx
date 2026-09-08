"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, Info } from "lucide-react";
import { fetchAreaFitness } from "@/lib/api";
import type { AreaFitness } from "@/lib/types";

const won = (v: number) => `${v.toLocaleString()}원`;

const TONE_ICON = { good: CircleCheck, warn: Info, bad: CircleAlert } as const;
const TONE_CLASS = { good: "text-up", warn: "text-foreground-muted", bad: "text-down" } as const;

// 종합점수(0~1) 5단계 — 방향 토큰 2개(up/down)만 쓴다(AreaScoreCard와 같은 규칙, DESIGN.md §7)
function gradeOf(score: number) {
  if (score >= 0.75) return { label: "탁월", tone: "text-up" };
  if (score >= 0.58) return { label: "양호", tone: "text-up" };
  if (score >= 0.46) return { label: "보통", tone: "text-foreground" };
  if (score >= 0.33) return { label: "주의", tone: "text-down" };
  return { label: "위험", tone: "text-down" };
}

/**
 * 입지 적합도 카드 — /market/trdar/{code}/fitness.
 * 이 상권에 이 업종이 맞는 자리인지 4축(수요·시간대·경쟁·생존)으로 판정한다.
 * 전부 서울시 상권분석서비스 실데이터이고 창업비용·임대료 같은 가정치는 없다.
 */
export default function AreaFitnessCard({
  trdarCode,
  serviceCode,
}: {
  trdarCode: string;
  serviceCode: string;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["area-fitness", trdarCode, serviceCode],
    queryFn: () => fetchAreaFitness(trdarCode, serviceCode),
    enabled: !!trdarCode && !!serviceCode,
  });

  if (isLoading) return <div className="skeleton h-40 rounded-xl" />;
  if (!data) return null;

  return <FitnessBody fitness={data} />;
}

function FitnessBody({ fitness }: { fitness: AreaFitness }) {
  const grade = gradeOf(fitness.totalScore);

  return (
    <div className="bg-surface border border-border rounded-xl p-3.5">
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-xs text-foreground-muted">{fitness.serviceName}</span>
        <span className={`ml-auto text-lg font-bold ${grade.tone}`}>{grade.label}</span>
        <span className="text-sm text-foreground-muted tabular-nums">
          {(fitness.totalScore * 100).toFixed(0)}점
        </span>
      </div>

      {/* 4축 분해 — 가중치를 보여야 어느 축이 점수를 갈랐는지 읽힌다 */}
      <ul className="mt-3 space-y-2">
        {fitness.components.map((c) => (
          <li key={c.key} className="flex items-center gap-2 text-xs">
            <span className="w-20 shrink-0 text-foreground-muted">
              {c.label}
              <span className="ml-1 opacity-60 tabular-nums">×{c.weight.toFixed(2)}</span>
            </span>
            <span className="flex-1 h-1.5 rounded-full bg-black/[0.06] overflow-hidden">
              <span
                className="block h-full rounded-full bg-brand"
                style={{ width: `${Math.round(c.score * 100)}%` }}
              />
            </span>
            <span className="w-8 text-right tabular-nums">{(c.score * 100).toFixed(0)}</span>
          </li>
        ))}
      </ul>

      {/* 진단 — 나쁜 신호가 먼저 온다 */}
      <ul className="mt-3 space-y-1.5">
        {fitness.diagnoses.map((d, i) => {
          const Icon = TONE_ICON[d.tone];
          return (
            <li key={i} className="flex gap-2 text-xs leading-relaxed">
              <Icon size={14} strokeWidth={2} className={`shrink-0 mt-0.5 ${TONE_CLASS[d.tone]}`} />
              <span>{d.message}</span>
            </li>
          );
        })}
      </ul>

      <dl className="mt-3 pt-3 border-t border-border grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <dt className="text-foreground-muted">점포당 월매출</dt>
          <dd className="tabular-nums font-medium">{won(fitness.observedSalesPerStore)}</dd>
        </div>
        <div>
          <dt className="text-foreground-muted">객단가</dt>
          <dd className="tabular-nums font-medium">{won(fitness.observedTicketPrice)}</dd>
        </div>
        <div>
          <dt className="text-foreground-muted">같은 업종 점포</dt>
          <dd className="tabular-nums font-medium">
            {fitness.observedSimilarStoreCount.toLocaleString()}곳
          </dd>
        </div>
        <div>
          <dt className="text-foreground-muted">평균 영업 기간</dt>
          <dd className="tabular-nums font-medium">
            {(fitness.observedOperatingMonthsAvg / 12).toFixed(1)}년
          </dd>
        </div>
      </dl>

      <p className="mt-3 text-xs text-foreground-muted">
        {fitness.yearQuarter}분기 서울시 상권분석서비스 실데이터 기준. 임대료·권리금·창업비용은
        공개 데이터가 없어 포함하지 않았습니다.
      </p>
    </div>
  );
}
