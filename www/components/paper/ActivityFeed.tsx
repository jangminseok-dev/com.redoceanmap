"use client";

import type { PaperDecision, PaperTrade } from "@/lib/types";
import { ACTION_LABEL, ACTION_TONE, fmtDay, fmtKrw, fmtPrice } from "./format";

const VERB: Record<string, string> = { BUY: "샀어요", SELL: "팔았어요", SHORT: "숏 쳤어요", COVER: "숏을 닫았어요" };

type Item =
  | { kind: "fill"; trade: PaperTrade }
  | { kind: "pending"; ticker: string; action: string; reason: string; as_of: string };

/**
 * AI가 한 일 — 최근 체결(사실)과 아직 체결 안 된 오늘 판단(대기)을 시간 역순 카드로.
 * 문형은 "샀어요/팔았어요"까지다 — 권유가 아니라 기록이다.
 */
export default function ActivityFeed({
  trades,
  latest,
  limit = 6,
}: {
  trades: PaperTrade[];
  latest: PaperDecision | null;
  limit?: number;
}) {
  const filledTickers = new Set((latest?.fills ?? []).map((f) => `${f.ticker}:${f.action}`));
  const pending: Item[] = (latest?.orders ?? [])
    .filter((o) => !filledTickers.has(`${o.ticker}:${o.action}`))
    .map((o) => ({ kind: "pending", ticker: o.ticker, action: o.action, reason: o.reason, as_of: latest!.as_of }));
  const fills: Item[] = [...trades]
    .sort((a, b) => b.ts.localeCompare(a.ts))
    .slice(0, limit)
    .map((t) => ({ kind: "fill", trade: t }));
  const items = [...pending, ...fills].slice(0, limit + pending.length);

  if (items.length === 0) return <p className="text-sm text-foreground-muted">아직 사고판 기록이 없어요.</p>;

  return (
    <ul className="space-y-2">
      {items.map((it, i) => {
        if (it.kind === "pending") {
          return (
            <li key={`p-${i}`} className="rounded-xl border border-dashed border-border bg-surface p-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${ACTION_TONE[it.action]}`}>{ACTION_LABEL[it.action]}</span>
                <span className="font-semibold">{it.ticker}</span>
                <span className="text-foreground-muted">다음 장 열리면 체결돼요</span>
                <span className="ml-auto text-xs text-foreground-muted">{fmtDay(it.as_of)} 판단</span>
              </div>
              {it.reason && <p className="mt-1 text-xs text-foreground-muted leading-relaxed line-clamp-2">{it.reason}</p>}
            </li>
          );
        }
        const t = it.trade;
        return (
          <li key={t.id} className="rounded-xl border border-border bg-surface p-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${ACTION_TONE[t.action]}`}>{ACTION_LABEL[t.action]}</span>
              <span className="font-semibold">{t.ticker}</span>
              <span className="tabular-nums">{t.quantity.toLocaleString("ko-KR")}주 {VERB[t.action]}</span>
              <span className="text-xs text-foreground-muted tabular-nums">@ {fmtPrice(t.price, t.ticker)}</span>
              {t.realized_pnl_krw != null && (
                <span className={`tabular-nums font-medium ${t.realized_pnl_krw >= 0 ? "text-up" : "text-down"}`}>
                  {t.realized_pnl_krw >= 0 ? "+" : ""}{fmtKrw(t.realized_pnl_krw)}
                </span>
              )}
              <span className="ml-auto text-xs text-foreground-muted">{fmtDay(t.ts)}</span>
            </div>
            {t.reason && <p className="mt-1 text-xs text-foreground-muted leading-relaxed line-clamp-2">{t.reason}</p>}
          </li>
        );
      })}
    </ul>
  );
}
