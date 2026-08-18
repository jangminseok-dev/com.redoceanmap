"use client";

import { Minus, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";
import type { StockAnalyzeResult } from "@/lib/types";
import { formatPrice } from "@/lib/currency";
import { strength } from "@/lib/verdict";
import SymbolMark from "@/components/common/SymbolMark";

type Props = {
  symbol: string;
  resolvedTicker?: string;
  analyze?: StockAnalyzeResult;
  isLoading: boolean;
  quotePrice?: number | null; // 30초 폴링 현재가(지연 시세) — 있으면 분석 시점 가격보다 우선
  previousClose?: number | null; // 전일 종가 — 등락률 기준
  asOfLabel?: string | null; // 기준 시점("8월 14일 19:59 기준") — 페이지가 quote 수신 시각으로 만든다
};

const DIRECTION_META = {
  UP: { label: "상승 신호", icon: TrendingUp, className: "text-up bg-up-weak border-up/20" },
  DOWN: { label: "하락 신호", icon: TrendingDown, className: "text-down bg-down-weak border-down/20" },
  NEUTRAL: { label: "중립", icon: Minus, className: "text-foreground-muted bg-surface border-border" },
} as const;

/**
 * 종목 헤더 — 1줄이다(레퍼런스 토스 종목 헤더).
 *
 * 예전에는 이 컴포넌트가 헤더 + AI 결론 카드 + 근거 2열까지 세로로 쌓아 스테이지 위쪽을
 * 절반 넘게 먹었고, 차트가 접혀 내려갔다. 결론·근거는 AiInsightCard로 옮겨 **차트 바로 아래**에
 * 붙는다(토스 "왜 올랐을까?" 자리) — 차트를 본 눈이 바로 아래에서 해설을 만나는 순서가 맞다.
 */
export default function StockHero({
  symbol,
  resolvedTicker,
  analyze,
  isLoading,
  quotePrice,
  previousClose,
  asOfLabel,
}: Props) {
  if (isLoading && !analyze) {
    return (
      <header className="shrink-0 px-4 pt-4 pb-3 border-b border-border">
        <div className="skeleton h-9 w-72 rounded-md" />
      </header>
    );
  }
  if (!analyze) return null;

  const ticker = resolvedTicker ?? symbol;
  const price = quotePrice ?? analyze.price;
  const changePct = previousClose ? (price / previousClose - 1) * 100 : null;
  const changeAmount = previousClose ? price - previousClose : null;
  const meta = DIRECTION_META[analyze.direction] ?? DIRECTION_META.NEUTRAL;
  const DirectionIcon = meta.icon;

  return (
    <header className="shrink-0 px-4 pt-3 pb-2.5 border-b border-border">
      {/* 좁은 폭에서는 flex-wrap이 자연스럽게 [이름 행 / 가격 행] 2줄로 갠다(375px 검증) */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <SymbolMark name={symbol} size="md" />
          <h1 className="text-sm font-bold truncate">{symbol}</h1>
          {ticker !== symbol && (
            <span className="text-xs text-foreground-muted shrink-0">{ticker}</span>
          )}
        </div>

        <div className="flex items-baseline gap-2">
          <span className="text-data-xl tabular-nums">{formatPrice(price, ticker)}</span>
          {changePct !== null && (
            <span className={`text-data-l tabular-nums px-2 py-0.5 rounded-md ${toneBox(changePct)}`}>
              {changePct > 0 ? "+" : ""}
              {changePct.toFixed(2)}%
            </span>
          )}
          {changeAmount !== null && (
            <span
              className={`text-[13px] tabular-nums ${
                changeAmount > 0 ? "text-up" : changeAmount < 0 ? "text-down" : "text-foreground-muted"
              }`}
            >
              {changeAmount > 0 ? "+" : ""}
              {formatPrice(changeAmount, ticker)}
            </span>
          )}
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium ${meta.className}`}
          >
            <DirectionIcon size={12} strokeWidth={2} />
            {meta.label} · {strength(analyze)}
          </span>
          {analyze.reference_up_signal && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-border bg-surface text-xs text-foreground-muted">
              <ShieldCheck size={12} strokeWidth={2} className="text-brand" />
              백테스트 참고
            </span>
          )}
          <span className="text-xs text-foreground-muted tabular-nums">
            {asOfLabel ?? "지연 시세"}
            {quotePrice != null && " · 30초 갱신"}
          </span>
        </div>
      </div>
    </header>
  );
}

// 등락률 배경 하이라이트 — 값이 아니라 값의 방향이 먼저 읽히게 한다(DESIGN.md §2 Direction roles)
function toneBox(v: number) {
  if (v > 0) return "bg-up-weak text-up";
  if (v < 0) return "bg-down-weak text-down";
  return "text-foreground-muted";
}
