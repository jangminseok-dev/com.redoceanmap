"use client";

import { useMemo } from "react";
import type { GameCandle, GameChartPattern, GamePricePoint } from "@/lib/types";

// 한국 관례: 상승 빨강 / 하락 파랑 (CandleChart와 동일)
const UP = "#DC2626";
const DOWN = "#2563EB";

// SVG 내부 좌표계 — 실제 크기는 CSS가 정한다(viewBox 스케일링).
const W = 600;
const H = 200;
const PAD_Y = 8;

// 세로 축이 담아야 할 최소 범위(중앙값 대비 %). 이게 없으면 0.3%짜리 변동도 화면을 꽉 채워
// 잔잔한 종목이 급등락처럼 보인다. 백엔드 게임 1일 변동성이 2~9%라 2%를 바닥으로 둔다.
const DEFAULT_MIN_RANGE_PCT = 2;

const TICKS_PER_GAME_DAY = 60; // 백엔드 game_epoch.TICKS_PER_GAME_DAY와 같은 값

/** 차트 위에 뉴스 발생 지점을 찍는다 — 어느 지점이 그 뉴스인지 눈으로 잇게 한다 */
export type GamePriceMarker = {
  tick: number;
  positive: boolean;
};

type Props = {
  points: GamePricePoint[]; // tick 오름차순
  /** 주어지면 라인 대신 일봉으로 그린다. 마지막 봉은 진행 중일 수 있다 */
  candles?: GameCandle[];
  /** 리스트 안의 미니 차트 — 축·라벨 없이 선만 그린다 */
  compact?: boolean;
  /** 뉴스 발생 틱. compact에서는 그리지 않는다 */
  markers?: GamePriceMarker[];
  /** 강조할 형태 하나. 여러 개를 겹쳐 그리면 곡선이 선에 덮인다 */
  pattern?: GameChartPattern;
  /** 세로 축 최소 범위(중앙값 대비 %) */
  minRangePct?: number;
  className?: string;
};

/**
 * 게임 시세 차트 — 라인과 일봉을 함께 그린다.
 *
 * lightweight-charts를 쓰지 않는 이유: 게임 시세는 거래량·지표 축이 없고, 종목 12개에
 * 인스턴스를 12개 만들 이유는 더 없다. 폴리라인과 사각형이면 된다(game-harness §10).
 * 값은 전부 서버가 계산해 내려준 것이다 — 프론트는 가격을 만들지 않는다(§1-6).
 */
