"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, closeGameStore, decideGameStore, fetchGameStoreDaily } from "@/lib/api";
import type { GameCustomerBucket } from "@/lib/types";

const won = (v: number) => `${v.toLocaleString()}원`;
const toneOf = (v: number) => (v >= 0 ? "text-[#DC2626]" : "text-[#2563EB]");

function BucketRow({ title, buckets }: { title: string; buckets: GameCustomerBucket[] }) {
  const total = buckets.reduce((sum, b) => sum + b.count, 0) || 1;
  return (
    <div>
      <p className="text-[11px] text-foreground-muted">{title}</p>
      <ul className="mt-1 space-y-1">
        {buckets.slice(0, 3).map((b) => (
          <li key={b.label} className="flex items-center gap-2 text-xs">
            <span className="w-16 shrink-0 truncate">{b.label}</span>
            <span className="flex-1 h-1.5 rounded-full bg-black/[0.06] overflow-hidden">
              <span
                className="block h-full rounded-full bg-brand/70"
                style={{ width: `${Math.round((b.count / total) * 100)}%` }}
              />
            </span>
            <span className="w-8 text-right tabular-nums text-foreground-muted">
              {Math.round((b.count / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** 가게 현황 — 누적 손익, 최근 일별 내역, 오늘 온 손님 구성, 운영 결정. */
export default function StoreDetailCard({ storeId }: { storeId: number }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["game-store", storeId],
    queryFn: () => fetchGameStoreDaily(storeId, 14),
    refetchInterval: (query) => (query.state.status === "error" ? 300_000 : 30_000),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["game-store", storeId] });
    queryClient.invalidateQueries({ queryKey: ["game-stores"] });
    queryClient.invalidateQueries({ queryKey: ["game-wallet"] });
  };

  // 결정 변경 — 폼 제출이라 상태를 들지 않는다(REACT_RULES 패턴 A: FormData)
  const decide = useMutation({
    mutationFn: (body: { priceFactor?: number; staffCount?: number; facilityScore?: number }) =>
      decideGameStore(storeId, body),
    onSuccess: refresh,
  });
  const close = useMutation({
    mutationFn: () => closeGameStore(storeId),
    onSuccess: refresh,
  });
  const actionError = (decide.error ?? close.error) as ApiError | null;

  if (isLoading || !data) {
    return (
      <div className="rounded-2xl border border-border bg-surface p-8 text-center text-sm text-foreground-muted">
        가게 현황을 불러오는 중…
      </div>
    );
  }

  const profitable = data.cumulativeProfitKrw >= 0;

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-baseline gap-2 flex-wrap">
        <h3 className="text-base font-bold tracking-tight">{data.trdarName}</h3>
        <span className="text-xs text-foreground-muted">{data.serviceName}</span>
        <span className="ml-auto text-xs text-foreground-muted">
          개업 {data.daysOpen}일 · 좌석 {data.seats}석 · 규모 {(data.storeScale * 100).toFixed(1)}%
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div>
          <dt className="text-xs text-foreground-muted">누적 매출</dt>
          <dd className="text-base font-bold tabular-nums">{won(data.cumulativeSalesKrw)}</dd>
        </div>
        <div>
          <dt className="text-xs text-foreground-muted">누적 순익</dt>
          <dd className={`text-base font-bold tabular-nums ${toneOf(data.cumulativeProfitKrw)}`}>
            {data.cumulativeProfitKrw >= 0 ? "+" : ""}
            {data.cumulativeProfitKrw.toLocaleString()}원
          </dd>
        </div>
        <div>
          <dt className="text-xs text-foreground-muted">월 임대료 (가정)</dt>
          <dd className="text-base font-bold tabular-nums">{won(data.assumedMonthlyRentKrw)}</dd>
        </div>
        <div>
          <dt className="text-xs text-foreground-muted">평균 반려율</dt>
          <dd className="text-base font-bold tabular-nums">
            {(data.averageTurnedAwayRatio * 100).toFixed(0)}%
          </dd>
        </div>
      </dl>

      <dl className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3 border-t border-border pt-3">
        <div>
          <dt className="text-[11px] text-foreground-muted">보증금 (폐업 시 회수)</dt>
          <dd className="text-sm font-semibold tabular-nums">{won(data.depositKrw)}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-foreground-muted">인테리어 (회수 불가)</dt>
          <dd className="text-sm font-semibold tabular-nums">{won(data.interiorKrw)}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-foreground-muted">상권 점포당 월매출 (실측)</dt>
          <dd className="text-sm font-semibold tabular-nums">
            {won(Math.round(data.observedSalesPerStore))}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] text-foreground-muted">객단가 (실측)</dt>
          <dd className="text-sm font-semibold tabular-nums">
            {won(Math.round(data.observedTicketPrice))}
          </dd>
        </div>
        <p className="col-span-2 sm:col-span-4 text-[11px] text-foreground-muted">
          입지 적합도 {data.fitness.toFixed(2)}배 · 실측은 서울시 상권 데이터, 나머지는 게임 규칙의
          가정치입니다.
        </p>
      </dl>

      {data.averageTurnedAwayRatio >= 0.2 && (
        <p className="mt-3 rounded-xl bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
          손님의 {(data.averageTurnedAwayRatio * 100).toFixed(0)}%가 자리가 없어 돌아갔습니다.
          시설을 늘리면 더 받을 수 있습니다.
        </p>
      )}
      {!profitable && (
        <p className="mt-2 rounded-xl bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
          누적 적자입니다. 입지·업종이 맞지 않거나 고정비가 매출을 넘고 있습니다.
        </p>
      )}

      {data.status === "open" && (
        <form
          className="mt-4 border-t border-border pt-4"
          onSubmit={(e: React.FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            const added = Number(form.get("facilityAdd") ?? 0);
            decide.mutate({
              priceFactor: Number(form.get("priceFactor")),
              staffCount: Number(form.get("staffCount")),
              // 시설은 증가만 가능하다 — 더할 점수를 받아 현재값에 얹는다
              ...(added > 0 ? { facilityScore: data.facilityScore + added } : {}),
            });
          }}
        >
          <p className="text-xs font-semibold">운영 조정</p>
          <div className="mt-2 flex flex-wrap items-end gap-3">
            <label className="text-[11px] text-foreground-muted">
              가격 계수 (0.6~1.3)
              <input
                name="priceFactor"
                type="number"
                step="0.05"
                min={0.6}
                max={1.3}
                defaultValue={data.priceFactor}
                className="mt-1 block h-10 w-28 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
              />
            </label>
            <label className="text-[11px] text-foreground-muted">
              직원 수 (0~20)
              <input
                name="staffCount"
                type="number"
                min={0}
                max={20}
                defaultValue={data.staffCount}
                className="mt-1 block h-10 w-24 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
              />
            </label>
            <label className="text-[11px] text-foreground-muted">
              시설 추가 (현재 {data.facilityScore}점)
              <input
                name="facilityAdd"
                type="number"
                min={0}
                defaultValue={0}
                className="mt-1 block h-10 w-24 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
              />
            </label>
            <button
              type="submit"
              disabled={decide.isPending || close.isPending}
              className="h-10 px-4 rounded-xl bg-brand text-white text-sm font-semibold hover:bg-brand-deep disabled:opacity-40 transition-colors"
            >
              {decide.isPending ? "적용 중…" : "다음 날부터 적용"}
            </button>
            <button
              type="button"
              onClick={() => {
                if (
                  window.confirm(
                    `폐업하면 보증금 ${won(data.depositKrw)}은 돌려받지만 인테리어 ${won(
                      data.interiorKrw,
                    )}은 회수되지 않습니다. 폐업할까요?`,
                  )
                ) {
                  close.mutate();
                }
              }}
              disabled={decide.isPending || close.isPending}
              className="h-10 px-4 rounded-xl border border-border text-sm font-medium hover:bg-black/[0.03] disabled:opacity-40 transition-colors"
            >
              {close.isPending ? "폐업 중…" : "폐업"}
            </button>
          </div>
          <p className="mt-2 text-[11px] text-foreground-muted">
            변경은 <b>다음 게임일부터</b> 적용됩니다 — 지나간 날의 매출은 그때의 결정으로
            계산되어 바뀌지 않습니다. 조정은 게임 1일에 한 번이며, 시설은 줄일 수 없습니다
            (인테리어비는 회수되지 않습니다).
          </p>
          {actionError && (
            <p className="mt-2 rounded-xl bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
              {actionError.message}
            </p>
          )}
          {decide.isSuccess && !actionError && (
            <p className="mt-2 rounded-xl bg-brand/8 border border-brand/20 px-3 py-2 text-xs">
              {decide.data.effectiveFromDay}일차부터 적용됩니다
              {decide.data.interiorCostKrw > 0 &&
                ` · 시설 ${decide.data.facilityAdded}점 추가에 ${won(decide.data.interiorCostKrw)}`}
            </p>
          )}
        </form>
      )}

      <div className="mt-5 grid gap-4 sm:grid-cols-3">
        <BucketRow title="오늘 손님 — 연령" buckets={data.customersByAge} />
        <BucketRow title="시간대" buckets={data.customersByHour} />
        <BucketRow title="성향" buckets={data.customersByTaste} />
      </div>

      <div className="mt-5 overflow-x-auto">
        <table className="w-full text-xs tabular-nums">
          <thead>
            <tr className="text-foreground-muted text-left">
              <th className="font-normal py-1 pr-3">게임일</th>
              <th className="font-normal py-1 pr-3 text-right">매출</th>
              <th className="font-normal py-1 pr-3 text-right">손님</th>
              <th className="font-normal py-1 pr-3 text-right">비용 합계</th>
              <th className="font-normal py-1 text-right">순익</th>
            </tr>
          </thead>
          <tbody>
            {[...data.rows].reverse().map((r) => (
              <tr key={r.gameDay} className="border-t border-border">
                <td className="py-1.5 pr-3">{r.gameDay}일</td>
                <td className="py-1.5 pr-3 text-right">{r.simulatedSalesKrw.toLocaleString()}</td>
                <td className="py-1.5 pr-3 text-right text-foreground-muted">
                  {r.simulatedCustomerCount}/{r.capacityCustomerCount}
                </td>
                <td
                  className="py-1.5 pr-3 text-right text-foreground-muted"
                  // 공과금을 빼면 매출 − 비용이 순익과 맞지 않는다
                  title={`임대 ${r.assumedRentKrw.toLocaleString()} · 인건 ${r.assumedLaborKrw.toLocaleString()} · 원가 ${r.assumedCogsKrw.toLocaleString()} · 공과금 ${r.assumedUtilityKrw.toLocaleString()}`}
                >
                  {(
                    r.assumedRentKrw +
                    r.assumedLaborKrw +
                    r.assumedCogsKrw +
                    r.assumedUtilityKrw
                  ).toLocaleString()}
                </td>
                <td className={`py-1.5 text-right font-medium ${toneOf(r.profitKrw)}`}>
                  {r.profitKrw >= 0 ? "+" : ""}
                  {r.profitKrw.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
