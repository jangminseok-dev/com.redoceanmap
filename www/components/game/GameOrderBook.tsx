"use client";

import { TriangleAlert } from "lucide-react";
import type { GameOrderBook as Book } from "@/lib/types";

const UP = "#DC2626";
const DOWN = "#2563EB";

const LIMIT_LABEL: Record<string, { text: string; tone: string }> = {
  upper: { text: "상한가", tone: "text-[#DC2626]" },
  lower: { text: "하한가", tone: "text-[#2563EB]" },
  none: { text: "", tone: "" },
};

/**
 * 호가창 — 매도 10단계 / 매수 10단계.
 *
 * 게임에 다른 참가자의 실제 주문이 없으므로 잔량은 유동성 모형이 만든 **가정치**다.
 * 다만 매매가 실제로 이 호가를 걷어올리며 체결되므로(슬리피지), 보여주는 값과 체결가가
 * 같은 곳에서 나온다 — 화면과 체결이 다른 호가창을 쓰면 유저가 속았다고 느낀다.
 */
export default function GameOrderBook({ book }: { book: Book }) {
  const maxQty = Math.max(
    ...book.bids.map((q) => q.assumedQuantity),
    ...book.asks.map((q) => q.assumedQuantity),
    1,
  );
  const limit = LIMIT_LABEL[book.limitState] ?? LIMIT_LABEL.none;

  const Row = ({ price, qty, side }: { price: number; qty: number; side: "bid" | "ask" }) => (
    <div className="relative flex items-center justify-between px-2 py-[3px] text-[11px] tabular-nums">
      <span
        className="absolute inset-y-0 right-0 opacity-[0.10]"
        style={{ width: `${(qty / maxQty) * 100}%`, background: side === "ask" ? DOWN : UP }}
      />
      <span className="relative" style={{ color: side === "ask" ? DOWN : UP }}>
        {price.toLocaleString()}
      </span>
      <span className="relative text-foreground-muted">{qty.toLocaleString()}</span>
    </div>
  );

  return (
    <section className="rounded-2xl border border-border bg-surface p-4">
      <div className="flex items-baseline gap-2">
        <h3 className="text-sm font-bold tracking-tight">호가</h3>
        {limit.text && <span className={`text-xs font-bold ${limit.tone}`}>{limit.text}</span>}
        <span className="ml-auto text-[11px] text-foreground-muted tabular-nums">
          호가단위 {book.tickSizeKrw.toLocaleString()}원 · 스프레드{" "}
          {book.spreadKrw.toLocaleString()}원
        </span>
      </div>

      {book.halted && (
        <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-amber-50 border border-amber-200 px-2.5 py-1.5 text-[11px] text-amber-800">
          <TriangleAlert size={12} strokeWidth={2} className="mt-0.5 shrink-0" />
          변동성 완화장치(VI)가 발동해 지금은 매매할 수 없습니다.
        </p>
      )}

      <div className="mt-3 rounded-xl border border-border overflow-hidden">
        {/* 매도는 먼 호가가 위 — 실제 호가창과 같은 순서 */}
        {[...book.asks].reverse().map((q) => (
          <Row key={`a${q.priceKrw}`} price={q.priceKrw} qty={q.assumedQuantity} side="ask" />
        ))}
        <div className="border-y border-border bg-black/[0.03] px-2 py-1 text-[10px] text-foreground-muted">
          현재가 기준 · 잔량은 게임 규칙 산출 가정치입니다
        </div>
        {book.bids.map((q) => (
          <Row key={`b${q.priceKrw}`} price={q.priceKrw} qty={q.assumedQuantity} side="bid" />
        ))}
      </div>

      <p className="mt-2.5 text-[11px] text-foreground-muted">
        공매도 잔고{" "}
        <span className="font-medium tabular-nums text-foreground">
          {book.shortInterestPct.toFixed(2)}%
        </span>{" "}
        (발행주식 대비) · 큰 주문은 호가를 걷어올리며 체결돼 평균 체결가가 불리해집니다.
      </p>
    </section>
  );
}
