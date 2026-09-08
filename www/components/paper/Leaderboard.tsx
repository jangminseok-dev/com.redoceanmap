"use client";

import type { PaperBoard } from "@/lib/types";
import { KIND_LABEL, fmtKrw, fmtPct } from "./format";

/** 리더보드 — 수익률순. SPY 보유는 계정이 아니라 기준선이라 표 마지막에 따로 둔다. */
export default function Leaderboard({
  board,
  selected,
  onSelect,
}: {
  board: PaperBoard;
  selected: string;
  onSelect: (key: string) => void;
}) {
  const spyLast = board.spy[board.spy.length - 1];
  const spyReturn = spyLast ? spyLast.equity_krw / board.rules.assumed_initial_cash_krw - 1 : null;

  return (
    <div className="rounded-2xl border border-border bg-surface overflow-hidden">
      <div className="flex items-baseline gap-2 px-4 py-3 border-b border-border">
        <h2 className="text-sm font-semibold">리더보드</h2>
        <span className="text-xs text-foreground-muted">수익률순 · 일 1회 평가 · 계정을 누르면 곡선과 기록이 바뀝니다</span>
      </div>
      <ul className="divide-y divide-border">
        {board.rows.map((r, i) => (
          <li key={r.key}>
            <button
              type="button"
              onClick={() => onSelect(r.key)}
              aria-pressed={selected === r.key}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors hover:bg-accent ${
                selected === r.key ? "bg-accent" : ""
              }`}
            >
              <span className="w-5 shrink-0 text-xs text-foreground-muted tabular-nums">{i + 1}</span>
              <span className="flex-1 min-w-0">
                <span className="font-medium">{r.label}</span>
                <span className="ml-1.5 text-xs text-foreground-muted">{KIND_LABEL[r.kind] ?? r.kind}</span>
                {r.kind === "exaone" && (
                  <span className="ml-1.5 inline-flex px-1.5 py-0.5 rounded-full bg-border/40 text-[11px] text-foreground-muted">
                    검증되지 않은 판단
                  </span>
                )}
              </span>
              <span className={`w-20 shrink-0 text-right tabular-nums font-semibold ${r.return_pct >= 0 ? "text-up" : "text-down"}`}>
                {fmtPct(r.return_pct, 2)}
              </span>
              <span className="hidden sm:block w-24 shrink-0 text-right tabular-nums text-foreground-muted">
                {fmtKrw(r.equity_krw)}
              </span>
              <span className="hidden md:block w-24 shrink-0 text-right text-xs text-foreground-muted tabular-nums">
                보유 {r.open_positions} · 거래 {r.trades}
              </span>
            </button>
          </li>
        ))}
        {spyLast && (
          <li className="flex items-center gap-3 px-4 py-2.5 text-sm text-foreground-muted">
            <span className="w-5 shrink-0 text-xs">—</span>
            <span className="flex-1">SPY 매수보유 <span className="text-xs">기준선</span></span>
            <span className={`w-20 shrink-0 text-right tabular-nums font-semibold ${(spyReturn ?? 0) >= 0 ? "text-up" : "text-down"}`}>
              {fmtPct(spyReturn, 2)}
            </span>
            <span className="hidden sm:block w-24 shrink-0 text-right tabular-nums">{fmtKrw(spyLast.equity_krw)}</span>
            <span className="hidden md:block w-24 shrink-0" />
          </li>
        )}
      </ul>
    </div>
  );
}
