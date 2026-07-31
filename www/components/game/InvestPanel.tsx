"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info, TriangleAlert } from "lucide-react";
import GameOrderForm from "@/components/game/GameOrderForm";
import MarketNewsFeed from "@/components/game/MarketNewsFeed";
import GamePositionList from "@/components/game/GamePositionList";
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

const won = (v: number) => `${v.toLocaleString()}원`;
const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const toneOf = (v: number) => (v >= 0 ? "text-[#DC2626]" : "text-[#2563EB]");

export default function InvestPanel() {
  // 선택 종목 + 마지막 체결 안내. 나머지는 서버 응답이라 상태로 들 것이 없다
  // (REACT_RULES 패턴 B: 여러 값은 단일 객체로)
  const [view, setView] = useState<{ selected: string | null; notice: string | null }>({
    selected: null,
    notice: null,
  });
  const openAuth = useUIStore((s) => s.openAuth);
  const queryClient = useQueryClient();

  const rulebookQ = useQuery({
    queryKey: ["game-rulebook"],
    queryFn: fetchGameRulebook,
    staleTime: 10 * 60_000,
  });

  // 시세 — 결정론 계산이라 같은 틱을 다시 물어도 같은 값이다. 에러 시 5분 저속 재시도.
  const pricesQ = useQuery({
    queryKey: ["game-prices", CHART_TICKS],
    queryFn: () => fetchGamePrices(CHART_TICKS),
    refetchInterval: (query) => (query.state.status === "error" ? 300_000 : 30_000),
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
    }: {
      symbol: string;
      side: "LONG" | "SHORT";
      quantity: number;
    }) => openGameTrade(symbol, side, quantity),
    onSuccess: (r) => {
      refresh();
      setView((prev) => ({
        ...prev,
        notice: `${r.name} ${r.side === "LONG" ? "롱" : "숏"} ${r.quantity.toLocaleString()}주 체결 · ${won(r.priceKrw)}`,
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

            <GamePriceLine points={current.series} className="mt-4 w-full h-56 sm:h-64" />

            <p className="mt-3 text-xs text-foreground-muted">
              최근 게임 {Math.round(current.series.length / 60)}일 · 등락률은 게임 1일(현실 1시간)
              전 대비
            </p>
          </section>

          <div className="space-y-4">
            {wallet && (
              <GameOrderForm
                symbol={current}
                rules={rulebookQ.data}
                investableKrw={wallet.investableKrw}
                disabled={open.isPending || wallet.seasonOver}
                onSubmit={(side, quantity) =>
                  open.mutate({ symbol: current.symbol, side, quantity })
                }
              />
            )}

            {data && (
              <MarketNewsFeed
                events={data.events}
                currentTick={data.tick}
                ticksPerGameDay={rulebookQ.data?.ticksPerGameDay ?? 60}
              />
            )}

            <section className="rounded-2xl border border-border bg-surface p-2">
              <ul className="divide-y divide-border max-h-80 overflow-y-auto">
                {symbols.map((s) => {
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
                          <span className="block text-sm font-medium truncate">{s.name}</span>
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
