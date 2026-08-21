"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, SlidersHorizontal } from "lucide-react";
import {
  fetchAdminForecastRefit,
  type AdminRefitBoard,
  type AdminRefitCandidate,
  type AdminSignalConfig,
} from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import Empty from "@/components/admin/Empty";
import Kpi from "@/components/admin/Kpi";

// 리더보드 표시 상한 — 32조합 전부 늘어놓으면 상위 비교라는 목적이 묻힌다
const BOARD_ROWS_LIMIT = 10;

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const weights = (c: AdminRefitCandidate) =>
  [
    ["RSI", c.w_rsi],
    ["추세", c.w_trend],
    ["BB", c.w_bb],
    ["OBV", c.w_obv],
    ["MOM", c.w_momentum],
  ]
    .filter(([, w]) => (w as number) > 0)
    .map(([k, w]) => `${k} ${w}`)
    .join(" · ");

export default function ForecastRefitPage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-forecast-refit"],
    queryFn: fetchAdminForecastRefit,
  });

  const report = data?.report ?? null;
  const history = data?.history ?? [];

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight">가중치 재적합</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          동결 원신호 × 실현 수익률로 판정 조합 후보를 매주 재채점 —{" "}
          <span className="font-medium text-foreground">
            게이트(n≥100 + Wilson 하한 &gt; 기준선 + 현행 대비 마진 0.02)
          </span>
          를 통과하면 활성 조합이 자동 교체됩니다.
        </p>
      </div>

      {isPending && <BlockSkeleton rows={6} />}
      {isError && (
        <section className="rounded-2xl bg-surface border border-border">
          <Empty msg="재적합 리포트를 불러오지 못했습니다." />
        </section>
      )}

      {!isPending && !isError && (
        <>
          {report === null ? (
            <section className="rounded-2xl bg-surface border border-border">
              <Empty msg="아직 실행 이력이 없습니다. 매주 토 15:00 배치가 첫 리포트를 남깁니다." />
            </section>
          ) : (
            <>
              <section
                className={`rounded-2xl border px-4 py-3 text-sm ${
                  report.promote
                    ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                    : "bg-surface border-border text-foreground-muted"
                }`}
              >
                <p className="font-medium">
                  {report.promote ? "이번 실행에서 승격이 발화했습니다." : "승격 보류 — 현행 조합 유지."}
                </p>
                {report.reasons.map((r) => (
                  <p key={r} className="mt-0.5">
                    {r}
                  </p>
                ))}
              </section>

              {report.boards.map((board) => (
                <BoardTable
                  key={board.horizon_days}
                  board={board}
                  isGate={board.horizon_days === report.gate_horizon}
                />
              ))}

              <p className="text-xs text-foreground-muted">
                실행 {new Date(report.ran_at).toLocaleString("ko-KR")} · 게이트 지평{" "}
                {report.gate_horizon}일 · 승격 시 채점 요약은 새 조합 기준 0부터 재시작합니다(이력 분리).
              </p>
            </>
          )}

          <HistoryTable rows={history} />
        </>
      )}
    </div>
  );
}

function BoardTable({ board, isGate }: { board: AdminRefitBoard; isGate: boolean }) {
  const rows = board.rows.slice(0, BOARD_ROWS_LIMIT);
  return (
    <section className="rounded-2xl bg-surface border border-border p-4">
      <h2 className="font-semibold">
        {board.horizon_days}일 지평 {isGate ? "(승격 게이트)" : "(참고)"}
      </h2>
      <div className="mt-3 grid grid-cols-2 lg:grid-cols-3 gap-3">
        <Kpi icon={SlidersHorizontal} label="채점 표본" value={board.total.toLocaleString()} />
        <Kpi icon={SlidersHorizontal} label="기준선(상승 비율)" value={pct(board.baseline_up_rate)} />
        <Kpi
          icon={SlidersHorizontal}
          label="현행 하한"
          value={board.current ? pct(board.current.wilson_lower) : "—"}
        />
      </div>
      {rows.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-foreground-muted border-b border-border">
                <th className="text-left font-normal py-1.5">가중치</th>
                <th className="text-right font-normal py-1.5">임계</th>
                <th className="text-right font-normal py-1.5">UP n</th>
                <th className="text-right font-normal py-1.5">적중</th>
                <th className="text-right font-normal py-1.5">Wilson 하한</th>
                <th className="text-right font-normal py-1.5">게이트</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c, i) => (
                <tr
                  key={`${c.up_threshold}-${weights(c)}-${i}`}
                  className="border-b border-border/60 last:border-0"
                >
                  <td className="py-1.5">
                    {weights(c) || "—"}
                    {c.is_current && (
                      <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded-full bg-brand/10 text-brand">
                        현행
                      </span>
                    )}
                  </td>
                  <td className="text-right tabular-nums py-1.5">{c.up_threshold.toFixed(2)}</td>
                  <td className="text-right tabular-nums py-1.5">{c.n.toLocaleString()}</td>
                  <td className="text-right tabular-nums py-1.5">
                    {c.hit_rate != null ? pct(c.hit_rate) : "—"}
                  </td>
                  <td className="text-right tabular-nums py-1.5 font-semibold">
                    {pct(c.wilson_lower)}
                  </td>
                  <td className="text-right py-1.5">
                    {c.gate_passed ? (
                      <CheckCircle2 size={16} className="inline text-emerald-600" />
                    ) : (
                      <span className="text-xs text-foreground-muted">미달</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {board.rows.length > rows.length && (
            <p className="mt-2 text-xs text-foreground-muted">
              상위 {rows.length}개만 표시 (전체 {board.rows.length}조합)
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function HistoryTable({ rows }: { rows: AdminSignalConfig[] }) {
  if (!rows.length) return null;
  return (
    <section className="rounded-2xl bg-surface border border-border p-4">
      <h2 className="font-semibold">판정 조합 이력</h2>
      <p className="text-xs text-foreground-muted mt-0.5">
        승격이 일어날 때마다 행이 쌓입니다 — 스냅샷의 signal_config 스탬프와 같은 키입니다.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-foreground-muted border-b border-border">
              <th className="text-left font-normal py-1.5">키</th>
              <th className="text-left font-normal py-1.5">가중치</th>
              <th className="text-right font-normal py-1.5">임계</th>
              <th className="text-left font-normal py-1.5">출처</th>
              <th className="text-right font-normal py-1.5">활성화</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-b border-border/60 last:border-0">
                <td className="py-1.5 font-mono text-xs">
                  {r.key}
                  {r.is_active && (
                    <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded-full bg-brand/10 text-brand font-sans">
                      활성
                    </span>
                  )}
                </td>
                <td className="py-1.5">
                  {weights({
                    ...r,
                    n: 0,
                    hits: 0,
                    hit_rate: null,
                    wilson_lower: 0,
                    is_current: false,
                    gate_passed: false,
                  })}
                </td>
                <td className="text-right tabular-nums py-1.5">{r.up_threshold.toFixed(2)}</td>
                <td className="py-1.5">{r.source === "seed" ? "시드" : "재적합"}</td>
                <td className="text-right tabular-nums py-1.5 text-foreground-muted">
                  {r.activated_at ? new Date(r.activated_at).toLocaleDateString("ko-KR") : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
