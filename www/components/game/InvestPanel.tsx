"use client";

import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import GameOrderForm from "@/components/game/GameOrderForm";
import GamePositionList from "@/components/game/GamePositionList";
import GameSymbolTable from "@/components/game/GameSymbolTable";
import GameSymbolDetail from "@/components/game/GameSymbolDetail";
import GameMarketSummary from "@/components/game/GameMarketSummary";
import FuturesPanel from "@/components/game/FuturesPanel";
import {
  ApiError,
  closeGameTrade,
  fetchGameFutures,
  fetchGamePrices,
  fetchGameRulebook,
  fetchGameWallet,
  openGameTrade,
} from "@/lib/api";
import { useUIStore } from "@/lib/uiStore";
import { useFavorites } from "@/lib/useFavorites";
import type { GameSymbolPrices } from "@/lib/types";
import { Button } from "@/components/ui/button";
import CountUp from "@/components/common/CountUp";

const CHART_TICKS = 120; // 게임 2일치 — 곡선 모양이 읽히는 최소 구간
// 지수는 완만해서 주식보다 긴 구간을 봐야 모양이 읽힌다. FuturesPanel과 같은 값이어야
// 쿼리 키가 맞아 캐시를 공유한다.
const FUTURES_TICKS = 240;
const DEFAULT_CANDLE_DAYS = 30;

