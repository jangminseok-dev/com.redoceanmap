"use client";

import type { GameFuturesMarket, GameSymbolPrices } from "@/lib/types";
import GamePriceLine from "./GamePriceLine";

const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const toneOf = (v: number) => (v >= 0 ? "text-up" : "text-down");

/**
 * 마켓 요약 — 레퍼런스(토스증권) 홈 상단 박스에 대응한다.
 *
 * 왼쪽에 지수 하나를 크게 놓고 오른쪽에 나머지를 격자로 까는 구조를 그대로 따른다.
 * 토스의 코스피 자리에는 **GXI 지수**(12종목 상대가격의 기하평균 × 1000)가 들어간다 —
 * 게임이 이미 갖고 있던 값이고, 선물의 기초자산이라 화면과 거래가 같은 수를 본다.
 *
 * 토스에 있는 투자자별 매매동향·주요 일정은 게임에 대응 데이터가 없어 자리를 만들지 않았다
 * (빈 칸을 두면 고장으로 읽힌다).
 */
export default function GameMarketSummary({
  futures,
  symbols,
}: {
  futures: GameFuturesMarket | undefined;
  symbols: GameSymbolPrices[];
}) {
  // 지수 등락률 — 시계열 첫 값 대비. 게임 지수에는 "전일 종가" 개념이 없어 창 시작점을 기준으로 쓴다.
  const series = futures?.series ?? [];
  const indexChangePct =
    series.length >= 2 ? (series[series.length - 1].point / series[0].point - 1) * 100 : null;

  const sectors = groupBySector(symbols);

  return (
    <section className="rounded-2xl border border-border bg-surface p-4 grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      {/* 지수 — 이 화면에서 가장 큰 수 하나 */}
      <div className="lg:border-r lg:border-border lg:pr-4">
        {futures ? (
          <>
            <div className="flex items-baseline gap-2">
              <h2 className="text-sm font-bold">GXI 지수</h2>
              <span className="text-xs text-foreground-muted">{futures.contractCode}</span>
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-data-xl tabular-nums">
                {futures.indexPoint.toLocaleString()}
              </span>
              {indexChangePct !== null && (
                <span className={`text-sm font-semibold tabular-nums ${toneOf(indexChangePct)}`}>
                  {signed(indexChangePct)}
                </span>
              )}
            </div>

            <GamePriceLine
              points={series.map((p) => ({ tick: p.tick, priceKrw: p.point }))}
              className="mt-2 w-full h-16"
            />

            <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs">
              <div className="flex items-baseline gap-1">
                <dt className="text-foreground-muted">선물</dt>
                <dd className="font-semibold tabular-nums">
                  {futures.futuresPoint.toLocaleString()}
                </dd>
              </div>
              <div className="flex items-baseline gap-1">
                {/* 베이시스가 양수면 콘탱고 — 선물이 현물보다 비싸다 */}
                <dt className="text-foreground-muted">베이시스</dt>
                <dd className={`font-semibold tabular-nums ${toneOf(futures.basisPct)}`}>
                  {signed(futures.basisPct)}
                </dd>
              </div>
              <div className="flex items-baseline gap-1">
                <dt className="text-foreground-muted">만기</dt>
                <dd className="font-semibold tabular-nums">
                  {Math.max(0, Math.ceil(futures.ticksToExpiry / 60))}일
                </dd>
              </div>
            </dl>
          </>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="skeleton h-4 w-24 rounded-md" />
            <div className="skeleton h-8 w-32 rounded-md" />
            <div className="skeleton h-16 w-full rounded-lg" />
          </div>
        )}
      </div>

      {/* 섹터 격자 — 토스의 지수 8칸 자리. 게임에는 지수가 하나뿐이라 섹터가 그 역할을 한다. */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-x-4 gap-y-2.5 content-start">
        {sectors.map((s) => (
          <div key={s.group}>
            <p className="text-xs text-foreground-muted truncate">{s.group}</p>
            <p className={`text-sm font-semibold tabular-nums ${toneOf(s.changePct)}`}>
              {signed(s.changePct)}
              <span className="ml-1 text-xs font-normal text-foreground-muted">{s.count}</span>
            </p>
          </div>
        ))}
        {sectors.length === 0 &&
          Array.from({ length: 10 }, (_, i) => (
            <div key={i} className="skeleton h-9 rounded-md" />
          ))}
      </div>
    </section>
  );
}

/** 섹터 그룹별 평균 등락률 — 게임에 섹터 지수가 없어 종목 등락률의 산술평균으로 만든다.
 *  시가총액 가중이 아니므로 "큰 종목이 끌어올린 섹터"와 "고루 오른 섹터"를 구분하지 못한다. */
function groupBySector(symbols: GameSymbolPrices[]) {
  const buckets = new Map<string, number[]>();
  symbols.forEach((s) => {
    const list = buckets.get(s.sectorGroup) ?? [];
    list.push(s.changePct);
    buckets.set(s.sectorGroup, list);
  });
  return Array.from(buckets, ([group, values]) => ({
    group,
    count: values.length,
    changePct: values.reduce((a, b) => a + b, 0) / values.length,
  })).sort((a, b) => b.changePct - a.changePct);
}
