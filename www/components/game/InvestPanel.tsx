"use client";

import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info, TriangleAlert } from "lucide-react";
import GameOrderForm from "@/components/game/GameOrderForm";
import GamePositionList from "@/components/game/GamePositionList";
import GameSymbolTable from "@/components/game/GameSymbolTable";
import GameSymbolDetail from "@/components/game/GameSymbolDetail";
import {
  ApiError,
  closeGameTrade,
  fetchGamePrices,
  fetchGameRulebook,
  fetchGameWallet,
  openGameTrade,
} from "@/lib/api";
import { useUIStore } from "@/lib/uiStore";
import { useFavorites } from "@/lib/useFavorites";
import type { GameSymbolPrices } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Marquee } from "@/components/ui/marquee";
import CountUp from "@/components/common/CountUp";

const CHART_TICKS = 120; // 게임 2일치 — 곡선 모양이 읽히는 최소 구간
const DEFAULT_CANDLE_DAYS = 30;

const won = (v: number) => `${v.toLocaleString()}원`;
const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const toneOf = (v: number) => (v >= 0 ? "text-up" : "text-down");

export default function InvestPanel() {
  // 선택 종목 · 체결 안내 · 봉 기간. 봉 기간은 쿼리 키에 들어가므로 여기가 소유한다.
  // (REACT_RULES 패턴 B: 여러 값은 단일 객체로)
  const [view, setView] = useState<{
    selected: string | null;
    notice: string | null;
    candleDays: number;
  }>({ selected: null, notice: null, candleDays: DEFAULT_CANDLE_DAYS });

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

  // 섹터 지수 — 게임에는 지수가 없어 섹터 그룹별 평균 등락률로 만든다.
  // 레퍼런스(토스증권) 하단 티커 자리이며, 여기서는 "이 게임 장이 어느 쪽으로 움직이나"를 말한다.
  const sectorIndex = useMemo(() => {
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
          시즌이 아직 시작되지 않았습니다 — 지금 보이는 값은 전 종목의 시즌 시작가입니다. 시작되면
          1분마다 게임 1일이 흐릅니다.
        </p>
      )}

      {unauthorized && (
        <div className="mt-8 rounded-2xl border border-border bg-surface p-8 text-center">
          <p className="text-sm text-foreground-muted">
            게임은 누구나 이용할 수 있지만, 자산을 저장하려면 로그인이 필요합니다.
          </p>
          <Button type="button" onClick={() => openAuth("login")} className="mt-5">
            로그인하고 시작하기
          </Button>
        </div>
      )}

      {pricesQ.isLoading && !unauthorized && (
        <div className="mt-8 grid place-items-center h-64 text-sm text-foreground-muted">
          시세를 불러오는 중…
        </div>
      )}

      {/* 섹터 지수 티커 — 종목을 고르기 전에 장 전체가 어느 쪽인지 먼저 보인다 */}
      {sectorIndex.length > 0 && (
        <div className="mt-5 rounded-2xl border border-border bg-surface py-2">
          <Marquee duration="45s" className="[--gap:2rem]">
            {sectorIndex.map((s) => (
              <span key={s.group} className="inline-flex items-baseline gap-1.5 whitespace-nowrap text-xs">
                <span className="text-foreground-muted">{s.group}</span>
                <span className={`font-semibold tabular-nums ${toneOf(s.changePct)}`}>
                  {signed(s.changePct)}
                </span>
              </span>
            ))}
          </Marquee>
        </div>
      )}

      {/* 자산 요약 */}
      {wallet && (
        <section className="mt-4 rounded-2xl border border-border bg-surface p-5 grid grid-cols-2 sm:grid-cols-4 gap-4">
          {/* 금액은 체결·정산으로 계속 바뀌므로 굴러가게 둔다. 수익률은 소수라
              중간값이 튀어 읽기 나빠지므로 그대로 찍는다. */}
          {[
            { label: "총자산", raw: wallet.totalAssetKrw, format: won, animate: true, tone: "" },
            {
              label: "수익률",
              raw: wallet.totalReturnPct,
              format: signed,
              animate: false,
              tone: toneOf(wallet.totalReturnPct),
            },
            { label: "현금", raw: wallet.cashKrw, format: won, animate: true, tone: "" },
            { label: "투자 가능", raw: wallet.investableKrw, format: won, animate: true, tone: "" },
          ].map((item) => (
            <div key={item.label}>
              <dt className="text-xs text-foreground-muted">{item.label}</dt>
              <dd className={`mt-0.5 text-data-l tabular-nums ${item.tone}`}>
                {item.animate ? (
                  <CountUp value={item.raw} format={item.format} />
                ) : (
                  item.format(item.raw)
                )}
              </dd>
            </div>
          ))}
          <p className="col-span-2 sm:col-span-4 text-xs text-foreground-muted">
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

      {/* 3열 — [목록 | 상세 | 주문]. 레퍼런스(토스증권)처럼 목록이 상세와 함께 남는다.
          2xl 미만에서는 폭이 모자라 [상세 | 주문] 2열 + 목록을 아래로 내린다. */}
      {current && (
        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px] 2xl:grid-cols-[340px_minmax(0,1fr)_320px]">
          <div className="order-2 xl:order-3 xl:col-span-2 2xl:order-1 2xl:col-span-1">
            <GameSymbolTable
              symbols={symbols}
              selected={current.symbol}
              favorites={favorites}
              onSelect={(symbol) => setView((prev) => ({ ...prev, selected: symbol }))}
              onToggleFavorite={toggleFavorite}
            />
          </div>

          <div className="order-1 xl:order-1 2xl:order-2 min-w-0">
            <GameSymbolDetail
              current={current}
              data={data}
              events={data?.events ?? []}
              ticksPerGameDay={rulebookQ.data?.ticksPerGameDay ?? 60}
              candleDays={view.candleDays}
              onCandleDaysChange={(days) => setView((prev) => ({ ...prev, candleDays: days }))}
              isSelected={current.symbol === view.selected}
            />
          </div>

          <div className="order-3 xl:order-2">
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
