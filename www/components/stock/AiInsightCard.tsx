"use client";

import { ChevronDown, Sparkles } from "lucide-react";
import type { Fundamentals, StockAnalyzeResult, StockForecast } from "@/lib/types";
import { formatPrice } from "@/lib/currency";
import { downsideLine, positionLine, verdict } from "@/lib/verdict";
import InsightList from "@/components/common/InsightList";
import { Button } from "@/components/ui/button";

// 초보자가 체감할 기준 투자금 — ATR%를 금액으로 옮길 때 쓴다
const RISK_BASE_KRW = 1_000_000;

// 좁은 바 라벨이라 쉬운 말 짧은 형태만(괄호 병기는 넓은 지표 타일 쪽에서)
const SIGNAL_LABELS: Record<string, string> = {
  sentiment: "뉴스 감성",
  rsi: "RSI",
  trend: "단기 추세",
  bollinger: "밴드 위치",
  obv: "자금 흐름",
  momentum: "1년 추세",
};

const TONE_TEXT: Record<string, string> = {
  positive: "text-up",
  warning: "text-down",
  neutral: "text-foreground-muted",
};

type Props = {
  analyze: StockAnalyzeResult;
  forecast?: StockForecast;
  fundamentals?: Fundamentals;
  price: number;
  ticker: string; // 통화 판별용 해석된 티커
  aiSummary?: string; // 이 종목을 설명한 마지막 챗 답변
  expert: boolean;
  onToggleExpert: () => void;
};

/**
 * AI 해설 카드 — 차트 바로 아래(레퍼런스 토스 "왜 올랐을까?" 자리).
 *
 * 구 StockHero의 2·3층(결론 카드 + 근거 2열)과 SignalBreakdown을 흡수했다.
 * 카드가 셋으로 갈라져 있으면 "결론 따로, 근거 따로, 기여도 따로"가 되고
 * 각자 border를 둘러 화면이 상자 무더기가 된다 — 한 카드 안에서 border-t 선으로만 구획한다.
 */
export default function AiInsightCard({
  analyze,
  forecast,
  fundamentals,
  price,
  ticker,
  aiSummary,
  expert,
  onToggleExpert,
}: Props) {
  const { headline, detail } = verdict(analyze, forecast);
  const watch = watchPoint(analyze, price, ticker);
  const position = positionLine(forecast);
  const downside = downsideLine(forecast);
  const values = (fundamentals?.insights ?? []).slice(0, 2);
  const p = forecast?.probability;

  return (
    <div className="mx-4 my-3 rounded-xl border border-border bg-surface px-3.5 py-3">
      {/* 결론 — 이 제품이 다른 시세 화면과 다른 지점이므로 1급으로 다룬다 */}
      <div className="flex items-start gap-2">
        <Sparkles size={15} strokeWidth={2} className="mt-0.5 shrink-0 text-brand" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold leading-snug">
            {headline}
            {forecast?.earnings_veto && (
              <span className="ml-1.5 inline-block align-middle rounded-full bg-down-weak px-2 py-0.5 text-[11px] font-medium text-down">
                실적 발표 임박
              </span>
            )}
          </p>
          <p className="mt-0.5 text-xs text-foreground-muted leading-relaxed">{detail}</p>
          {forecast?.earnings_veto && (
            <p className="mt-0.5 text-xs text-foreground-muted leading-relaxed">
              실적 발표 앞뒤 2일은 변동이 커서 방향 신호를 관망으로 낮춰 보여드려요.
            </p>
          )}
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

      {/* 근거 — 현재가 위치와 변동성을 나란히 */}
      <div className="mt-3 pt-3 border-t border-border grid gap-x-8 gap-y-3 sm:grid-cols-2">
        <PricePosition analyze={analyze} price={price} symbol={ticker} />
        <RiskSummary analyze={analyze} forecast={forecast} price={price} symbol={ticker} />
      </div>

      {/* 매물대·지지/저항 구간 문장(I-5) — 접지 않고 전면에 둔다. 페르소나 테스트에서
          가장 잘 읽힌 쉬운 문장들인데 "근거 보기" 뒤에 숨어 있었다. */}
      {forecast && forecast.insights.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border">
          <p className="mb-1.5 text-xs text-foreground-muted">가격대 근거</p>
          <InsightList insights={forecast.insights} />
        </div>
      )}

      <ContributionBars analyze={analyze} />

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
  );
}

