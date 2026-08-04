"use client";

import { CircleAlert, CircleCheck, Info } from "lucide-react";
import type { GameAreaFitness } from "@/lib/types";

const won = (v: number) => `${v.toLocaleString()}원`;

const TONE_ICON = {
  good: CircleCheck,
  warn: Info,
  bad: CircleAlert,
} as const;

const TONE_CLASS = {
  good: "text-emerald-600",
  warn: "text-amber-600",
  bad: "text-up",
} as const;

function gradeOf(fitness: number) {
  if (fitness >= 1.3) return { label: "탁월", tone: "text-emerald-600" };
  if (fitness >= 1.1) return { label: "양호", tone: "text-emerald-600" };
  if (fitness >= 0.95) return { label: "보통", tone: "text-amber-600" };
  if (fitness >= 0.8) return { label: "주의", tone: "text-amber-700" };
  return { label: "위험", tone: "text-up" };
}

/**
 * 입지 적합도 카드.
 *
 * `observed*`는 서울시 상권분석서비스 실데이터, `simulated*`는 게임 규칙 산출값이다.
 * 화면에서도 그 구분이 보이게 라벨을 나눈다(game-harness §5-1).
 */
export default function StoreFitnessCard({ fitness }: { fitness: GameAreaFitness }) {
  const grade = gradeOf(fitness.fitness);

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-baseline gap-2 flex-wrap">
        <h3 className="text-base font-bold tracking-tight">{fitness.trdarName}</h3>
        <span className="text-xs text-foreground-muted">{fitness.serviceName}</span>
        <span className={`ml-auto text-lg font-bold ${grade.tone}`}>{grade.label}</span>
        <span className="text-sm text-foreground-muted tabular-nums">
          적합도 {fitness.fitness.toFixed(2)}
        </span>
      </div>

      {/* 적합도가 높아도 열 수 없는 자리가 있다 — 등급만 보고 오해하지 않게 먼저 말한다 */}
      {!fitness.openable && (
        <p className="mt-3 rounded-xl bg-up/[0.06] border border-up/20 px-3 py-2 text-xs text-up">
          이 상권엔 {fitness.serviceName} 매출 기록이 없어 창업 기준(점포당 월매출)을 세울 수
          없습니다.
        </p>
      )}

      {/* 4축 분해 */}
      <ul className="mt-4 space-y-2">
        {fitness.components.map((c) => (
          <li key={c.key} className="flex items-center gap-2 text-xs">
            <span className="w-20 shrink-0 text-foreground-muted">
              {c.label}
              {/* 가중치를 보여야 어느 축을 고쳐야 적합도가 오르는지 판단할 수 있다 */}
              <span className="ml-1 opacity-60 tabular-nums">
                ×{c.weight.toFixed(2)}
              </span>
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
      <ul className="mt-4 space-y-1.5">
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

      <dl className="mt-4 pt-3 border-t border-border grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div className="col-span-2">
          <dt className="text-foreground-muted">이 자리에서 예상되는 월매출 (게임 규칙 추정)</dt>
          <dd className="text-base font-bold tabular-nums">
            {won(fitness.simulatedMonthlySalesKrw)}
          </dd>
        </div>
        <div>
          <dt className="text-foreground-muted">점포당 월매출 (실측)</dt>
          <dd className="tabular-nums font-medium">{won(fitness.observedSalesPerStore)}</dd>
        </div>
        <div>
          <dt className="text-foreground-muted">객단가 (실측)</dt>
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
        {/* 자리마다 다르다 — 점포당 매출이 클수록(=임대료가 비쌀수록) 최소 자본도 커진다 */}
        {fitness.openable && (
          <>
            <div>
              <dt className="text-foreground-muted">최소 창업 자본</dt>
              <dd className="tabular-nums font-medium">
                {won(fitness.assumedMinimumCapitalKrw)}
              </dd>
            </div>
            <div>
              <dt className="text-foreground-muted">장사가 되는 자본</dt>
              <dd className="tabular-nums font-medium">
                {won(fitness.assumedViableCapitalKrw)}
              </dd>
            </div>
          </>
        )}
      </dl>

      <p className="mt-3 text-xs text-foreground-muted">
        {fitness.observedQuarter}분기 서울시 상권분석서비스 실데이터 기준. 임대료·인건비·원가는
        공개 데이터가 없어 게임 규칙으로 산정한 가정치입니다.
      </p>
    </div>
  );
}
