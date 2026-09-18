"use client";

import type { PaperBoard } from "@/lib/types";
import { fmtKrw, fmtPct } from "./format";

/** 성적표 — 계정 하나에 숫자 하나. AI 판단 · 지표 규칙(대조군) · 위험 규칙(검증 신호) · SPY 보유(기준선). */
export default function ScoreBoard({ board }: { board: PaperBoard }) {
  const find = (key: string) => board.rows.find((r) => r.key === key);
  const exaone = find("exaone");
  const signal = find("signal");
  const risk = find("risk");   // 2026-09-18 — 검증된 낙폭 위험 신호만 쓰는 계정
  const spy = board.spy[board.spy.length - 1];
  const spyReturn = spy ? spy.equity_krw / board.rules.assumed_initial_cash_krw - 1 : null;
  const lastAsOf = exaone?.last_as_of ?? signal?.last_as_of ?? risk?.last_as_of ?? null;

  const tile = (label: string, sub: string, ret: number | null | undefined, equity: number | null | undefined) => (
    <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <p className="text-xs text-foreground-muted">{sub}</p>
      <p className="mt-0.5 text-base font-semibold">{label}</p>
      <p className={`mt-2 text-3xl font-bold tracking-tight tabular-nums ${ret == null ? "text-foreground-muted" : ret >= 0 ? "text-up" : "text-down"}`}>
        {ret == null ? "—" : fmtPct(ret, 2)}
      </p>
      <p className="mt-1 text-xs text-foreground-muted tabular-nums">{equity == null ? "아직 기록 없음" : fmtKrw(equity)}</p>
    </div>
  );

  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        {tile("AI 판단", "AI가 직접 판단", exaone?.return_pct, exaone?.equity_krw)}
        {tile("지표 규칙(대조군)", "검증 안 된 방향 신호를 그대로", signal?.return_pct, signal?.equity_krw)}
        {tile("위험 규칙(검증 신호)", "낙폭 위험 낮은 종목만 롱", risk?.return_pct, risk?.equity_krw)}
        {tile("SPY 보유", "사서 들고만 있었다면", spyReturn, spy?.equity_krw)}
      </div>
      <p className="mt-2 text-xs text-foreground-muted tabular-nums">
        {lastAsOf ? `${lastAsOf} 평가 기준(주말·휴장일엔 갱신되지 않아요) · ` : ""}모두 초기 자본 {(board.rules.assumed_initial_cash_krw / 1e8).toFixed(0)}억원 · 실제 돈이 아닙니다
      </p>
    </div>
  );
}