/**
 * 신호별 기여도 — 중앙 0 기준 발산 막대.
 * 막대는 8px·radius 0이다: 데이터를 그리는 요소라 radius 표를 따르지 않는다 —
 * 이 높이에 radius를 주면 형태가 뭉개져 값을 읽을 수 없다(DESIGN.md §5 예외).
 */
function ContributionBars({ analyze }: { analyze: StockAnalyzeResult }) {
  const signals = analyze.signals ?? [];
  if (signals.length === 0 || analyze.score === undefined) return null;
  const upThr = analyze.up_threshold ?? 0.3;
  const downThr = analyze.down_threshold ?? -upThr;
  const maxAbs = Math.max(0.1, ...signals.map((s) => Math.abs(s.contribution)));

  return (
    <div className="mt-3 pt-3 border-t border-border">
      <p className="text-xs text-foreground-muted mb-2">신호별 기여도 (왜 이 방향인가)</p>
      <div className="grid gap-x-8 gap-y-1.5 sm:grid-cols-2">
        {signals.map((s) => {
          const inactive = s.weight === 0;
          const widthPct = Math.min(50, (Math.abs(s.contribution) / maxAbs) * 50);
          return (
            <div key={s.key} className="flex items-center gap-2 text-xs">
              <span className={`w-16 shrink-0 ${inactive ? "text-foreground-muted/60" : "text-foreground-muted"}`}>
                {SIGNAL_LABELS[s.key] ?? s.key}
              </span>
              <div className="relative flex-1 h-2">
                <div className="absolute inset-y-0 left-1/2 w-px bg-border" />
                {!inactive && s.contribution !== 0 && (
                  <div
                    className="absolute inset-y-0"
                    style={{
                      backgroundColor: s.contribution > 0 ? "var(--up)" : "var(--down)",
                      opacity: 0.75,
                      left: s.contribution > 0 ? "50%" : `${50 - widthPct}%`,
                      width: `${widthPct}%`,
                    }}
                  />
                )}
              </div>
              <span
                className={`w-12 shrink-0 text-right tabular-nums ${inactive ? "text-foreground-muted/60" : "font-medium"}`}
              >
                {inactive
                  ? `(${s.signal >= 0 ? "+" : ""}${s.signal.toFixed(1)})`
                  : `${s.contribution >= 0 ? "+" : ""}${s.contribution.toFixed(2)}`}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-2.5 pt-2 border-t border-border">
        <div className="flex justify-between text-xs text-foreground-muted mb-1">
          <span>하락 기준 {downThr.toFixed(2)}</span>
          <span className="font-medium text-foreground tabular-nums">
            종합 {analyze.score >= 0 ? "+" : ""}
            {analyze.score.toFixed(2)}
          </span>
          <span>상승 기준 +{upThr.toFixed(2)}</span>
        </div>
        <div className="relative h-2 bg-border/60">
          {/* 임계 눈금 (임계값을 ±1 스케일 위에) */}
          <div className="absolute inset-y-0 w-px bg-foreground-muted/50" style={{ left: `${50 + downThr * 50}%` }} />
          <div className="absolute inset-y-0 w-px bg-foreground-muted/50" style={{ left: `${50 + upThr * 50}%` }} />
          <div
            className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border-2 border-background shadow"
            style={{
              backgroundColor:
                analyze.score > 0 ? "var(--up)" : analyze.score < 0 ? "var(--down)" : "var(--foreground-muted)",
              left: `calc(${50 + Math.max(-1, Math.min(1, analyze.score)) * 50}% - 5px)`,
            }}
          />
        </div>
        <p className="mt-2 text-xs text-foreground-muted">
          회색 괄호 값은 판정에 반영되지 않는 지표(가중치 0)의 신호 상태입니다.
        </p>
      </div>
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
