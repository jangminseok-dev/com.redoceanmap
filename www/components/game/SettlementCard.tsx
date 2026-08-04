"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, Info } from "lucide-react";
import { fetchGameSettlements } from "@/lib/api";
import type { GameAdvice } from "@/lib/types";

const won = (v: number) => `${v.toLocaleString()}원`;
const toneOf = (v: number) => (v >= 0 ? "text-up" : "text-down");

const ADVICE_ICON: Record<GameAdvice["tone"], typeof Info> = {
  good: CircleCheck,
  warn: Info,
  bad: CircleAlert,
};
const ADVICE_CLASS: Record<GameAdvice["tone"], string> = {
  good: "text-emerald-600",
  warn: "text-amber-600",
  bad: "text-up",
};

/**
 * 분기 결산.
 *
 * **조회가 곧 정산 시점이다** — cron이 없어 밀린 분기를 이 요청에서 확정한다(지연 실행).
 * 멱등하므로 화면을 다시 열어도 중복 정산되지 않는다.
 */
export default function SettlementCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["game-settlements"],
    queryFn: fetchGameSettlements,
    refetchInterval: (query) => (query.state.status === "error" ? 300_000 : 60_000),
  });

  if (isLoading || !data) return null;
  if (data.settlements.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-surface p-5">
        <h2 className="text-sm font-bold tracking-tight">분기 결산</h2>
        <p className="mt-2 text-sm text-foreground-muted">
          아직 끝난 분기가 없습니다. 게임 90일(현실 90시간)마다 결산이 확정되고 손익이 지갑에
          반영됩니다.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-baseline gap-2 flex-wrap">
        <h2 className="text-sm font-bold tracking-tight">분기 결산</h2>
        {data.newlySettled > 0 && (
          <span className="text-xs text-brand font-medium">
            {data.newlySettled}개 분기가 방금 확정됐습니다
          </span>
        )}
        <span className={`ml-auto text-base font-bold tabular-nums ${toneOf(data.totalProfitKrw)}`}>
          누적 {data.totalProfitKrw >= 0 ? "+" : ""}
          {data.totalProfitKrw.toLocaleString()}원
        </span>
      </div>

      <ul className="mt-4 space-y-3">
        {[...data.settlements].reverse().map((s) => (
          <li key={`${s.storeId}-${s.gameQuarter}`} className="rounded-xl border border-border p-3">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-sm font-medium">
                {s.gameQuarter}분기 · {s.trdarName}
              </span>
              <span className="text-xs text-foreground-muted">
                {s.serviceName} · {s.daysCounted}일 · 손님 {s.customerCount.toLocaleString()}명
              </span>
              <span className={`ml-auto text-sm font-bold tabular-nums ${toneOf(s.profitKrw)}`}>
                {s.profitKrw >= 0 ? "+" : ""}
                {s.profitKrw.toLocaleString()}원
              </span>
            </div>

            <dl className="mt-2 grid grid-cols-2 sm:grid-cols-5 gap-x-3 gap-y-1 text-xs">
              <div>
                <dt className="text-foreground-muted">매출</dt>
                <dd className="tabular-nums">{won(s.simulatedSalesKrw)}</dd>
              </div>
              <div>
                <dt className="text-foreground-muted">임대료</dt>
                <dd className="tabular-nums">{won(s.assumedRentKrw)}</dd>
              </div>
              <div>
                <dt className="text-foreground-muted">인건비</dt>
                <dd className="tabular-nums">{won(s.assumedLaborKrw)}</dd>
              </div>
              <div>
                <dt className="text-foreground-muted">원가</dt>
                <dd className="tabular-nums">{won(s.assumedCogsKrw)}</dd>
              </div>
              <div>
                <dt className="text-foreground-muted">상권 평균 대비</dt>
                <dd className="tabular-nums">{(s.performanceRatio * 100).toFixed(0)}%</dd>
              </div>
            </dl>

            {s.advices.length > 0 && (
              <ul className="mt-2 space-y-1">
                {s.advices.map((a, i) => {
                  const Icon = ADVICE_ICON[a.tone];
                  return (
                    <li key={i} className="flex gap-1.5 text-xs leading-relaxed">
                      <Icon
                        size={13}
                        strokeWidth={2}
                        className={`shrink-0 mt-0.5 ${ADVICE_CLASS[a.tone]}`}
                      />
                      <span>{a.message}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </li>
        ))}
      </ul>

      <p className="mt-3 text-xs text-foreground-muted">
        임대료·인건비·원가는 공개 데이터가 없어 게임 규칙으로 산정한 가정치입니다.
      </p>
    </div>
  );
}
