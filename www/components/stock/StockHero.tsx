"use client";

import { ChevronDown, ShieldCheck, Sparkles } from "lucide-react";
import type { Fundamentals, StockAnalyzeResult, StockForecast } from "@/lib/types";
import { formatPrice } from "@/lib/currency";
import { downsideLine, positionLine, strength, verdict } from "@/lib/verdict";
import InsightList from "@/components/common/InsightList";
import SymbolMark from "@/components/common/SymbolMark";
import { Button } from "@/components/ui/button";
import Disclaimer from "./Disclaimer";

// 초보자가 체감할 기준 투자금 — ATR%를 금액으로 옮길 때 쓴다
const RISK_BASE_KRW = 1_000_000;

type Props = {
  symbol: string;
  resolvedTicker?: string;
  analyze?: StockAnalyzeResult;
  forecast?: StockForecast;
  fundamentals?: Fundamentals;
  isLoading: boolean;
  quotePrice?: number | null; // 30초 폴링 현재가(지연 시세) — 있으면 분석 시점 가격보다 우선
  previousClose?: number | null; // 전일 종가 — 등락률 기준
  aiSummary?: string; // 이 종목을 설명한 마지막 챗 답변
  expert: boolean;
  onToggleExpert: () => void;
};

/**
 * 스테이지 결론 블록 — `SymbolHeader` + `StockVerdictHero` + `StageSummary` + `SymbolSummary`를 흡수했다.
 *
 * 넷을 합친 이유: 각자 `border-b`를 두르고 세로로 쌓여 스테이지 위쪽 절반이 구분선 4개짜리
 * 띠가 됐고, 정작 "결론"은 전부 11px이라 어느 것이 결론인지 형태로 알 수 없었다.
 * 지금은 한 블록 안에서 **크기**가 위계를 말한다 — 가격 28px > 등락 20px > 결론 14px > 근거 12px.
 */
