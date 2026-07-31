"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Gamepad2, Info, TriangleAlert } from "lucide-react";
import GamePriceLine from "@/components/game/GamePriceLine";
import { ApiError, fetchGamePrices, fetchGameRulebook } from "@/lib/api";
import { useUIStore } from "@/lib/uiStore";
import type { GameSymbolPrices } from "@/lib/types";

const CHART_TICKS = 120; // 게임 2일치 — 곡선 모양이 읽히는 최소 구간

const won = (v: number) => `${v.toLocaleString()}원`;
const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const toneOf = (v: number) => (v >= 0 ? "text-[#DC2626]" : "text-[#2563EB]");

export default function GamePage() {
  // 선택 종목 하나뿐 — 나머지는 서버 응답이라 상태로 들 것이 없다(REACT_RULES: useState 1개)
  const [selected, setSelected] = useState<string | null>(null);
  const openAuth = useUIStore((s) => s.openAuth);

  // 규칙·게임 시각 — 진입 시 한 번. 시각은 시세 응답에도 실려 오므로 자주 부를 이유가 없다.
  const rulebookQ = useQuery({
    queryKey: ["game-rulebook"],
    queryFn: fetchGameRulebook,
    staleTime: 10 * 60_000,
  });

  // 시세 — 탭 활성 시 30초 폴링. 결정론 계산이라 같은 틱을 다시 물어도 같은 값이다.
  // 에러 시 5분 저속 재시도(주식 화면과 같은 관례 — 일시 오류로 갱신이 영구 중단되지 않게).
  const pricesQ = useQuery({
    queryKey: ["game-prices", CHART_TICKS],
    queryFn: () => fetchGamePrices(CHART_TICKS),
    refetchInterval: (query) => (query.state.status === "error" ? 300_000 : 30_000),
  });

  const data = pricesQ.data;
  const symbols = data?.symbols ?? [];
  const current: GameSymbolPrices | undefined =
    symbols.find((s) => s.symbol === selected) ?? symbols[0];

  return (
    <div className="mx-auto w-full max-w-6xl px-4 sm:px-6 py-6 sm:py-8">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="grid place-items-center w-9 h-9 rounded-xl bg-brand/10 text-brand">
          <Gamepad2 size={19} strokeWidth={1.9} />
        </span>
        <h1 className="text-xl font-bold tracking-tight">모의 투자</h1>

        {rulebookQ.data && (
          <span className="text-sm text-foreground-muted">
            {rulebookQ.data.gameQuarter}분기 {rulebookQ.data.dayOfQuarter}일차
            <span className="mx-1.5 text-border">·</span>
            시즌 {Math.ceil(rulebookQ.data.ticksRemaining / 60 / 24)}일 남음
          </span>
        )}

        <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-amber-50 border border-amber-200 px-3 py-1 text-xs font-medium text-amber-800">
          <Info size={13} strokeWidth={2} />
          가상 주가 · 실제 시세가 아닙니다
        </span>
      </header>

      <p className="mt-3 text-sm text-foreground-muted leading-relaxed">
        실제 1시간이 게임 1일입니다. 접속하지 않는 동안에도 시세가 움직이며, 모든 참가자가 같은
        장을 봅니다. 종목은 가상의 회사이고 업종만 실제 시장에서 가져왔습니다.
      </p>

      {data && !data.calibrated && (
        <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-foreground-muted">
          <TriangleAlert size={13} strokeWidth={2} className="text-amber-600" />
          종목 변동성은 실데이터 캘리브레이션 전 잠정값입니다.
        </p>
      )}

      {pricesQ.isLoading && (
        <div className="mt-8 grid place-items-center h-64 text-sm text-foreground-muted">
          시세를 불러오는 중…
        </div>
      )}

      {pricesQ.isError && (
        <div className="mt-8 rounded-2xl border border-border bg-surface p-8 text-center">
          {(pricesQ.error as ApiError)?.status === 401 ? (
            <>
              {/* 등급 제한은 없지만 로그인은 필요하다 — 지갑·보유 종목이 유저별이다 */}
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
            </>
          ) : (
            <p className="text-sm text-foreground-muted">
              시세를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
            </p>
          )}
        </div>
      )}

      {current && (
        <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_360px]">
          {/* 선택 종목 큰 차트 */}
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

            <GamePriceLine points={current.series} className="mt-4 w-full h-56 sm:h-72" />

            <p className="mt-3 text-xs text-foreground-muted">
              최근 게임 {Math.round(current.series.length / 60)}일 · 등락률은 게임 1일(현실 1시간)
              전 대비
            </p>
          </section>

          {/* 종목 목록 */}
          <section className="rounded-2xl border border-border bg-surface p-2 overflow-hidden">
            <ul className="divide-y divide-border max-h-[32rem] overflow-y-auto">
              {symbols.map((s) => {
                const active = s.symbol === current.symbol;
                return (
                  <li key={s.symbol}>
                    <button
                      type="button"
                      onClick={() => setSelected(s.symbol)}
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

                      <GamePriceLine points={s.series} compact className="w-14 h-7 shrink-0" />

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
      )}
    </div>
  );
}
