import type { PaperTrade } from "@/lib/types";
import { ACTION_LABEL, ACTION_TONE, fmtDay, fmtKrw, fmtPrice } from "./format";

export default function TradeLog({ trades, limit = 30 }: { trades: PaperTrade[]; limit?: number }) {
  if (trades.length === 0) return <p className="text-sm text-foreground-muted">체결 기록이 없습니다.</p>;
  const recent = [...trades].sort((a, b) => b.ts.localeCompare(a.ts)).slice(0, limit);
  return (
    <ul className="divide-y divide-border">
      {recent.map((t) => (
        <li key={t.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
          <span className="w-12 shrink-0 text-xs text-foreground-muted tabular-nums">{fmtDay(t.ts)}</span>
          <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${ACTION_TONE[t.action]}`}>{ACTION_LABEL[t.action]}</span>
          <span className="font-medium">{t.ticker}</span>
          <span className="tabular-nums text-foreground-muted">{fmtPrice(t.price, t.ticker)} × {t.quantity.toLocaleString("ko-KR")}주</span>
          {t.realized_pnl_krw != null && (
            <span className={`ml-auto tabular-nums ${t.realized_pnl_krw >= 0 ? "text-up" : "text-down"}`}>
              {t.realized_pnl_krw >= 0 ? "+" : ""}{fmtKrw(t.realized_pnl_krw)}
            </span>
          )}
          {t.reason && <span className="basis-full text-xs text-foreground-muted leading-relaxed">{t.reason}</span>}
        </li>
      ))}
    </ul>
  );
}