export default function StockHero({
  symbol,
  resolvedTicker,
  analyze,
  forecast,
  fundamentals,
  isLoading,
  quotePrice,
  previousClose,
  aiSummary,
  expert,
  onToggleExpert,
}: Props) {
  if (isLoading && !analyze) {
    return (
      <header className="shrink-0 px-4 pt-4 pb-3 border-b border-border">
        <div className="skeleton h-5 w-32 rounded-md" />
        <div className="mt-2 skeleton h-8 w-48 rounded-md" />
        <div className="mt-3 skeleton h-16 w-full rounded-xl" />
      </header>
    );
  }
  if (!analyze) return null;

  const ticker = resolvedTicker ?? symbol;
  const price = quotePrice ?? analyze.price;
  const changePct = previousClose ? (price / previousClose - 1) * 100 : null;
  const { headline, detail } = verdict(analyze, forecast);
  const watch = watchPoint(analyze, price, ticker);
  const position = positionLine(forecast);
  const downside = downsideLine(forecast);
  const values = (fundamentals?.insights ?? []).slice(0, 2);
  const p = forecast?.probability;

  return (
    <header className="shrink-0 px-4 pt-4 pb-3 border-b border-border">
      {/* 1층 — 이름·가격·등락률, 그리고 우측에 참고 수치를 가로로 눕힌다(레퍼런스 토스 종목 헤더) */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <SymbolMark name={symbol} size="md" />
            <h1 className="text-base font-bold">{symbol}</h1>
            {ticker !== symbol && <span className="text-xs text-foreground-muted">{ticker}</span>}
            {analyze.reference_up_signal && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-border bg-surface text-xs text-foreground-muted">
                <ShieldCheck size={12} strokeWidth={2} className="text-brand" />
                백테스트 참고 신호
              </span>
            )}
          </div>

          <div className="mt-1.5 flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <span className="text-data-xl tabular-nums">{formatPrice(price, ticker)}</span>
            {changePct !== null && (
              <span
                className={`text-data-l tabular-nums px-2 py-0.5 rounded-md ${toneBox(changePct)}`}
              >
                {changePct > 0 ? "+" : ""}
                {changePct.toFixed(2)}%
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-foreground-muted">
            전일 대비{quotePrice != null && " · 지연 시세 30초 갱신"}
          </p>
        </div>

        <dl className="flex flex-wrap gap-x-6 gap-y-2">
          <Stat label="60일 최저" value={formatPrice(analyze.support, ticker)} />
          <Stat label="60일 최고" value={formatPrice(analyze.resistance, ticker)} />
          <Stat label="하루 변동" value={`±${(analyze.atr_pct * 100).toFixed(1)}%`} />
          <Stat label="신호 세기" value={strength(analyze)} />
        </dl>
      </div>

      {/* 2층 — AI 결론. 이 제품이 다른 시세 화면과 다른 지점이므로 카드로 띄워 1급으로 다룬다. */}
      <div className="mt-3 rounded-xl border border-border bg-background px-3 py-2.5">
        <div className="flex items-start gap-2">
          <Sparkles size={15} strokeWidth={2} className="mt-0.5 shrink-0 text-brand" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold leading-snug">{headline}</p>
            <p className="mt-0.5 text-xs text-foreground-muted leading-relaxed">{detail}</p>
            {watch && <p className="mt-1 text-xs leading-relaxed">{watch}</p>}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleExpert}
            aria-pressed={expert}
            className="shrink-0 text-foreground-muted"
          >
            {expert ? "간단히" : "자세히"}
          </Button>
        </div>

        {aiSummary && (
          <details className="group mt-2 pt-2 border-t border-border">
            <summary className="flex items-center gap-1.5 cursor-pointer list-none select-none text-xs text-foreground-muted">
              <ChevronDown size={13} className="shrink-0 transition-transform group-open:rotate-180" />
              <span className="flex-1 truncate group-open:hidden">{aiSummary}</span>
              <span className="hidden group-open:block flex-1">이 종목에 대한 답변</span>
            </summary>
            <p className="mt-1.5 pl-[19px] text-xs leading-relaxed whitespace-pre-wrap">{aiSummary}</p>
          </details>
        )}
      </div>

      {/* 3층 — 근거. 현재가 위치와 변동성을 나란히 둔다. */}
      <div className="mt-3 grid gap-x-8 gap-y-3 sm:grid-cols-2">
        <PricePosition analyze={analyze} price={price} symbol={ticker} />
        <RiskSummary analyze={analyze} forecast={forecast} price={price} symbol={ticker} />
      </div>

      {expert && (
        <div className="mt-3 pt-3 border-t border-border flex flex-col gap-1 text-xs leading-relaxed">
          {position && (
            <p>
              <span className="text-foreground-muted">현재 국면 </span>
              {position}
            </p>
          )}
          {downside && (
            <p>
              <span className="text-foreground-muted">하방 </span>
              {downside}
            </p>
          )}
          {values.length > 0 && (
            <p>
              <span className="text-foreground-muted">가치·체력 </span>
              {values.map((v, i) => (
                <span key={v.key} className={TONE_TEXT[v.tone] ?? ""}>
                  {i > 0 && <span className="text-foreground-muted"> · </span>}
                  {v.text}
                </span>
              ))}
            </p>
          )}
          <p className="text-foreground-muted">
            종합 점수 {analyze.score !== undefined ? analyze.score.toFixed(2) : "—"} (기준 ±
            {(analyze.up_threshold ?? 0.3).toFixed(2)}) · 확신도 {Math.round(analyze.confidence * 100)}%
            {p && (
              <>
                {" · "}상승 확률 {Math.round(p.up_rate * 100)}% · 평소 {Math.round(p.baseline_up_rate * 100)}%
                {" · "}표본 {p.sample_size}회 중 {p.hits}회 · 95% 구간{" "}
                {Math.round(p.ci_low * 100)}~{Math.round(p.ci_high * 100)}%
                {!p.ready && " · 표본 부족(참고용)"}
              </>
            )}
          </p>
        </div>
      )}

      {forecast && forecast.insights.length > 0 && (
        <details className="mt-2 group">
          <summary className="flex items-center gap-1 text-xs text-foreground-muted cursor-pointer list-none select-none">
            <ChevronDown size={13} className="transition-transform group-open:rotate-180" />
            근거 보기
          </summary>
          <div className="mt-1.5 pl-1">
            <InsightList insights={forecast.insights} />
          </div>
        </details>
      )}

      <Disclaimer className="mt-2.5" />
    </header>
  );
}

const TONE_TEXT: Record<string, string> = {
  positive: "text-up",
  warning: "text-down",
  neutral: "text-foreground-muted",
};

// 등락률 배경 하이라이트 — 값이 아니라 값의 방향이 먼저 읽히게 한다(DESIGN.md §2 Direction roles)
function toneBox(v: number) {
  if (v > 0) return "bg-up-weak text-up";
  if (v < 0) return "bg-down-weak text-down";
  return "text-foreground-muted";
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-foreground-muted">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

/** 현재가가 60일 저/고점 구간 어디쯤인지에 따라 "지켜볼 것"을 말한다 — 관측 지시일 뿐 매수 조언이 아니다. */
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

/** 최근 60거래일 최저~최고 안에서 현재가 위치.
 *  "지지/저항"으로 부르지 않는다 — 실제로는 60일 롤링 최저·최고 한 봉일 뿐이고,
 *  그 봉이 창을 벗어나면 시장과 무관하게 값이 점프한다(SNDK 실측: 40거래일간 517→980,
 *  2% 넘는 점프 11회). 예측이 아니라 관측된 구간이라는 뜻이 라벨에 드러나야 한다. */
function PricePosition({
  analyze,
  price,
  symbol,
}: {
  analyze: StockAnalyzeResult;
  price: number;
  symbol: string;
}) {
  const { support, resistance } = analyze;
  if (!(resistance > support)) return null;
  const ratio = Math.max(0, Math.min(1, (price - support) / (resistance - support)));

  return (
    <div>
      <div className="flex items-baseline justify-between text-xs text-foreground-muted">
        <span>60일 최저 {formatPrice(support, symbol)}</span>
        <span>60일 최고 {formatPrice(resistance, symbol)}</span>
      </div>
      <div className="relative mt-1.5 h-1.5 rounded-full bg-gradient-to-r from-down-weak via-border to-up-weak">
        <div
          className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-foreground border-2 border-background shadow"
          style={{ left: `calc(${ratio * 100}% - 5px)` }}
        />
      </div>
      <p className="mt-1.5 text-xs text-foreground-muted">
        60일 등락 구간의 <b className="font-semibold text-foreground">{Math.round(ratio * 100)}% 지점</b>에
        있습니다 {ratio <= 0.25 ? "(바닥권)" : ratio >= 0.75 ? "(고점권)" : "(중간)"}
      </p>
    </div>
  );
}

/** 변동성·예측 범위를 금액으로. "ATR 12.5%"보다 "100만원이면 하루 ±12.5만원"이 훨씬 읽힌다. */
function RiskSummary({
  analyze,
  forecast,
  price,
  symbol,
}: {
  analyze: StockAnalyzeResult;
  forecast?: StockForecast;
  price: number;
  symbol: string;
}) {
  const daily = Math.round(analyze.atr_pct * RISK_BASE_KRW);
  const band = forecast?.band;

  return (
    <div className="text-xs leading-relaxed">
      <p>
        하루 평균 <b className="font-semibold">±{(analyze.atr_pct * 100).toFixed(1)}%</b> 움직입니다 —
        100만원이면 하루 <b className="font-semibold">±{daily.toLocaleString("ko-KR")}원</b>.
      </p>
      {band && (
        <p className="mt-1">
          {forecast!.horizon_days}일 뒤 예상 범위{" "}
          <b className="font-semibold text-down">{formatPrice(price * (1 + band.q25_pct), symbol)}</b> ~{" "}
          <b className="font-semibold text-up">{formatPrice(price * (1 + band.q75_pct), symbol)}</b>
        </p>
      )}
    </div>
  );
}
