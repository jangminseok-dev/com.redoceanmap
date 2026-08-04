"use client";

import { TriangleAlert } from "lucide-react";
import type { GameOrderBook as Book } from "@/lib/types";

const UP = "#DC2626";
const DOWN = "#2563EB";

const LIMIT_LABEL: Record<string, { text: string; tone: string }> = {
  upper: { text: "상한가", tone: "text-up" },
  lower: { text: "하한가", tone: "text-down" },
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

  const bidSum = book.bids.reduce((sum, q) => sum + q.assumedQuantity, 0);
  const askSum = book.asks.reduce((sum, q) => sum + q.assumedQuantity, 0);
  // 잔량이 0이면(시즌 시작 전 등) 50:50으로 둔다 — 0으로 나누지 않기 위해서다
  const bidPct = bidSum + askSum === 0 ? 50 : Math.round((bidSum / (bidSum + askSum)) * 100);

  const Row = ({ price, qty, side }: { price: number; qty: number; side: "bid" | "ask" }) => (
    <div className="relative flex items-center justify-between px-2 py-[3px] text-xs tabular-nums">
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
        <span className="ml-auto text-xs text-foreground-muted tabular-nums">
          호가단위 {book.tickSizeKrw.toLocaleString()}원 · 스프레드{" "}
          {book.spreadKrw.toLocaleString()}원
        </span>
      </div>

      {book.halted && (
        <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-amber-50 border border-amber-200 px-2.5 py-1.5 text-xs text-amber-800">
          <TriangleAlert size={12} strokeWidth={2} className="mt-0.5 shrink-0" />
          변동성 완화장치(VI)가 발동해 지금은 매매할 수 없습니다.
        </p>
      )}

      {/* 매수·매도 잔량 비율 — 10단계를 세로로 훑지 않아도 어느 쪽이 두꺼운지 한눈에 보인다
          (레퍼런스 토스증권 테이블의 이중 막대와 같은 형태). 같은 잔량에서 뽑으므로
          아래 호가창과 항상 일치한다. */}
      <div className="mt-3">
        <div className="flex items-center justify-between text-xs font-semibold tabular-nums">
          <span className="text-up">매수 {bidPct}</span>
          <span className="text-down">{100 - bidPct} 매도</span>
        </div>
        <div className="mt-1 flex h-1.5 rounded-full overflow-hidden">
          <div className="bg-up" style={{ width: `${bidPct}%` }} />
          <div className="bg-down flex-1" />
        </div>
      </div>

      <div className="mt-3 rounded-xl border border-border overflow-hidden">
        {/* 매도는 먼 호가가 위 — 실제 호가창과 같은 순서 */}
        {[...book.asks].reverse().map((q) => (
          <Row key={`a${q.priceKrw}`} price={q.priceKrw} qty={q.assumedQuantity} side="ask" />
        ))}
        <div className="border-y border-border bg-black/[0.03] px-2 py-1 text-xs text-foreground-muted">
          현재가 기준 · 잔량은 게임 규칙 산출 가정치입니다
        </div>
        {book.bids.map((q) => (
          <Row key={`b${q.priceKrw}`} price={q.priceKrw} qty={q.assumedQuantity} side="bid" />
        ))}
      </div>

      <p className="mt-2.5 text-xs text-foreground-muted">
        공매도 잔고{" "}
        <span className="font-medium tabular-nums text-foreground">
          {book.shortInterestPct.toFixed(2)}%
        </span>{" "}
        (발행주식 대비) · 큰 주문은 호가를 걷어올리며 체결돼 평균 체결가가 불리해집니다.
      </p>
    </section>
  );
}
