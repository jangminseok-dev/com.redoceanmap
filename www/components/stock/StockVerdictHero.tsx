"use client";

import { Eye, Minus, TrendingDown, TrendingUp } from "lucide-react";
import type { Fundamentals, StockAnalyzeResult, StockForecast } from "@/lib/types";
import { formatPrice } from "@/lib/currency";
import { downsideLine, positionLine, strength, verdict } from "@/lib/verdict";
import Disclaimer from "./Disclaimer";

const DIRECTION_META = {
  UP: { icon: TrendingUp, className: "text-red-600 bg-red-50 border-red-200" },
  DOWN: { icon: TrendingDown, className: "text-blue-600 bg-blue-50 border-blue-200" },
  NEUTRAL: { icon: Minus, className: "text-foreground-muted bg-surface border-border" },
} as const;

const TONE_TEXT: Record<string, string> = {
  positive: "text-red-600",
  warning: "text-blue-600",
  neutral: "text-foreground-muted",
};

// 현재가가 60일 저/고점 구간 어디쯤인지에 따라 "지켜볼 것"을 말한다 — 관측 지시일 뿐 매수 조언이 아니다.
function watchPoint(analyze: StockAnalyzeResult, price: number, symbol: string): string | null {
  const { support, resistance } = analyze;
  if (!(resistance > support)) return null;
  const ratio = Math.max(0, Math.min(1, (price - support) / (resistance - support)));
  const lo = formatPrice(support, symbol);
  const hi = formatPrice(resistance, symbol);
  if (ratio <= 0.25) return `저점권입니다. ${lo}(60일 저점) 이탈 여부를 지켜보세요.`;
  if (ratio >= 0.75) return `고점권입니다. ${hi}(60일 고점) 돌파·유지 여부를 지켜보세요.`;
  return `관심 있으면 ${lo}(60일 저점) 이탈이나 ${hi}(60일 고점) 돌파를 지켜보세요.`;
}

/** 결론 먼저 — 방향 결론 + 신호 세기 + 가치·체력 한 줄 + 지켜볼 포인트를 스테이지 최상단에 모은다.
 *  가치·체력은 펀더멘털 해석(fundamental_narrator)에서 대표 1~2개를 끌어온다(없으면 생략·열화). */
export default function StockVerdictHero({
  symbol,
  price,
  analyze,
  forecast,
  fundamentals,
  expert,
  onToggleExpert,
}: {
  symbol: string;
  price?: number;
  analyze?: StockAnalyzeResult;
  forecast?: StockForecast;
  fundamentals?: Fundamentals;
  expert: boolean;
  onToggleExpert: () => void;
}) {
  if (!analyze) return null;
  const current = price ?? analyze.price;
  const { headline, detail } = verdict(analyze, forecast);
  const meta = DIRECTION_META[analyze.direction] ?? DIRECTION_META.NEUTRAL;
  const Icon = meta.icon;
  const watch = watchPoint(analyze, current, symbol);
  const values = (fundamentals?.insights ?? []).slice(0, 2);
  const position = positionLine(forecast);
  const downside = downsideLine(forecast);

  return (
    <div className="shrink-0 px-4 pt-3 pb-2.5 border-b border-border">
      <div className="flex items-start gap-2">
        <span
          className={`shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded-full border text-[11px] font-medium ${meta.className}`}
        >
          <Icon size={12} strokeWidth={2} />
          신호 {strength(analyze)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-base font-bold leading-snug">{headline}</p>
          <p className="mt-0.5 text-[11px] text-foreground-muted leading-snug">{detail}</p>
        </div>
        <button
          type="button"
          onClick={onToggleExpert}
          className="shrink-0 inline-flex items-center gap-1 px-2 h-6 rounded-md border border-border text-[10px] text-foreground-muted hover:bg-accent transition-colors"
          aria-pressed={expert}
        >
          <Eye size={11} strokeWidth={2} />
          {expert ? "간단히" : "자세히"}
        </button>
      </div>

      {(values.length > 0 || watch || position || downside) && (
        <div className="mt-2 flex flex-col gap-1">
          {position && (
            <p className="text-[11px] leading-snug">
              <span className="text-foreground-muted">현재 국면 </span>
              {position}
            </p>
          )}
          {downside && (
            <p className="text-[11px] leading-snug">
              <span className="text-foreground-muted">하방 </span>
              {downside}
            </p>
          )}
          {values.length > 0 && (
            <p className="text-[11px] leading-snug">
              <span className="text-foreground-muted">가치·체력 </span>
              {values.map((v, i) => (
                <span key={v.key} className={TONE_TEXT[v.tone] ?? ""}>
                  {i > 0 && <span className="text-foreground-muted"> · </span>}
                  {v.text}
                </span>
              ))}
            </p>
          )}
          {watch && (
            <p className="text-[11px] leading-snug">
              <span className="text-foreground-muted">지켜볼 점 </span>
              {watch}
            </p>
          )}
        </div>
      )}

      <Disclaimer className="mt-2" />
    </div>
  );
}
