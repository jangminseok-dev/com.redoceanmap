import type { PaperPosition } from "@/lib/types";
import { fmtKrw, fmtPct } from "./format";

/** 지갑 — 보유 종목 카드. 손익률이 주인공이고 나머지는 작은 글씨다. */
export default function HoldingsGrid({ positions, empty }: { positions: PaperPosition[]; empty: string }) {
  if (positions.length === 0) return <p className="text-sm text-foreground-muted">{empty}</p>;
  return (
    <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
      {positions.map((p) => {
        const up = (p.unrealized_pct ?? 0) >= 0;
        return (
          <li key={`${p.ticker}-${p.side}`} className="rounded-xl border border-border bg-surface p-3">
            <div className="flex items-center gap-1.5">
              <span className="font-semibold">{p.ticker}</span>
              <span className={`inline-flex px-1.5 py-0.5 rounded-full text-[11px] ${p.side === "LONG" ? "text-up bg-up-weak" : "text-down bg-down-weak"}`}>
                {p.side === "LONG" ? "롱" : "숏"}
              </span>
            </div>
            <p className="text-xs text-foreground-muted truncate">{p.name}</p>
            <p className={`mt-2 text-xl font-bold tabular-nums ${p.unrealized_pct == null ? "text-foreground-muted" : up ? "text-up" : "text-down"}`}>
              {fmtPct(p.unrealized_pct)}
            </p>
            <p className="text-xs text-foreground-muted tabular-nums">{p.quantity.toLocaleString("ko-KR")}주 · {fmtKrw(p.value_krw)}</p>
          </li>
        );
      })}
    </ul>
  );
}
