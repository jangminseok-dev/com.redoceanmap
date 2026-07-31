"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchGameStoreDaily } from "@/lib/api";
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

/** 가게 현황 — 누적 손익, 최근 일별 내역, 오늘 온 손님 구성. */
export default function StoreDetailCard({ storeId }: { storeId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["game-store", storeId],
    queryFn: () => fetchGameStoreDaily(storeId, 14),
    refetchInterval: (query) => (query.state.status === "error" ? 300_000 : 30_000),
  });

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
              <th className="font-normal py-1 pr-3 text-right">임대·인건·원가</th>
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
                <td className="py-1.5 pr-3 text-right text-foreground-muted">
                  {(r.assumedRentKrw + r.assumedLaborKrw + r.assumedCogsKrw).toLocaleString()}
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
