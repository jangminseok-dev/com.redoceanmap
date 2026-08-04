"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, Download, Target, TrendingUp } from "lucide-react";
import {
  downloadCsv,
  fetchAdminForecasts,
  type AdminForecastSnapshot,
} from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import Empty from "@/components/admin/Empty";
import Kpi from "@/components/admin/Kpi";

const SIGNAL_LABEL: Record<string, string> = {
  sentiment: "뉴스 감성",
  rsi: "RSI",
  trend: "MA 추세",
  bollinger: "볼린저 %B",
  obv: "OBV",
  momentum: "12-1 모멘텀",
};

const DIRECTION_LABEL: Record<string, string> = { UP: "상승", DOWN: "하락", NEUTRAL: "관망" };

const REGIME_LABEL: Record<string, string> = {
  BULL: "강세장",
  BEAR: "약세장",
  HIGH_VOL: "고변동",
  NONE: "미상",
};

const HORIZON_OPTIONS = [
  { value: null, label: "전체" },
  { value: 5, label: "5일" },
  { value: 20, label: "20일" },
];

const pct = (v: number | null, digits = 1) =>
  v == null ? "—" : `${(v * 100).toFixed(digits)}%`;

const signedPct = (v: number | null) =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;

export default function ForecastsPage() {
  // 필터 상태 — 단일 객체 패턴 (REACT_RULES)
  const [filter, setFilter] = useState<{ horizon: number | null }>({ horizon: null });

  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-forecasts", filter.horizon],
    queryFn: () => fetchAdminForecasts(filter.horizon, 50),
  });

  const exportCsv = (rows: AdminForecastSnapshot[]) =>
    downloadCsv(
      "forecast_snapshots.csv",
      ["티커", "기준일", "호라이즌", "방향", "레짐", "어닝veto", "기준가", "점수", "과거상승비율", "채점일", "실현수익률", "적중"],
      rows.map((r) => [
        r.ticker,
        r.as_of.slice(0, 10),
        r.horizon_days,
        r.direction,
        r.regime ?? "",
        r.earnings_veto ? "O" : "",
        r.base_price,
        r.score.toFixed(3),
        r.up_rate == null ? "" : r.up_rate.toFixed(3),
        r.evaluated_at?.slice(0, 10) ?? "",
        r.realized_return_pct == null ? "" : (r.realized_return_pct * 100).toFixed(2),
        r.hit == null ? "" : r.hit ? "O" : "X",
      ]),
    );

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">예측 채점</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            일일 예측 스냅샷의 사후 채점 현황 — 방향·신호별 실측 적중률
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-full border border-border bg-surface p-1">
          {HORIZON_OPTIONS.map((opt) => (
            <button
              key={opt.label}
              type="button"
              onClick={() => setFilter({ horizon: opt.value })}
              className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors ${
                filter.horizon === opt.value
                  ? "bg-brand text-white"
                  : "text-foreground-muted hover:text-foreground"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {isPending && <BlockSkeleton rows={6} />}
      {isError && (
        <section className="rounded-2xl bg-surface border border-border">
          <Empty msg="예측 채점 현황을 불러오지 못했습니다." />
        </section>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <Kpi icon={CheckCircle2} label="채점 완료" value={data.kpi.scored.toLocaleString()} sub={`전체 ${data.kpi.total.toLocaleString()}건`} />
            <Kpi icon={Clock} label="채점 대기" value={data.kpi.pending.toLocaleString()} sub="horizon 미도래" />
            <Kpi icon={Target} label="전체 적중률" value={pct(data.kpi.hit_rate)} sub="UP·DOWN만" />
            <Kpi icon={TrendingUp} label="UP 적중률" value={pct(data.kpi.up_hit_rate)} sub={`DOWN ${pct(data.kpi.down_hit_rate)}`} />
          </div>

          <div className="grid lg:grid-cols-2 gap-4">
            <StatTable
              title="방향별"
              headers={["방향", "채점", "적중률", "평균 실현수익률"]}
              rows={data.by_direction.map((d) => [
                DIRECTION_LABEL[d.direction] ?? d.direction,
                d.scored.toLocaleString(),
                pct(d.hit_rate),
                signedPct(d.avg_realized_return_pct),
              ])}
              empty="채점 완료된 스냅샷이 없습니다."
            />
            <StatTable
              title="신호별 방향 일치율"
              headers={["신호", "표본", "일치", "일치율"]}
              rows={data.by_signal.map((s) => [
                SIGNAL_LABEL[s.key] ?? s.key,
                s.n.toLocaleString(),
                s.hits.toLocaleString(),
                pct(s.hit_rate),
              ])}
              empty="신호 표본이 아직 없습니다."
            />
            <StatTable
              title="레짐별 (캡처 시점 시장 국면)"
              headers={["레짐", "채점", "적중률", "평균 실현수익률"]}
              rows={data.by_regime.map((r) => [
                REGIME_LABEL[r.regime] ?? r.regime,
                r.scored.toLocaleString(),
                pct(r.hit_rate),
                signedPct(r.avg_realized_return_pct),
              ])}
              empty="채점 완료된 스냅샷이 없습니다."
            />
          </div>

          <section className="rounded-2xl bg-surface border border-border overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-border">
              <h2 className="text-sm font-semibold">최근 스냅샷 (50건)</h2>
              <button
                type="button"
                onClick={() => exportCsv(data.recent)}
                disabled={data.recent.length === 0}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border border-border text-foreground-muted hover:text-foreground hover:bg-accent transition-colors disabled:opacity-40"
              >
                <Download size={13} /> CSV
              </button>
            </div>
            {data.recent.length === 0 ? (
              <Empty msg="아직 저장된 스냅샷이 없습니다. cron(snapshot_forecasts.py) 첫 실행을 기다려 주세요." />
            ) : (
              <>
                <div className="hidden sm:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-foreground-muted border-b border-border bg-background/60">
                        <th className="font-medium px-5 py-2.5">티커</th>
                        <th className="font-medium px-4 py-2.5">기준일</th>
                        <th className="font-medium px-4 py-2.5 text-right">호라이즌</th>
                        <th className="font-medium px-4 py-2.5">방향</th>
                        <th className="font-medium px-4 py-2.5">레짐</th>
                        <th className="font-medium px-4 py-2.5 text-right">과거 상승비율</th>
                        <th className="font-medium px-4 py-2.5 text-right">실현 수익률</th>
                        <th className="font-medium px-5 py-2.5 text-right">적중</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent.map((r) => (
                        <tr
                          key={`${r.ticker}-${r.horizon_days}-${r.as_of}`}
                          className="border-b border-border last:border-0 hover:bg-background/40"
                        >
                          <td className="px-5 py-3 font-medium">{r.ticker}</td>
                          <td className="px-4 py-3 text-foreground-muted tabular-nums">{r.as_of.slice(0, 10)}</td>
                          <td className="px-4 py-3 text-right text-foreground-muted tabular-nums">{r.horizon_days}일</td>
                          <td className="px-4 py-3">
                            <DirectionBadge direction={r.direction} />
                            {r.earnings_veto && (
                              <span className="ml-1 inline-flex px-1.5 py-0.5 rounded-full text-[10px] bg-amber-50 text-amber-700">
                                어닝
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-xs text-foreground-muted">
                            {r.regime ? REGIME_LABEL[r.regime] ?? r.regime : "—"}
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">
                            {r.up_rate == null ? "—" : `${(r.up_rate * 100).toFixed(1)}%`}
                            {r.ready && <span className="ml-1 text-[10px] text-emerald-600 font-medium">ready</span>}
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">{signedPct(r.realized_return_pct)}</td>
                          <td className="px-5 py-3 text-right"><HitBadge hit={r.hit} evaluated={r.evaluated_at != null} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="sm:hidden divide-y divide-border">
                  {data.recent.map((r) => (
                    <div key={`${r.ticker}-${r.horizon_days}-${r.as_of}`} className="px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium text-sm">{r.ticker}</span>
                        <HitBadge hit={r.hit} evaluated={r.evaluated_at != null} />
                      </div>
                      <p className="mt-1 text-xs text-foreground-muted tabular-nums">
                        {r.as_of.slice(0, 10)} · {r.horizon_days}일 · {DIRECTION_LABEL[r.direction] ?? r.direction}
                        {" · 실현 "}{signedPct(r.realized_return_pct)}
                      </p>
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function StatTable({
  title,
  headers,
  rows,
  empty,
}: {
  title: string;
  headers: string[];
  rows: (string | number)[][];
  empty: string;
}) {
  return (
    <section className="rounded-2xl bg-surface border border-border overflow-hidden">
      <h2 className="px-5 py-3 text-sm font-semibold border-b border-border">{title}</h2>
      {rows.length === 0 ? (
        <Empty msg={empty} />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-foreground-muted border-b border-border bg-background/60">
              {headers.map((h, i) => (
                <th key={h} className={`font-medium px-5 py-2.5 ${i > 0 ? "text-right" : ""}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((cells, ri) => (
              <tr key={ri} className="border-b border-border last:border-0">
                {cells.map((c, ci) => (
                  <td key={ci} className={`px-5 py-2.5 tabular-nums ${ci > 0 ? "text-right text-foreground-muted" : "font-medium"}`}>
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function DirectionBadge({ direction }: { direction: string }) {
  const style =
    direction === "UP"
      ? "bg-emerald-50 text-emerald-700"
      : direction === "DOWN"
        ? "bg-rose-50 text-rose-700"
        : "bg-foreground/5 text-foreground-muted";
  return (
    <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${style}`}>
      {DIRECTION_LABEL[direction] ?? direction}
    </span>
  );
}

function HitBadge({ hit, evaluated }: { hit: boolean | null; evaluated: boolean }) {
  if (!evaluated) {
    return <span className="text-xs text-foreground-muted">대기</span>;
  }
  if (hit == null) {
    return <span className="text-xs text-foreground-muted">관망(제외)</span>;
  }
  return (
    <span
      className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${
        hit ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
      }`}
    >
      {hit ? "적중" : "빗나감"}
    </span>
  );
}
