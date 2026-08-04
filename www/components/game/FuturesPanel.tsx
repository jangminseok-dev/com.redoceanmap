"use client";

import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info, TrendingDown, TrendingUp } from "lucide-react";
import GamePriceLine from "@/components/game/GamePriceLine";
import { ApiError, closeGameFutures, fetchGameFutures, openGameFutures } from "@/lib/api";
import { useUIStore } from "@/lib/uiStore";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const CHART_TICKS = 240; // 지수는 완만해서 주식보다 긴 구간을 봐야 모양이 읽힌다

const won = (v: number) => `${v.toLocaleString()}원`;
const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toLocaleString()}`;
const toneOf = (v: number) => (v >= 0 ? "text-up" : "text-down");

/**
 * 지수 선물 — 근월물 하나.
 *
 * 중도 강제청산이 없다. 만기 구간의 지수 변동이 증거금(20%)에 못 미쳐 손실 상한만으로
 * 충분하기 때문이며, 그래서 만기까지 들고 가거나 중간에 직접 청산하는 두 갈래만 있다.
 * 만기가 지난 계약은 조회 시점에 현물 지수로 자동 정산된다.
 */
export default function FuturesPanel() {
  // 방향·계약 수를 실시간으로 반영해 증거금을 보여준다(REACT_RULES 패턴 B: 단일 객체)
  const [order, setOrder] = useState<{
    side: "LONG" | "SHORT";
    contracts: number;
    notice: string | null;
  }>({ side: "LONG", contracts: 1, notice: null });

  const openAuth = useUIStore((s) => s.openAuth);
  const queryClient = useQueryClient();

  const marketQ = useQuery({
    queryKey: ["game-futures", CHART_TICKS],
    queryFn: () => fetchGameFutures(CHART_TICKS),
    refetchInterval: (query) => (query.state.status === "error" ? 300_000 : 30_000),
    placeholderData: keepPreviousData,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["game-futures", CHART_TICKS] });
    queryClient.invalidateQueries({ queryKey: ["game-wallet"] });
  };

  const open = useMutation({
    mutationFn: () => openGameFutures(order.side, order.contracts),
    onSuccess: (r) => {
      refresh();
      setOrder((prev) => ({
        ...prev,
        notice: `${r.contractCode} ${r.side === "LONG" ? "매수" : "매도"} ${r.contracts}계약 · ${r.futuresPoint.toLocaleString()}pt · 증거금 ${won(r.marginKrw)}`,
      }));
    },
    onError: (e) =>
      setOrder((prev) => ({ ...prev, notice: (e as ApiError).message ?? "주문에 실패했습니다." })),
  });

  const close = useMutation({
    mutationFn: (positionId: number) => closeGameFutures(positionId),
    onSuccess: (r) => {
      refresh();
      setOrder((prev) => ({
        ...prev,
        notice: `${r.contractCode} 마감 · 실현손익 ${signed(r.realizedPnlKrw ?? 0)}원`,
      }));
    },
    onError: (e) =>
      setOrder((prev) => ({ ...prev, notice: (e as ApiError).message ?? "청산에 실패했습니다." })),
  });

  const data = marketQ.data;
  const unauthorized = (marketQ.error as ApiError)?.status === 401;

  if (unauthorized) {
    return (
      <div className="mt-6 rounded-2xl border border-border bg-surface p-8 text-center">
        <p className="text-sm">로그인하면 선물 시장에 참여할 수 있습니다.</p>
        <button
          type="button"
          onClick={() => openAuth("login")}
          className="mt-3 h-10 px-5 rounded-xl bg-brand text-white text-sm font-semibold hover:bg-brand-deep transition-colors"
        >
          로그인
        </button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mt-6 rounded-2xl border border-border bg-surface p-8 text-center text-sm text-foreground-muted">
        {marketQ.isLoading ? "선물 시장을 불러오는 중…" : "선물 시장을 열 수 없습니다."}
      </div>
    );
  }

  const margin = data.marginPerContractKrw * order.contracts;
  const overBudget = margin > data.investableKrw;
  const expiryGameDays = Math.max(0, Math.ceil(data.ticksToExpiry / 60));
  const contango = data.basisPct >= 0;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 border border-amber-200 px-3 py-1 text-xs font-medium text-amber-800">
          <Info size={13} strokeWidth={2} />
          가상 지수입니다. 실제 지수·선물과 무관합니다
        </span>
        <span className="text-xs text-foreground-muted">
          {data.gameQuarter}분기 {data.gameDay}일차
        </span>
      </div>

      {order.notice && (
        <p className="mt-3 rounded-xl bg-brand/8 border border-brand/20 px-4 py-2.5 text-sm">
          {order.notice}
        </p>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_320px]">
        <section className="rounded-2xl border border-border bg-surface p-5">
          <div className="flex items-baseline gap-2 flex-wrap">
            <h2 className="text-lg font-bold tracking-tight">GXI 지수</h2>
            <span className="text-xs text-foreground-muted">{data.contractCode}</span>
            <span className="ml-auto text-xl font-bold tabular-nums">
              {data.indexPoint.toLocaleString()}
              <span className="ml-1 text-sm font-normal text-foreground-muted">pt</span>
            </span>
          </div>

          <GamePriceLine
            points={data.series.map((p) => ({ tick: p.tick, priceKrw: p.point }))}
            className="mt-4 w-full h-56 sm:h-64"
          />

          <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 border-t border-border pt-4">
            <div>
              <dt className="text-xs text-foreground-muted">선물가</dt>
              <dd className="text-sm font-semibold tabular-nums">
                {data.futuresPoint.toLocaleString()}pt
              </dd>
            </div>
            <div>
              <dt className="text-xs text-foreground-muted">베이시스</dt>
              <dd className="text-sm font-semibold tabular-nums">
                {data.basisPct >= 0 ? "+" : ""}
                {data.basisPct.toFixed(2)}%
                <span className="ml-1 text-xs font-normal text-foreground-muted">
                  {contango ? "콘탱고" : "백워데이션"}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-foreground-muted">만기까지</dt>
              <dd className="text-sm font-semibold tabular-nums">
                게임 {expiryGameDays}일 ({data.ticksToExpiry}틱)
              </dd>
            </div>
            <div>
              <dt className="text-xs text-foreground-muted">1계약 명목</dt>
              <dd className="text-sm font-semibold tabular-nums">{won(data.contractValueKrw)}</dd>
            </div>
            <p className="col-span-2 sm:col-span-4 text-xs leading-relaxed text-foreground-muted">
              지수는 게임 종목 12개 상대가격의 기하평균입니다. 선물가는 만기가 가까울수록
              현물에 수렴하며, 만기에는 그 시점 현물 지수로 정산됩니다.
            </p>
          </dl>
        </section>

        <div className="space-y-4">
          <div className="rounded-2xl border border-border bg-surface p-5">
            <h3 className="text-sm font-bold tracking-tight">근월물 주문</h3>

            <div className="mt-3 grid grid-cols-2 gap-2">
              {(["LONG", "SHORT"] as const).map((side) => {
                const active = order.side === side;
                const isLong = side === "LONG";
                return (
                  <button
                    key={side}
                    type="button"
                    onClick={() => setOrder((prev) => ({ ...prev, side }))}
                    aria-pressed={active}
                    className={`flex items-center justify-center gap-1.5 h-10 rounded-xl text-sm font-medium border transition-colors ${
                      active
                        ? isLong
                          ? "bg-up text-white border-transparent"
                          : "bg-down text-white border-transparent"
                        : "border-border text-foreground-muted hover:bg-accent"
                    }`}
                  >
                    {isLong ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
                    {isLong ? "매수" : "매도"}
                  </button>
                );
              })}
            </div>

            <label className="mt-4 block text-xs text-foreground-muted" htmlFor="futures-contracts">
              계약 수
            </label>
            <div className="mt-1 flex gap-2">
              <Input
                id="futures-contracts"
                type="number"
                min={1}
                value={order.contracts}
                onChange={(e) =>
                  setOrder((prev) => ({
                    ...prev,
                    contracts: Math.max(1, Math.min(Number(e.target.value), 1_000)),
                  }))
                }
                className="flex-1 h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-brand/30"
              />
              <button
                type="button"
                onClick={() =>
                  setOrder((prev) => ({ ...prev, contracts: Math.max(1, data.maxContracts) }))
                }
                disabled={data.maxContracts < 1}
                className="px-3 h-10 rounded-xl border border-border text-xs font-medium text-foreground-muted hover:bg-accent disabled:opacity-40"
              >
                최대 {data.maxContracts}
              </button>
            </div>

            <dl className="mt-4 space-y-1 text-xs">
              <div className="flex justify-between">
                <dt className="text-foreground-muted">명목 금액</dt>
                <dd className="tabular-nums">{won(data.contractValueKrw * order.contracts)}</dd>
              </div>
              <div className="flex justify-between font-semibold border-t border-border pt-1 mt-1">
                <dt>증거금 ({Math.round(data.marginRatio * 100)}%)</dt>
                <dd className={`tabular-nums ${overBudget ? "text-up" : ""}`}>
                  {won(margin)}
                </dd>
              </div>
            </dl>

            <p className="mt-2 text-xs leading-relaxed text-foreground-muted">
              중도 강제청산은 없습니다 — 손실은 증거금까지입니다. 만기(게임 {expiryGameDays}일 뒤)가
              지나면 접속하지 않아도 현물 지수로 자동 정산됩니다.
            </p>

            <Button
              type="button"
              onClick={() => open.mutate()}
              disabled={open.isPending || overBudget || data.seasonOver || data.ticksToExpiry < 5}
              size="lg"
              className="mt-4 w-full"
            >
              {data.seasonOver
                ? "시즌이 끝났습니다"
                : data.ticksToExpiry < 5
                  ? "만기가 임박해 진입할 수 없습니다"
                  : overBudget
                    ? "증거금이 부족합니다"
                    : `${order.contracts}계약 ${order.side === "LONG" ? "매수" : "매도"}`}
            </Button>
          </div>
        </div>
      </div>

      <section className="mt-6">
        <h3 className="text-sm font-bold tracking-tight">보유 선물</h3>
        {data.positions.length === 0 ? (
          <p className="mt-2 rounded-2xl border border-border bg-surface p-6 text-center text-sm text-foreground-muted">
            보유한 선물이 없습니다.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {data.positions.map((p) => (
              <li
                key={p.id}
                className="rounded-2xl border border-border bg-surface p-4 flex flex-wrap items-center gap-x-4 gap-y-2"
              >
                <span
                  className={`px-2 py-0.5 rounded-md text-xs font-bold text-white ${
                    p.side === "LONG" ? "bg-up" : "bg-down"
                  }`}
                >
                  {p.side === "LONG" ? "매수" : "매도"}
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold truncate">{p.contractCode}</span>
                  <span className="block text-xs text-foreground-muted">
                    {p.contracts}계약 · {won(p.entryPriceKrw)} 진입 · 만기까지{" "}
                    {Math.max(0, Math.ceil(p.ticksToExpiry / 60))}게임일
                  </span>
                </span>
                <span className="ml-auto text-right">
                  <span className="block text-sm tabular-nums">{won(p.currentPriceKrw)}</span>
                  <span className={`block text-xs tabular-nums ${toneOf(p.unrealizedPnlKrw)}`}>
                    {signed(p.unrealizedPnlKrw)}원 ({p.unrealizedPct >= 0 ? "+" : ""}
                    {p.unrealizedPct.toFixed(2)}%)
                  </span>
                  <span className="block text-xs text-foreground-muted tabular-nums">
                    지금 청산 시 {won(p.marketValueKrw)}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => close.mutate(p.id)}
                  disabled={close.isPending}
                  className="px-3 h-10 rounded-xl border border-border text-xs font-medium hover:bg-accent disabled:opacity-40 transition-colors"
                >
                  {close.isPending ? "청산 중…" : "청산"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
