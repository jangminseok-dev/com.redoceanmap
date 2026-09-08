"use client";

import type { PaperBoard } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { fmtKrw, fmtPct } from "./format";

/** 성적표 — 계정 하나에 숫자 하나. 게임 점수판처럼 읽힌다. */
export default function ScoreBoard({
  board,
  myKey,
  onJoin,
}: {
  board: PaperBoard;
  myKey: string | null; // user:<id> — 비로그인은 null
  onJoin: () => void;
}) {
  const find = (key: string) => board.rows.find((r) => r.key === key);
  const exaone = find("exaone");
  const signal = find("signal");
  const me = myKey ? find(myKey) : undefined;
  const spy = board.spy[board.spy.length - 1];
  const spyReturn = spy ? spy.equity_krw / board.rules.assumed_initial_cash_krw - 1 : null;

  const tile = (label: string, sub: string, ret: number | null | undefined, equity: number | null | undefined, accent: string) => (
    <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <p className="text-xs text-foreground-muted">{sub}</p>
      <p className="mt-0.5 text-base font-semibold">{label}</p>
      <p className={`mt-2 text-3xl font-bold tracking-tight tabular-nums ${ret == null ? "text-foreground-muted" : ret >= 0 ? "text-up" : "text-down"} ${accent}`}>
        {ret == null ? "—" : fmtPct(ret, 2)}
      </p>
      <p className="mt-1 text-xs text-foreground-muted tabular-nums">{equity == null ? "아직 기록 없음" : fmtKrw(equity)}</p>
    </div>
  );

  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {tile("EXAONE", "AI가 직접 판단", exaone?.return_pct, exaone?.equity_krw, "")}
        {tile("지표 규칙", "검증된 신호만 따라감", signal?.return_pct, signal?.equity_krw, "")}
        {me ? (
          tile("나", "같은 돈, 같은 규칙", me.return_pct, me.equity_krw, "")
        ) : (
          <div className="rounded-2xl border border-dashed border-border bg-surface p-4 sm:p-5 flex flex-col">
            <p className="text-xs text-foreground-muted">같은 돈, 같은 규칙</p>
            <p className="mt-0.5 text-base font-semibold">나</p>
            <p className="mt-2 text-sm text-foreground-muted leading-relaxed">1억원으로 시작해 AI와 성적을 겨룹니다.</p>
            <Button size="md" className="mt-auto self-start" onClick={onJoin}>참가하기</Button>
          </div>
        )}
      </div>
      <p className="mt-2 text-xs text-foreground-muted tabular-nums">
        같은 기간 SPY를 사서 들고만 있었다면 {fmtPct(spyReturn, 2)} · 모두 초기 자본 {(board.rules.assumed_initial_cash_krw / 1e8).toFixed(0)}억원 · 실제 돈이 아닙니다
      </p>
    </div>
  );
}