export default function GamePriceLine({
  points,
  candles,
  compact = false,
  markers,
  pattern,
  minRangePct = DEFAULT_MIN_RANGE_PCT,
  className,
}: Props) {
  const shape = useMemo(() => {
    const candleMode = !!candles && candles.length > 0;
    if (!candleMode && points.length < 2) return null;

    // 값 범위 — 봉 모드는 심지(고저)까지 담아야 한다
    const values = candleMode
      ? candles!.flatMap((c) => [c.highKrw, c.lowKrw])
      : points.map((p) => p.priceKrw);
    let min = Math.min(...values);
    let max = Math.max(...values);

    // 최소 범위 확보 — 평평한 구간이 세로로 늘어나 보이지 않게 중앙값 기준으로 넓힌다
    const mid = (min + max) / 2;
    const minSpan = (mid * minRangePct) / 100;
    if (max - min < minSpan) {
      min = mid - minSpan / 2;
      max = mid + minSpan / 2;
    }
    const span = max - min || 1; // 0으로 나누지 않는다
    const usable = H - PAD_Y * 2;

    const count = candleMode ? candles!.length : points.length;
    const x = (i: number) => (count === 1 ? W / 2 : (i / (count - 1)) * W);
    const y = (price: number) => PAD_Y + (1 - (price - min) / span) * usable;

    // 뉴스 마커 — 창 밖 틱은 버린다(과거 뉴스가 왼쪽 끝에 뭉치지 않게)
    const firstTick = points[0]?.tick ?? 0;
    const toIndex = (tick: number) =>
      candleMode
        ? candles!.findIndex((c) => c.gameDay === Math.floor(tick / TICKS_PER_GAME_DAY))
        : tick - firstTick;
    const priceAt = (i: number) => (candleMode ? candles![i].closeKrw : points[i].priceKrw);

    // 형태 오버레이 — 좌표가 series 인덱스 기준이라 봉 모드에서는 축이 달라 그리지 않는다
    const shapePoints =
      compact || candleMode || !pattern
        ? null
        : pattern.points
            .filter(([i]) => i >= 0 && i < points.length)
            .map(([i, price]) => `${x(i).toFixed(1)},${y(price).toFixed(1)}`)
            .join(" ");

    const marks = (compact || !markers ? [] : markers)
      .map((m) => ({ ...m, index: toIndex(m.tick) }))
      .filter((m) => m.index >= 0 && m.index < count)
      .map((m) => ({
        key: `${m.tick}-${m.positive}`,
        x: x(m.index),
        y: y(priceAt(m.index)),
        color: m.positive ? UP : DOWN,
      }));

    if (candleMode) {
      // 봉 폭 — 봉 사이 간격의 60%. 봉이 1개면 화면의 8%.
      const gap = count > 1 ? W / (count - 1) : W * 0.14;
      const bodyW = Math.max(2, gap * 0.6);
      const bars = candles!.map((c, i) => {
        const rising = c.closeKrw >= c.openKrw;
        const top = y(Math.max(c.openKrw, c.closeKrw));
        const bottom = y(Math.min(c.openKrw, c.closeKrw));
        return {
          key: c.gameDay,
          cx: x(i),
          bodyW,
          bodyY: top,
          // 시가=종가인 날에도 몸통이 보이도록 최소 높이를 준다
          bodyH: Math.max(1.5, bottom - top),
          highY: y(c.highKrw),
          lowY: y(c.lowKrw),
          color: rising ? UP : DOWN,
        };
      });
      const first = candles![0];
      const last = candles![count - 1];
      return {
        mode: "candle" as const,
        bars,
        marks,
        shapePoints,
        min,
        max,
        color: last.closeKrw >= first.openKrw ? UP : DOWN,
        lastY: y(last.closeKrw),
        baseY: y(first.openKrw),
      };
    }

    const prices = points.map((p) => p.priceKrw);
    const line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.priceKrw).toFixed(1)}`).join(" ");
    return {
      mode: "line" as const,
      line,
      // 면적은 선 아래를 채워 방향을 읽기 쉽게 한다
      area: `${line} ${W},${H} 0,${H}`,
      marks,
      shapePoints,
      min,
      max,
      color: prices[prices.length - 1] >= prices[0] ? UP : DOWN,
      lastY: y(prices[prices.length - 1]),
      baseY: y(prices[0]),
    };
  }, [points, candles, compact, markers, pattern, minRangePct]);

  if (!shape) {
    return (
      <div className={`grid place-items-center text-xs text-foreground-muted ${className ?? ""}`}>
        데이터가 부족합니다
      </div>
    );
  }

  const gradientId = `game-line-${shape.color.slice(1)}`;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={className}
      role="img"
      aria-label={`가격 추이 ${Math.round(shape.min).toLocaleString()}원 ~ ${Math.round(
        shape.max,
      ).toLocaleString()}원`}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={shape.color} stopOpacity={compact ? 0.18 : 0.22} />
          <stop offset="100%" stopColor={shape.color} stopOpacity={0} />
        </linearGradient>
      </defs>

      {/* 기준선 — 구간 시작가. 지금이 그보다 위인지 아래인지가 한눈에 보인다 */}
      {!compact && (
        <line
          x1="0"
          y1={shape.baseY}
          x2={W}
          y2={shape.baseY}
          stroke="currentColor"
          strokeWidth={1}
          strokeDasharray="2 5"
          opacity={0.25}
          vectorEffect="non-scaling-stroke"
        />
      )}

      {shape.mode === "line" ? (
        <>
          <polygon points={shape.area} fill={`url(#${gradientId})`} />
          <polyline
            points={shape.line}
            fill="none"
            stroke={shape.color}
            strokeWidth={compact ? 3 : 2}
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        </>
      ) : (
        shape.bars.map((b) => (
          <g key={b.key}>
            {/* 심지 — preserveAspectRatio none이라 선 굵기는 vectorEffect로 고정한다 */}
            <line
              x1={b.cx}
              y1={b.highY}
              x2={b.cx}
              y2={b.lowY}
              stroke={b.color}
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            />
            <rect
              x={b.cx - b.bodyW / 2}
              y={b.bodyY}
              width={b.bodyW}
              height={b.bodyH}
              fill={b.color}
            />
          </g>
        ))
      )}

      {/* 형태 오버레이 — 어깨·넥라인을 잇는 보조선. 곡선을 가리지 않게 점선으로 얇게 */}
      {shape.shapePoints && (
        <polyline
          points={shape.shapePoints}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          strokeDasharray="5 3"
          opacity={0.55}
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      )}

      {/* 뉴스 발생 지점 — 가격에서 아래로 내린 짧은 눈금. 색이 호재·악재를 가른다 */}
      {shape.marks.map((m) => (
        <line
          key={m.key}
          x1={m.x}
          y1={m.y}
          x2={m.x}
          y2={Math.min(m.y + 14, H)}
          stroke={m.color}
          strokeWidth={2}
          opacity={0.7}
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      ))}

      {!compact && (
        /* 현재가 지점 — preserveAspectRatio none이라 원은 찌그러진다. 짧은 선분을 쓴다 */
        <line
          x1={W - 1}
          y1={shape.lastY}
          x2={W}
          y2={shape.lastY}
          stroke={shape.color}
          strokeWidth={7}
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      )}
    </svg>
  );
}
