"use client";

import { useState } from "react";
import type {
  GameMarketEvent,
  GameMarketPrices,
  GameSymbolPrices,
} from "@/lib/types";
import SymbolMark from "@/components/common/SymbolMark";
import GameChart, { MA_COLOR } from "./GameChart";
import GameOrderBook from "./GameOrderBook";
import GameAnalysisCard from "./GameAnalysisCard";
import MarketNewsFeed from "./MarketNewsFeed";

// 일봉 기간 탭. 백엔드 상한은 120일이고, 120일선을 그리려면 그만큼이 화면에 있어야 한다.
// "년"은 두지 않는다 — 한 시즌이 720 게임일이라 해에 대응하는 단위가 없다.
const CANDLE_RANGES = [
  { days: 30, label: "1개월" },
  { days: 60, label: "3개월" },
  { days: 120, label: "전체" },
] as const;

const TABS = [
  { key: "chart", label: "차트 · 호가" },
  { key: "info", label: "종목정보" },
  { key: "news", label: "뉴스" },
  { key: "analysis", label: "상태 분석" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

const won = (v: number) => `${v.toLocaleString()}원`;
const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const toneOf = (v: number) => (v >= 0 ? "text-up" : "text-down");
// 시가총액은 원 단위로 쓰면 자릿수를 셀 수 없다 — 증권 앱처럼 조·억으로 접는다
const eok = (v: number) =>
  v >= 1e12 ? `${(v / 1e12).toFixed(2)}조원` : `${Math.round(v / 1e8).toLocaleString()}억원`;

const SURPRISE: Record<string, { label: string; tone: string }> = {
  beat: { label: "기대 상회", tone: "text-up font-medium" },
  miss: { label: "기대 하회", tone: "text-down font-medium" },
  inline: { label: "기대 부합", tone: "text-foreground-muted" },
};

/**
 * 종목 상세 — 레퍼런스(토스증권 종목 화면)의 구조를 따른다.
 * 상단 요약바에 지표를 가로로 눕히고, 그 아래를 탭으로 가른다.
 *
 * 예전에는 차트·종목정보·호가·분석이 한 카드 안에 세로로 전부 쌓여 있어
 * 아래쪽 내용이 있는 줄도 모르고 지나쳤다.
 *
 * **커뮤니티 탭은 만들지 않았다** — 게임에는 다른 참가자가 없어서 글을 지어내야 하고,
 * 그건 사람이 쓴 것처럼 보이는 가짜 콘텐츠가 된다.
 */
export default function GameSymbolDetail({
  current,
  data,
  events,
  ticksPerGameDay,
  candleDays,
  onCandleDaysChange,
  isSelected,
}: {
  current: GameSymbolPrices;
  data: GameMarketPrices | undefined;
  events: GameMarketEvent[];
  ticksPerGameDay: number;
  candleDays: number;
  onCandleDaysChange: (days: number) => void;
  /** 봉·호가·분석은 선택 종목에만 계산된다 — 목록의 첫 종목을 보고 있을 때는 아직 없다 */
  isSelected: boolean;
}) {
  const [view, setView] = useState<{
    tab: TabKey;
    chart: "line" | "candle";
    pattern: string | null;
    ma: number[]; // 표시할 이동평균 — 기본 20/60만. 상관 높은 선 4개를 다 켜면
    // 같은 신호를 네 번 보고 네 개의 근거로 착각한다(선이 많다고 정확해지지 않는다)
  }>({
    tab: "chart",
    chart: "line",
    pattern: null,
    ma: [20, 60],
  });

  const info = isSelected ? (data?.symbolInfo ?? null) : null;
  const candles = data?.candles ?? [];
  const patterns = data?.patterns ?? [];
  const activePattern = patterns.find((p) => p.name === view.pattern) ?? patterns[0] ?? undefined;
  const orderBook = isSelected ? data?.orderBook : null;

  // 이 종목에 실제로 걸린 뉴스만 차트에 찍는다 — 피드의 대부분은 남의 종목 뉴스다
  const newsMarkers = events
    .filter((e) => e.affectedSymbols.includes(current.symbol))
    .map((e) => ({ tick: e.tick, positive: e.positive }));

  // 체결강도 대용 — 게임에 체결 이력이 없어 호가 잔량 비율로 낸다(같은 유동성 모형에서 나온 값)
  const bidSum = orderBook?.bids.reduce((s, q) => s + q.assumedQuantity, 0) ?? 0;
  const askSum = orderBook?.asks.reduce((s, q) => s + q.assumedQuantity, 0) ?? 0;
  const bidPct = bidSum + askSum === 0 ? null : Math.round((bidSum / (bidSum + askSum)) * 100);

  return (
    <section className="rounded-2xl border border-border bg-surface">
      {/* 요약바 — 값을 가로로 눕힌다(레퍼런스 토스 종목 헤더) */}
      <header className="px-4 pt-4 pb-3 border-b border-border">
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <SymbolMark name={current.name} size="md" />
              <h2 className="text-base font-bold tracking-tight truncate">{current.name}</h2>
              <span className="text-xs text-foreground-muted">{current.sector}</span>
            </div>
            <div className="mt-1.5 flex flex-wrap items-baseline gap-x-2.5">
              <span className="text-data-xl tabular-nums">{won(current.priceKrw)}</span>
              <span
                className={`text-data-l tabular-nums px-2 py-0.5 rounded-md ${
                  current.changePct > 0
                    ? "bg-up-weak text-up"
                    : current.changePct < 0
                      ? "bg-down-weak text-down"
                      : "text-foreground-muted"
                }`}
              >
                {signed(current.changePct)}
              </span>
            </div>
            <p className="mt-1 text-xs text-foreground-muted">게임 1일(현실 1시간) 전 대비</p>
          </div>

          <dl className="flex flex-wrap gap-x-6 gap-y-2">
            {info && (
              <>
                <Stat label={`최근 ${info.recentDays}일 고가`} value={won(info.recentHighKrw)} />
                <Stat label={`최근 ${info.recentDays}일 저가`} value={won(info.recentLowKrw)} />
                <Stat label="시가총액" value={eok(info.assumedMarketCapKrw)} />
              </>
            )}
            {bidPct !== null && <Stat label="매수 잔량 비율" value={`${bidPct}%`} />}
            {orderBook && (
              <Stat label="공매도 잔고" value={`${orderBook.shortInterestPct.toFixed(2)}%`} />
            )}
          </dl>
        </div>
      </header>

      <nav className="flex gap-1 px-3 pt-2.5 border-b border-border" aria-label="종목 상세">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setView((p) => ({ ...p, tab: t.key }))}
            aria-current={view.tab === t.key}
            className={`h-9 px-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              view.tab === t.key
                ? "border-brand text-foreground"
                : "border-transparent text-foreground-muted hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="p-4">
        {view.tab === "chart" && (
          <>
            <div className="flex flex-wrap items-center gap-1.5">
              {(["line", "candle"] as const).map((mode) => (
                <SmallChip
                  key={mode}
                  active={view.chart === mode}
                  onClick={() => setView((p) => ({ ...p, chart: mode }))}
                >
                  {mode === "line" ? "틱 차트" : "일봉"}
                </SmallChip>
              ))}
              {view.chart === "candle" && (
                <>
                  <span className="mx-1 h-4 w-px bg-border" aria-hidden />
                  {CANDLE_RANGES.map((r) => (
                    <SmallChip
                      key={r.days}
                      active={candleDays === r.days}
                      onClick={() => onCandleDaysChange(r.days)}
                    >
                      {r.label}
                    </SmallChip>
                  ))}
                  {/* 이동평균 범례 겸 토글 — 기본 20/60만 켠다. 원하는 선만 추가로 */}
                  <span className="ml-auto flex items-center gap-2 text-xs tabular-nums">
                    {data?.movingAverages?.map((m) => {
                      const active = view.ma.includes(m.period);
                      return (
                        <button
                          key={m.period}
                          type="button"
                          aria-pressed={active}
                          onClick={() =>
                            setView((p) => ({
                              ...p,
                              ma: active
                                ? p.ma.filter((d) => d !== m.period)
                                : [...p.ma, m.period],
                            }))
                          }
                          style={{ color: MA_COLOR[m.period] }}
                          className={active ? "font-semibold" : "opacity-35"}
                        >
                          {m.period}
                        </button>
                      );
                    })}
                  </span>
                </>
              )}
            </div>

            <GameChart
              points={current.series}
              candles={view.chart === "candle" ? candles : undefined}
              movingAverages={
                view.chart === "candle"
                  ? (data?.movingAverages ?? []).filter((m) => view.ma.includes(m.period))
                  : []
              }
              rsi={view.chart === "candle" ? (data?.rsi ?? []) : []}
              markers={newsMarkers}
              pattern={view.chart === "line" ? activePattern : undefined}
              className="mt-3 w-full h-72 sm:h-80"
            />

            <p className="mt-2.5 text-xs text-foreground-muted leading-relaxed">
              {view.chart === "candle" && candles.length > 0
                ? `일봉 ${candles.length}개 · 게임 1일(현실 1시간)이 1봉 · 이동평균은 범례에서 켠 선만(기본 20·60) · RSI 14 · 우측 음영은 매물대(가격대별 거래 밀집 — 진한 칸이 최다 거래 구간). 거래량은 게임에 호가·체결 개념이 없어 규칙으로 만든 가정치입니다.`
                : `최근 게임 ${Math.round(current.series.length / 60)}일 · 등락률은 게임 1일(현실 1시간) 전 대비`}
              {newsMarkers.length > 0 && " · 세로 눈금은 이 종목에 걸린 뉴스 시점"}
            </p>

            {patterns.length > 0 && view.chart === "line" && (
              <div className="mt-3 pt-3 border-t border-border">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs font-semibold">보이는 형태</span>
                  {patterns.map((p) => (
                    <SmallChip
                      key={p.name}
                      active={activePattern?.name === p.name}
                      onClick={() => setView((prev) => ({ ...prev, pattern: p.name }))}
                    >
                      {p.label}
                      <span className="ml-1 tabular-nums opacity-70">
                        {Math.round(p.confidence * 100)}
                      </span>
                    </SmallChip>
                  ))}
                </div>
                {activePattern && (
                  <p className="mt-2 text-xs leading-relaxed text-foreground-muted">
                    {activePattern.note} 점선이 그 형태의 꼭짓점을 잇습니다. 형태를 알아본 것일 뿐
                    앞으로의 방향을 뜻하지 않습니다 — 이 게임의 주가는 난수와 뉴스 충격으로
                    만들어지므로 형태에 시장 심리가 담겨 있지 않습니다.
                  </p>
                )}
              </div>
            )}

            {orderBook && (
              <div className="mt-4">
                <GameOrderBook book={orderBook} />
              </div>
            )}
          </>
        )}

        {view.tab === "info" &&
          (info ? (
            <>
              <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: "시가총액", value: eok(info.assumedMarketCapKrw) },
                  // 적자면 PER 칸을 비운다 — 음수 PER은 "싸다"로 오독된다
                  { label: "PER", value: info.per === null ? "적자" : `${info.per.toFixed(1)}배` },
                  { label: "PBR", value: info.pbr === null ? "—" : `${info.pbr.toFixed(2)}배` },
                  { label: "ROE", value: `${(info.assumedRoe * 100).toFixed(1)}%` },
                  { label: "EPS (연환산)", value: won(info.assumedEpsKrw) },
                  { label: "BPS", value: won(info.assumedBpsKrw) },
                  { label: "부채비율", value: `${(info.assumedDebtRatio * 100).toFixed(0)}%` },
                  {
                    label: "발행주식수",
                    value: `${(info.assumedSharesOutstanding / 10_000).toLocaleString()}만주`,
                  },
                  { label: "시즌 시작가", value: won(info.basePriceKrw) },
                  { label: "게임 1일 변동성", value: `${info.gameDailySigmaPct.toFixed(2)}%` },
                ].map((item) => (
                  <div key={item.label}>
                    <dt className="text-xs text-foreground-muted">{item.label}</dt>
                    <dd className="mt-0.5 text-sm font-semibold tabular-nums">{item.value}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 pt-3 border-t border-border text-xs text-foreground-muted leading-relaxed">
                {info.sectorGroup} · {info.gameQuarter}분기 공시{" "}
                <span className={SURPRISE[info.earningsSurprise].tone}>
                  {SURPRISE[info.earningsSurprise].label}
                </span>{" "}
                · 실적은 <b>가상 기업의 가정치</b>입니다(실재 기업의 재무가 아닙니다). 분기마다 새로
                공시되며, 주가와 독립으로 만들어지므로 많이 오르면 PER이 올라갑니다.
                {info.meme && (
                  <span className="text-up">
                    {" "}
                    밈 종목입니다 — <b>적자 상태</b>라 PER이 없습니다. 실적이 아니라 수급·화제성이
                    값을 만들고, 전용 뉴스(스퀴즈·반대매매)가 한 번에 8~28%를 밀어냅니다.
                  </span>
                )}
              </p>
            </>
          ) : (
            <p className="py-8 text-center text-sm text-foreground-muted">
              목록에서 종목을 선택하면 재무 정보가 계산됩니다.
            </p>
          ))}

        {view.tab === "news" && (
          <MarketNewsFeed
            events={events}
            currentTick={data?.tick ?? 0}
            ticksPerGameDay={ticksPerGameDay}
            selectedSymbol={current.symbol}
          />
        )}

        {view.tab === "analysis" &&
          (isSelected && data?.analysis ? (
            <GameAnalysisCard analysis={data.analysis} />
          ) : (
            <p className="py-8 text-center text-sm text-foreground-muted">
              목록에서 종목을 선택하면 상태 분석이 계산됩니다.
            </p>
          ))}
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-foreground-muted">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function SmallChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center h-7 px-2.5 rounded-full text-xs font-medium transition-colors duration-150 ${
        active
          ? "bg-brand text-white"
          : "border border-border text-foreground-muted hover:bg-accent hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

export { toneOf };