const won = (v: number) => `${v.toLocaleString()}원`;
// signed는 **퍼센트 전용**이다. 원화 손익에 쓰면 "-243328848.00%원"이 된다(실사고) — 금액은 signedWon.
// 수익률이 네 자리를 넘는 값이 실제로 나오므로(레버리지 시즌) 콤마를 넣는다: +11,716.48%
const signed = (v: number) =>
  `${v >= 0 ? "+" : ""}${v.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
const signedWon = (v: number) => `${v >= 0 ? "+" : ""}${v.toLocaleString()}원`;
const toneOf = (v: number) => (v >= 0 ? "text-up" : "text-down");

// 폭 상한 — 대시보드 예외 폭(DESIGN.md §5)
const SHELL = "mx-auto w-full max-w-[1720px] px-4 sm:px-6";

/**
 * 투자 탭 — 레퍼런스(토스증권 홈)의 골격을 따른다.
 *
 *   [마켓 요약: GXI + 섹터]                ← 얇게
 *   [표 (주인공, 내부 스크롤) | 상세·주문 컬럼]
 *   [하단 고정 티커 바]
 *
 * 지갑은 **한 줄**이다 — 토스 홈에 계좌 정보가 없는 것처럼, 자산 카드가 화면 위 절반을
 * 먹고 정작 표가 접혀 있던 이전 구조를 버렸다.
 */
export default function InvestPanel() {
  // 선택 종목 · 체결 안내 · 봉 기간 · 시장 세그먼트(REACT_RULES 패턴 B: 단일 객체)
  const [view, setView] = useState<{
    market: "stock" | "futures";
    selected: string | null;
    notice: string | null;
    candleDays: number;
  }>({ market: "stock", selected: null, notice: null, candleDays: DEFAULT_CANDLE_DAYS });

  const openAuth = useUIStore((s) => s.openAuth);
  const queryClient = useQueryClient();
  const { favorites, toggle: toggleFavorite } = useFavorites("game:favorites");

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

  // 지수·선물 — 마켓 요약·티커 바가 쓴다. FuturesPanel과 같은 쿼리 키라 캐시를 공유한다.
  const futuresQ = useQuery({
    queryKey: ["game-futures", FUTURES_TICKS],
    queryFn: () => fetchGameFutures(FUTURES_TICKS),
    refetchInterval: (query) => (query.state.status === "error" ? 300_000 : 30_000),
    placeholderData: keepPreviousData,
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
  const current: GameSymbolPrices | undefined =
    symbols.find((s) => s.symbol === view.selected) ?? symbols[0];
  const unauthorized =
    (pricesQ.error as ApiError)?.status === 401 || (walletQ.error as ApiError)?.status === 401;

  // 섹터별 평균 등락 — 하단 티커 바용(산술평균이라 대형주 가중이 없다)
  const sectorMoves = useMemo(() => {
    const buckets = new Map<string, number[]>();
    symbols.forEach((s) => {
      const list = buckets.get(s.sectorGroup) ?? [];
      list.push(s.changePct);
      buckets.set(s.sectorGroup, list);
    });
    return Array.from(buckets, ([group, values]) => ({
      group,
      changePct: values.reduce((a, b) => a + b, 0) / values.length,
    })).sort((a, b) => b.changePct - a.changePct);
  }, [symbols]);

  // 주문 + 보유 — lg(2열)에서는 상세 컬럼 아래에, 2xl(3열)에서는 전용 컬럼에 들어간다.
  // JSX 변수로 둔다: 렌더 안에서 컴포넌트로 정의하면 매 렌더마다 리마운트되어 폼 상태가 날아간다.
  const orderColumn =
    current && wallet ? (
      <>
        <GameOrderForm
          symbol={current}
          rules={rulebookQ.data}
          investableKrw={wallet.investableKrw}
          disabled={open.isPending || wallet.seasonOver}
          onSubmit={(side, quantity, leverage) =>
            open.mutate({ symbol: current.symbol, side, quantity, leverage })
          }
        />
        <section>
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
      </>
    ) : null;

  if (unauthorized) {
    return (
      <div className={`${SHELL} mt-8`}>
        <div className="rounded-2xl border border-border bg-surface p-8 text-center">
          <p className="text-sm text-foreground-muted">
            게임은 누구나 이용할 수 있지만, 자산을 저장하려면 로그인이 필요합니다.
          </p>
          <Button type="button" onClick={() => openAuth("login")} className="mt-5">
            로그인하고 시작하기
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* 세그먼트 + 지갑 한 줄 — 토스의 전체/국내/해외 자리 + 계좌는 문장이 아니라 숫자 세 개.
          페이지 탭(투자/상권창업)이 이미 알약이라 여기는 **밑줄 탭**으로 층을 가른다 —
          같은 모양의 알약이 두 줄 겹치면 위계 없이 어수선하다(실화면 지적). */}
      <div className={`${SHELL} shrink-0 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border`}>
        <div className="flex items-center gap-1" role="tablist" aria-label="시장 선택">
          {(
            [
              ["stock", "주식"],
              ["futures", "지수 선물"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={view.market === key}
              onClick={() => setView((p) => ({ ...p, market: key }))}
              className={`h-9 px-3 -mb-px border-b-2 text-sm font-semibold transition-colors duration-150 ${
                view.market === key
                  ? "border-brand text-foreground"
                  : "border-transparent text-foreground-muted hover:text-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {wallet && (
          <dl className="ml-auto flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm tabular-nums">
            <div className="flex items-baseline gap-1.5">
              <dt className="text-xs text-foreground-muted">총자산</dt>
              <dd className="font-semibold">
                <CountUp value={wallet.totalAssetKrw} format={won} />
              </dd>
            </div>
            <div className="flex items-baseline gap-1.5">
              <dt className="text-xs text-foreground-muted">수익률</dt>
              <dd className={`font-semibold ${toneOf(wallet.totalReturnPct)}`}>
                {signed(wallet.totalReturnPct)}
              </dd>
            </div>
            <div className="flex items-baseline gap-1.5">
              <dt className="text-xs text-foreground-muted">투자 가능</dt>
              <dd className="font-semibold">
                <CountUp value={wallet.investableKrw} format={won} />
              </dd>
            </div>
          </dl>
        )}
      </div>

      {/* 상태 알림 — 전부 한 줄씩. 카드로 쌓으면 표가 밀린다 */}
      <div className={`${SHELL} shrink-0`}>
        {view.notice && (
          <p className="mt-2 rounded-lg bg-brand/8 border border-brand/20 px-3 py-1.5 text-xs">
            {view.notice}
          </p>
        )}
        {data && !data.calibrated && (
          <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-foreground-muted">
            <TriangleAlert size={12} strokeWidth={2} className="text-amber-600" />
            종목 변동성은 실데이터 캘리브레이션 전 잠정값입니다.
          </p>
        )}
        {data && data.tick === 0 && (
          <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-foreground-muted">
            <TriangleAlert size={12} strokeWidth={2} className="text-amber-600" />
            시즌이 아직 시작되지 않았습니다 — 지금 값은 전 종목의 시즌 시작가입니다.
          </p>
        )}
        {(wallet?.recentlyClosed?.length ?? 0) > 0 && (
          <p className="mt-1.5 text-xs text-amber-900 tabular-nums">
            자리를 비운 사이 —{" "}
            {wallet?.recentlyClosed?.slice(0, 2).map((c, i) => (
              <span key={c.id}>
                {i > 0 && " · "}
                {c.name}{" "}
                {c.reason === "liquidated" ? "강제청산" : c.reason === "expired" ? "만료 마감" : "만기 정산"}
                <b className={`ml-0.5 ${toneOf(c.realizedPnlKrw)}`}>{signedWon(c.realizedPnlKrw)}</b>
              </span>
            ))}
            {(wallet?.recentlyClosed?.length ?? 0) > 2 && ` 외 ${wallet!.recentlyClosed!.length - 2}건`}
          </p>
        )}
      </div>

      {view.market === "stock" ? (
        <>
          {pricesQ.isLoading && (
            <div className="flex-1 grid place-items-center text-sm text-foreground-muted">
              시세를 불러오는 중…
            </div>
          )}

          {current && (
            <div
              className={`${SHELL} flex-1 min-h-0 mt-3 overflow-y-auto lg:overflow-hidden lg:grid lg:grid-cols-[minmax(0,1fr)_400px] 2xl:grid-cols-[minmax(0,1fr)_420px_320px] lg:gap-4`}
            >
              {/* 주인공 — 표. 데스크탑은 컬럼 내부에서만 스크롤한다 */}
              <div className="lg:h-full lg:min-h-0">
                <GameSymbolTable
                  symbols={symbols}
                  selected={current.symbol}
                  favorites={favorites}
                  onSelect={(symbol) => setView((prev) => ({ ...prev, selected: symbol }))}
                  onToggleFavorite={toggleFavorite}
                />
              </div>

              {/* 선택 종목 상세 — 토스의 종목 미니 패널 자리 */}
              <aside className="mt-4 lg:mt-0 lg:h-full lg:min-h-0 lg:overflow-y-auto flex flex-col gap-4 pb-4">
                <GameSymbolDetail
                  current={current}
                  data={data}
                  events={data?.events ?? []}
                  ticksPerGameDay={rulebookQ.data?.ticksPerGameDay ?? 60}
                  candleDays={view.candleDays}
                  onCandleDaysChange={(days) => setView((prev) => ({ ...prev, candleDays: days }))}
                  isSelected={current.symbol === view.selected}
                />
                {/* lg(2열)에서는 주문·보유가 이 컬럼에 이어진다 — 2xl에서는 세 번째 컬럼이 가져간다.
                    두 자리 모두 마운트되는 대신 CSS로 한쪽만 보인다(1536px 경계에서 입력 중이던
                    수량은 초기화될 수 있다 — 감수). */}
                <div className="2xl:hidden flex flex-col gap-4">{orderColumn}</div>
              </aside>

              {/* 주문 컬럼 — 토스는 주문 패널이 항상 보인다. 차트 아래로 밀지 않는다(실화면 지적) */}
              <aside className="hidden 2xl:flex 2xl:h-full 2xl:min-h-0 2xl:overflow-y-auto flex-col gap-4 pb-4">
                {orderColumn}
              </aside>
            </div>
          )}

          {/* 마켓 요약은 표 아래가 아니라 모바일 스크롤 최하단으로 밀지 않도록 티커 바 위에 두지
              않는다 — 데스크탑에서는 표가 이미 주인공이므로 요약은 접근 부담이 없는 하단 티커와
              지수 카드(GameMarketSummary)를 상세 컬럼 위에 두는 대신 티커 바가 대신한다. */}
        </>
      ) : (
        <div className={`${SHELL} flex-1 min-h-0 overflow-y-auto mt-3 pb-4`}>
          <div className="mb-3">
            <GameMarketSummary futures={futuresQ.data} symbols={symbols} />
          </div>
          <FuturesPanel />
        </div>
      )}

      {/* 하단 고정 티커 바 — 레퍼런스(토스증권)의 지수 스트립. 흐르지 않고 서 있다 */}
      <div className="shrink-0 border-t border-border bg-surface">
        <div
          className={`${SHELL} flex items-center gap-5 py-1.5 overflow-x-auto whitespace-nowrap text-xs [scrollbar-width:none] [&::-webkit-scrollbar]:hidden`}
        >
          {futuresQ.data && (
            <>
              <Tick label="GXI" value={futuresQ.data.indexPoint.toLocaleString()} />
              <Tick label="선물" value={futuresQ.data.futuresPoint.toLocaleString()} />
              <Tick
                label="베이시스"
                value={signed(futuresQ.data.basisPct)}
                tone={toneOf(futuresQ.data.basisPct)}
              />
              <Tick
                label="만기"
                value={`D-${Math.max(0, Math.ceil(futuresQ.data.ticksToExpiry / 60))}`}
              />
              <span className="h-3.5 w-px bg-border shrink-0" aria-hidden />
            </>
          )}
          {sectorMoves.map((s) => (
            <Tick key={s.group} label={s.group} value={signed(s.changePct)} tone={toneOf(s.changePct)} />
          ))}
        </div>
      </div>
    </div>
  );
}

function Tick({ label, value, tone = "" }: { label: string; value: string; tone?: string }) {
  return (
    <span className="inline-flex items-baseline gap-1.5 shrink-0">
      <span className="text-foreground-muted">{label}</span>
      <span className={`font-semibold tabular-nums ${tone}`}>{value}</span>
    </span>
  );
}
