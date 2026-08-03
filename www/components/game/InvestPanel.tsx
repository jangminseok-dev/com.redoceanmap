"use client";

import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info, TriangleAlert } from "lucide-react";
import GameOrderForm from "@/components/game/GameOrderForm";
import MarketNewsFeed from "@/components/game/MarketNewsFeed";
import GamePositionList from "@/components/game/GamePositionList";
import GameAnalysisCard from "@/components/game/GameAnalysisCard";
import GameChart, { MA_COLOR } from "@/components/game/GameChart";
import GamePriceLine from "@/components/game/GamePriceLine";
import {
  ApiError,
  closeGameTrade,
  fetchGamePrices,
  fetchGameRulebook,
  fetchGameWallet,
  openGameTrade,
} from "@/lib/api";
import { useUIStore } from "@/lib/uiStore";
import type { GameSymbolPrices } from "@/lib/types";

const CHART_TICKS = 120; // 게임 2일치 — 곡선 모양이 읽히는 최소 구간
// 일봉 기간 탭. 백엔드 상한은 120일이고, 120일선을 그리려면 그만큼이 화면에 있어야 한다.
// "년"은 두지 않는다 — 한 시즌이 720 게임일이라 해에 대응하는 단위가 없다.
const CANDLE_RANGES = [
  { days: 30, label: "1개월" },
  { days: 60, label: "3개월" },
  { days: 120, label: "전체" },
] as const;
const ALL_SECTORS = "전체";

const won = (v: number) => `${v.toLocaleString()}원`;
const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
// 시가총액은 원 단위로 쓰면 자릿수를 셀 수 없다 — 증권 앱처럼 조·억으로 접는다
const eok = (v: number) =>
  v >= 1e12 ? `${(v / 1e12).toFixed(2)}조원` : `${Math.round(v / 1e8).toLocaleString()}억원`;

const SURPRISE: Record<string, { label: string; tone: string }> = {
  beat: { label: "기대 상회", tone: "text-[#DC2626] font-medium" },
  miss: { label: "기대 하회", tone: "text-[#2563EB] font-medium" },
  inline: { label: "기대 부합", tone: "text-foreground-muted" },
};
const toneOf = (v: number) => (v >= 0 ? "text-[#DC2626]" : "text-[#2563EB]");

export default function InvestPanel() {
  // 선택 종목 · 체결 안내 · 화면 필터. 나머지는 서버 응답이라 상태로 들 것이 없다
  // (REACT_RULES 패턴 B: 여러 값은 단일 객체로)
  const [view, setView] = useState<{
    selected: string | null;
    notice: string | null;
    sector: string;
    chart: "line" | "candle";
    pattern: string | null;
    candleDays: number;
  }>({
    selected: null,
    notice: null,
    sector: ALL_SECTORS,
    chart: "line",
    pattern: null,
    candleDays: CANDLE_RANGES[0].days,
  });
  const openAuth = useUIStore((s) => s.openAuth);
  const queryClient = useQueryClient();

  const rulebookQ = useQuery({
    queryKey: ["game-rulebook"],
    queryFn: fetchGameRulebook,
    staleTime: 10 * 60_000,
  });

  // 시세 — 결정론 계산이라 같은 틱을 다시 물어도 같은 값이다. 에러 시 5분 저속 재시도.
  // 선택 종목의 일봉·종목정보를 함께 받는다(전 종목 봉은 응답 목표를 넘긴다).
  // 종목을 바꾸면 키가 바뀌므로 이전 데이터를 유지해 차트가 깜빡이지 않게 한다.
  const pricesQ = useQuery({
    queryKey: ["game-prices", CHART_TICKS, view.selected, view.candleDays],
    queryFn: () => fetchGamePrices(CHART_TICKS, view.selected ?? undefined, view.candleDays),
    refetchInterval: (query) => (query.state.status === "error" ? 300_000 : 30_000),
    placeholderData: keepPreviousData,
  });

  // 지갑 — 평가손익이 시세를 따라 움직여야 하므로 같은 주기로 갱신한다
  const walletQ = useQuery({
    queryKey: ["game-wallet"],
    queryFn: fetchGameWallet,
    refetchInterval: (query) => (query.state.status === "error" ? 300_000 : 30_000),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["game-wallet"] });
    queryClient.invalidateQueries({ queryKey: ["game-prices", CHART_TICKS] });
  };

  const open = useMutation({
    mutationFn: ({
      symbol,
      side,
      quantity,
      leverage,
    }: {
      symbol: string;
      side: "LONG" | "SHORT";
      quantity: number;
      leverage: number;
    }) => openGameTrade(symbol, side, quantity, leverage),
    onSuccess: (r) => {
      refresh();
      setView((prev) => ({
        ...prev,
        notice:
          `${r.name} ${r.side === "LONG" ? "롱" : "숏"}${r.leverage > 1 ? ` ${r.leverage}배` : ""} ` +
          `${r.quantity.toLocaleString()}주 체결 · ${won(r.priceKrw)}` +
          (r.liquidationPriceKrw ? ` · 청산선 ${won(r.liquidationPriceKrw)}` : ""),
      }));
    },
    onError: (e) =>
      setView((prev) => ({
        ...prev,
        notice: e instanceof Error ? e.message : "주문에 실패했습니다.",
      })),
  });

  const close = useMutation({
    mutationFn: (positionId: number) => closeGameTrade(positionId),
    onSuccess: (r) => {
      refresh();
      const pnl = r.realizedPnlKrw ?? 0;
      setView((prev) => ({
        ...prev,
        notice: `${r.name} 청산 · 실현손익 ${pnl >= 0 ? "+" : ""}${pnl.toLocaleString()}원`,
      }));
    },
    onError: (e) =>
      setView((prev) => ({
        ...prev,
        notice: e instanceof Error ? e.message : "청산에 실패했습니다.",
      })),
  });

  const data = pricesQ.data;
  const wallet = walletQ.data;
  const symbols = data?.symbols ?? [];
  const candles = data?.candles ?? [];
  const info = data?.symbolInfo ?? null;
  const patterns = data?.patterns ?? [];
  const activePattern =
    patterns.find((p) => p.name === view.pattern) ?? patterns[0] ?? undefined;
  const current: GameSymbolPrices | undefined =
    symbols.find((s) => s.symbol === view.selected) ?? symbols[0];

  // 섹터 그룹 4개 — 도메인이 정한 축이라 프론트가 목록을 지어내지 않는다
  const sectorGroups = useMemo(
    () => [ALL_SECTORS, ...Array.from(new Set(symbols.map((s) => s.sectorGroup)))],
    [symbols],
  );
  const visibleSymbols =
    view.sector === ALL_SECTORS ? symbols : symbols.filter((s) => s.sectorGroup === view.sector);
  const unauthorized =
    (pricesQ.error as ApiError)?.status === 401 || (walletQ.error as ApiError)?.status === 401;

  // 지금 보고 있는 종목에 실제로 걸리는 뉴스만 차트에 찍는다 — 피드의 대부분은 남의 종목 뉴스다
  const newsMarkers = useMemo(
    () =>
      current
        ? (data?.events ?? [])
            .filter((e) => e.affectedSymbols.includes(current.symbol))
            .map((e) => ({ tick: e.tick, positive: e.positive }))
        : [],
    [data?.events, current],
  );

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 border border-amber-200 px-3 py-1 text-xs font-medium text-amber-800">
          <Info size={13} strokeWidth={2} />
          가상 주가 · 실제 시세가 아닙니다
        </span>
        <p className="text-sm text-foreground-muted">
          접속하지 않는 동안에도 시세가 움직이며, 모든 참가자가 같은 장을 봅니다.
        </p>
      </div>

      {data && !data.calibrated && (
        <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-foreground-muted">
          <TriangleAlert size={13} strokeWidth={2} className="text-amber-600" />
          종목 변동성은 실데이터 캘리브레이션 전 잠정값입니다.
        </p>
      )}

      {/* 시즌 시작 전·직후에는 전 종목이 기준가에 멈춰 있다 — 화면이 고장 난 것처럼 보이지 않게 말한다 */}
      {data && data.tick === 0 && (
        <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-foreground-muted">
          <TriangleAlert size={13} strokeWidth={2} className="text-amber-600" />
          시즌이 아직 시작되지 않았습니다 — 지금 보이는 값은 전 종목의 시즌 시작가입니다.
          시작되면 1분마다 게임 1일이 흐릅니다.
        </p>
      )}

      {unauthorized && (
        <div className="mt-8 rounded-2xl border border-border bg-surface p-8 text-center">
          <p className="text-sm text-foreground-muted">
            게임은 누구나 이용할 수 있지만, 자산을 저장하려면 로그인이 필요합니다.
          </p>
          <button
            type="button"
            onClick={() => openAuth("login")}
            className="mt-5 inline-flex items-center px-5 h-10 rounded-full bg-brand text-white text-sm font-medium hover:bg-brand-deep transition-colors"
          >
            로그인하고 시작하기
          </button>
        </div>
      )}

      {pricesQ.isLoading && !unauthorized && (
        <div className="mt-8 grid place-items-center h-64 text-sm text-foreground-muted">
          시세를 불러오는 중…
        </div>
      )}

      {/* 자산 요약 */}
      {wallet && (
        <section className="mt-6 rounded-2xl border border-border bg-surface p-5 grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "총자산", value: won(wallet.totalAssetKrw), tone: "" },
            {
              label: "수익률",
              value: signed(wallet.totalReturnPct),
              tone: toneOf(wallet.totalReturnPct),
            },
            { label: "현금", value: won(wallet.cashKrw), tone: "" },
            { label: "투자 가능", value: won(wallet.investableKrw), tone: "" },
          ].map((item) => (
            <div key={item.label}>
              <dt className="text-xs text-foreground-muted">{item.label}</dt>
              <dd className={`mt-0.5 text-lg font-bold tabular-nums ${item.tone}`}>
                {item.value}
              </dd>
            </div>
          ))}
          <p className="col-span-2 sm:col-span-4 text-[11px] text-foreground-muted">
            최소 생활자금 {won(wallet.reservedKrw)}은 투자에 쓸 수 없습니다 — 전부 잃어도 이 돈은
            남습니다.
          </p>
        </section>
      )}

      {view.notice && (
        <p className="mt-3 rounded-xl bg-brand/8 border border-brand/20 px-4 py-2.5 text-sm">
          {view.notice}
        </p>
      )}

      {/* 미접속 중 마감된 포지션 — 복귀했을 때 무슨 일이 있었는지 알린다 */}
      {(wallet?.recentlyClosed?.length ?? 0) > 0 && (
        <section className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="text-xs font-semibold text-amber-900">자리를 비운 사이에</p>
          <ul className="mt-1.5 space-y-1">
            {wallet?.recentlyClosed?.map((c) => (
              <li key={c.id} className="text-xs text-amber-900 tabular-nums">
                {c.name} {c.side === "LONG" ? "롱" : "숏"}
                {c.leverage > 1 && ` ${c.leverage}배`} {c.quantity.toLocaleString()}주 —{" "}
                {c.closedGameDay}일차에{" "}
                {c.reason === "liquidated"
                  ? "강제청산"
                  : c.reason === "expired"
                    ? "만료 마감"
                    : "만기 정산"}
                <span className={`ml-1 font-semibold ${toneOf(c.realizedPnlKrw)}`}>
                  {signed(c.realizedPnlKrw)}원
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {current && (
        <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_320px]">
          <section className="rounded-2xl border border-border bg-surface p-5">
            <div className="flex items-baseline gap-2 flex-wrap">
              <h2 className="text-lg font-bold tracking-tight">{current.name}</h2>
              <span className="text-xs text-foreground-muted">{current.sector}</span>
              <span className="ml-auto text-xl font-bold tabular-nums">
                {won(current.priceKrw)}
              </span>
              <span className={`text-sm font-semibold tabular-nums ${toneOf(current.changePct)}`}>
                {signed(current.changePct)}
              </span>
            </div>

            <div className="mt-3 flex gap-1 rounded-xl border border-border p-0.5 w-fit">
              {(["line", "candle"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() =>
                    setView((prev) => ({
                      ...prev,
                      chart: mode,
                      // 봉은 선택 종목에만 계산된다 — 아직 고른 적이 없으면 지금 보는 종목으로 채운다
                      selected: prev.selected ?? current.symbol,
                    }))
                  }
                  className={`h-7 rounded-lg px-3 text-xs font-medium transition-colors ${
                    view.chart === mode
                      ? "bg-brand text-white"
                      : "text-foreground-muted hover:text-foreground"
                  }`}
                >
                  {mode === "line" ? "틱 차트" : "일봉"}
                </button>
              ))}
            </div>

            {/* 일봉일 때만 기간을 고른다 — 틱 차트는 구간이 하나다 */}
            {view.chart === "candle" && (
              <div className="mt-2 flex items-center gap-1.5">
                {CANDLE_RANGES.map((r) => (
                  <button
                    key={r.days}
                    type="button"
                    onClick={() => setView((prev) => ({ ...prev, candleDays: r.days }))}
                    className={`h-7 rounded-lg px-2.5 text-[11px] font-medium transition-colors ${
                      view.candleDays === r.days
                        ? "bg-foreground/10 text-foreground"
                        : "text-foreground-muted hover:text-foreground"
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
                {/* 이동평균 범례 — 어느 색이 몇 일선인지 알아야 선이 의미를 갖는다 */}
                <span className="ml-auto flex items-center gap-2 text-[10px] tabular-nums">
                  {data?.movingAverages?.map((m) => (
                    <span key={m.period} style={{ color: MA_COLOR[m.period] }}>
                      {m.period}
                    </span>
                  ))}
                </span>
              </div>
            )}

            <GameChart
              points={current.series}
              candles={view.chart === "candle" ? candles : undefined}
              movingAverages={view.chart === "candle" ? (data?.movingAverages ?? []) : []}
              rsi={view.chart === "candle" ? (data?.rsi ?? []) : []}
              markers={newsMarkers}
              pattern={view.chart === "line" ? activePattern : undefined}
              className="mt-3 w-full h-72 sm:h-96"
            />

            <p className="mt-3 text-xs text-foreground-muted">
              {view.chart === "candle" && candles.length > 0
                ? `일봉 ${candles.length}개 · 게임 1일(현실 1시간)이 1봉 · 이동평균 5·20·60·120일 · RSI 14`
                : `최근 게임 ${Math.round(current.series.length / 60)}일 · 등락률은 게임 1일(현실 1시간) 전 대비`}
              {newsMarkers.length > 0 && " · 세로 눈금은 이 종목에 걸린 뉴스 시점"}
            </p>
            {view.chart === "candle" && (
              <p className="mt-1 text-[11px] text-foreground-muted">
                거래량은 게임에 호가·체결 개념이 없어 규칙으로 만든 가정치입니다.
              </p>
            )}

            {patterns.length > 0 && view.chart === "line" && (
              <div className="mt-4 border-t border-border pt-4">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs font-semibold">보이는 형태</span>
                  {patterns.map((p) => (
                    <button
                      key={p.name}
                      type="button"
                      onClick={() => setView((prev) => ({ ...prev, pattern: p.name }))}
                      className={`h-7 rounded-lg px-2.5 text-[11px] font-medium transition-colors ${
                        activePattern?.name === p.name
                          ? "bg-foreground text-background"
                          : "text-foreground-muted hover:bg-black/[0.04]"
                      }`}
                    >
                      {p.label}
                      <span className="ml-1 tabular-nums opacity-70">
                        {Math.round(p.confidence * 100)}
                      </span>
                    </button>
                  ))}
                </div>
                {activePattern && (
                  <p className="mt-2 text-[11px] leading-relaxed text-foreground-muted">
                    {activePattern.note} 점선이 그 형태의 꼭짓점을 잇습니다.
                    <br />
                    형태를 알아본 것일 뿐 앞으로의 방향을 뜻하지 않습니다. 이 게임의 주가는
                    난수와 뉴스 충격으로 만들어지므로 형태에 시장 심리가 담겨 있지 않습니다.
                  </p>
                )}
              </div>
            )}

            {info && info.symbol === current.symbol && (
              <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 border-t border-border pt-4">
                {[
                  { label: "시가총액", value: eok(info.assumedMarketCapKrw) },
                  // 적자면 PER 칸을 비운다 — 음수 PER은 "싸다"로 오독된다
                  { label: "PER", value: info.per === null ? "적자" : `${info.per.toFixed(1)}배` },
                  { label: "PBR", value: info.pbr === null ? "—" : `${info.pbr.toFixed(2)}배` },
                  { label: "ROE", value: `${(info.assumedRoe * 100).toFixed(1)}%` },
                  { label: "EPS (연환산)", value: won(info.assumedEpsKrw) },
                  { label: "BPS", value: won(info.assumedBpsKrw) },
                  { label: "부채비율", value: `${(info.assumedDebtRatio * 100).toFixed(0)}%` },
                  { label: "발행주식수", value: `${(info.assumedSharesOutstanding / 10_000).toLocaleString()}만주` },
                  { label: "시즌 시작가", value: won(info.basePriceKrw) },
                  { label: "게임 1일 변동성", value: `${info.gameDailySigmaPct.toFixed(2)}%` },
                  { label: `최근 ${info.recentDays}일 고가`, value: won(info.recentHighKrw) },
                  { label: `최근 ${info.recentDays}일 저가`, value: won(info.recentLowKrw) },
                ].map((item) => (
                  <div key={item.label}>
                    <dt className="text-[11px] text-foreground-muted">{item.label}</dt>
                    <dd className="text-sm font-semibold tabular-nums">{item.value}</dd>
                  </div>
                ))}
                <p className="col-span-2 sm:col-span-4 text-[11px] text-foreground-muted leading-relaxed">
                  {info.sectorGroup} · {info.gameQuarter}분기 공시{" "}
                  <span className={SURPRISE[info.earningsSurprise].tone}>
                    {SURPRISE[info.earningsSurprise].label}
                  </span>{" "}
                  · 실적은 <b>가상 기업의 가정치</b>입니다(실재 기업의 재무가 아닙니다). 분기마다
                  새로 공시되며, 주가와 독립으로 만들어지므로 많이 오르면 PER이 올라갑니다.
                  {info.meme && (
                    <span className="text-[#DC2626]">
                      {" "}
                      밈 종목입니다 — <b>적자 상태</b>라 PER이 없습니다. 실적이 아니라 수급·화제성이
                      값을 만들고, 전용 뉴스(스퀴즈·반대매매)가 한 번에 8~28%를 밀어냅니다.
                    </span>
                  )}
                </p>
              </dl>
            )}

            {/* 상태 요약 — 선택 종목에만 계산된다 */}
            {data?.analysis && current.symbol === view.selected && (
              <GameAnalysisCard analysis={data.analysis} className="mt-4" />
            )}
          </section>

          <div className="space-y-4">
            {wallet && (
              <GameOrderForm
                symbol={current}
                rules={rulebookQ.data}
                investableKrw={wallet.investableKrw}
                disabled={open.isPending || wallet.seasonOver}
                onSubmit={(side, quantity, leverage) =>
                  open.mutate({ symbol: current.symbol, side, quantity, leverage })
                }
              />
            )}

            {data && (
              <MarketNewsFeed
                events={data.events}
                currentTick={data.tick}
                ticksPerGameDay={rulebookQ.data?.ticksPerGameDay ?? 60}
                selectedSymbol={current.symbol}
              />
            )}

            <section className="rounded-2xl border border-border bg-surface p-2">
              {/* 섹터 그룹 — 뉴스가 걸리는 단위와 같은 축이라 "업종 악재"가 어디에 닿는지 보인다 */}
              <div className="flex flex-wrap gap-1 px-1 pt-1 pb-2">
                {sectorGroups.map((group) => (
                  <button
                    key={group}
                    type="button"
                    onClick={() => setView((prev) => ({ ...prev, sector: group }))}
                    className={`h-7 rounded-lg px-2.5 text-[11px] font-medium transition-colors ${
                      view.sector === group
                        ? "bg-brand text-white"
                        : "text-foreground-muted hover:bg-black/[0.04]"
                    }`}
                  >
                    {group}
                  </button>
                ))}
              </div>
              <ul className="divide-y divide-border max-h-80 overflow-y-auto">
                {visibleSymbols.map((s) => {
                  const active = s.symbol === current.symbol;
                  return (
                    <li key={s.symbol}>
                      <button
                        type="button"
                        onClick={() => setView((prev) => ({ ...prev, selected: s.symbol }))}
                        aria-current={active}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors ${
                          active ? "bg-brand/8" : "hover:bg-black/[0.03]"
                        }`}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-1.5">
                            <span className="text-sm font-medium truncate">{s.name}</span>
                            {/* 밈 종목은 변동성이 다른 종목의 2배 이상이다 — 목록에서 바로 보이게 */}
                            {s.meme && (
                              <span className="shrink-0 rounded px-1 py-px text-[10px] font-bold bg-[#DC2626]/10 text-[#DC2626]">
                                밈
                              </span>
                            )}
                          </span>
                          <span className="block text-[11px] text-foreground-muted truncate">
                            {s.sector}
                          </span>
                        </span>
                        <GamePriceLine points={s.series} compact className="w-12 h-6 shrink-0" />
                        <span className="text-right shrink-0">
                          <span className="block text-sm font-semibold tabular-nums">
                            {s.priceKrw.toLocaleString()}
                          </span>
                          <span
                            className={`block text-[11px] font-medium tabular-nums ${toneOf(s.changePct)}`}
                          >
                            {signed(s.changePct)}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          </div>
        </div>
      )}

      {/* 보유 포지션 */}
      {wallet && (
        <section className="mt-6">
          <h2 className="text-sm font-bold tracking-tight mb-2">
            보유 포지션
            {wallet.positions.length > 0 && (
              <span className="ml-1.5 text-foreground-muted font-normal">
                {wallet.positions.length}건 · 평가 {won(wallet.positionValueKrw)}
              </span>
            )}
          </h2>
          <GamePositionList
            positions={wallet.positions}
            ticksPerGameDay={rulebookQ.data?.ticksPerGameDay ?? 60}
            currentTick={wallet.tick}
            closingId={close.isPending ? (close.variables ?? null) : null}
            onClose={(id) => close.mutate(id)}
          />
        </section>
      )}
    </div>
  );
}
