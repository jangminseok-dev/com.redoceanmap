"use client";

import { useEffect, useRef, useState } from "react";
import type {
  GameCandle,
  GameChartPattern,
  GameMovingAverage,
  GamePricePoint,
} from "@/lib/types";
import { computeVolumeProfile } from "@/lib/volumeProfile";

// 한국 관례: 상승 빨강 / 하락 파랑
const UP = "#DC2626";
const DOWN = "#2563EB";

// 이동평균선 색 — 백엔드 indicators.MA_PERIODS와 같은 기간을 쓴다.
// 범례가 같은 값을 써야 하므로 내보낸다 — 두 곳에 적으면 색이 갈라진다.
export const MA_COLOR: Record<number, string> = {
  5: "#16A34A",
  20: "#DC2626",
  60: "#EA580C",
  120: "#7C3AED",
};

const RSI_OVERBOUGHT = 70;
const RSI_OVERSOLD = 30;

// 여백 — 오른쪽은 가격 축 라벨(현재가 배지 포함), 아래는 날짜 라벨 자리다
const PAD = { top: 10, right: 62, bottom: 18, left: 2 };
// 세로 분할 비율(가격 : 거래량 : RSI). 합이 1이다
const PANE = { price: 0.62, volume: 0.17, rsi: 0.21 };
const PANE_GAP = 10;

// 세로 축이 담아야 할 최소 범위(중앙값 대비 %). 없으면 0.3% 변동도 화면을 꽉 채워
// 잔잔한 종목이 급등락처럼 보인다.
const MIN_RANGE_PCT = 2;

const TICKS_PER_GAME_DAY = 60; // 백엔드 game_epoch.TICKS_PER_GAME_DAY와 같은 값

export type GameChartMarker = { tick: number; positive: boolean };

type Props = {
  /** 틱 곡선 — 라인 모드에서 그린다 */
  points: GamePricePoint[];
  /** 일봉 — 주어지면 봉 모드로 그린다 */
  candles?: GameCandle[];
  movingAverages?: GameMovingAverage[];
  rsi?: (number | null)[];
  /** 뉴스 발생 틱(라인 모드에서만 눈금으로 찍는다) */
  markers?: GameChartMarker[];
  /** 강조할 형태 하나(라인 모드 전용) */
  pattern?: GameChartPattern;
  className?: string;
};

const won = (v: number) => v.toLocaleString();

/** 축 라벨용 — 자리수에 따라 눈금 간격을 사람이 읽는 단위로 맞춘다 */
function niceTicks(min: number, max: number, count = 4): number[] {
  const span = max - min;
  if (span <= 0) return [min];
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10;
  const first = Math.ceil(min / step) * step;
  const out: number[] = [];
  for (let v = first; v <= max; v += step) out.push(v);
  return out;
}

/**
 * 게임 시세 차트 — 가격 축·현재가·이동평균·거래량·RSI를 한 화면에.
 *
 * lightweight-charts를 쓰지 않는 이유는 그대로다(game-harness §10) — 값은 전부 서버가
 * 계산해 내려준 것이고 프론트는 가격도 지표도 만들지 않는다(§1-6). 여기서 하는 일은
 * 좌표 변환과 그리기뿐이다.
 *
 * SVG를 `preserveAspectRatio="none"`으로 늘이지 않고 **실제 픽셀 좌표**로 그린다 —
 * 축 라벨·현재가 배지처럼 글자가 들어가면 늘어난 좌표계에서 글꼴이 찌그러진다.
 * 그래서 컨테이너 너비를 재서 쓴다.
 */
export default function GameChart({
  points,
  candles,
  movingAverages = [],
  rsi = [],
  markers,
  pattern,
  className,
}: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  // 너비 측정 + 크로스헤어 위치를 한 객체로 든다(REACT_RULES 패턴 B)
  const [ui, setUi] = useState<{ width: number; height: number; hover: number | null }>({
    width: 0,
    height: 0,
    hover: null,
  });

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setUi((prev) =>
        prev.width === width && prev.height === height ? prev : { ...prev, width, height },
      );
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const candleMode = !!candles && candles.length > 0;
  const count = candleMode ? candles!.length : points.length;
  const ready = ui.width > 0 && ui.height > 0 && count >= (candleMode ? 1 : 2);

  return (
    <div ref={boxRef} className={className}>
      {!ready ? (
        <div className="grid h-full place-items-center text-xs text-foreground-muted">
          아직 시세 기록이 없습니다 — 1분마다 게임 1일이 흐릅니다
        </div>
      ) : (
        <Plot
          width={ui.width}
          height={ui.height}
          hover={ui.hover}
          onHover={(index) => setUi((prev) => ({ ...prev, hover: index }))}
          points={points}
          candles={candles}
          movingAverages={movingAverages}
          rsi={rsi}
          markers={markers}
          pattern={pattern}
        />
      )}
    </div>
  );
}

type PlotProps = Props & {
  width: number;
  height: number;
  hover: number | null;
  onHover: (index: number | null) => void;
};

function Plot({
  width,
  height,
  hover,
  onHover,
  points,
  candles,
  movingAverages = [],
  rsi = [],
  markers,
  pattern,
}: PlotProps) {
  const candleMode = !!candles && candles.length > 0;
  const count = candleMode ? candles!.length : points.length;

  const plotW = Math.max(1, width - PAD.left - PAD.right);
  const plotH = Math.max(1, height - PAD.top - PAD.bottom);
  const hasVolume = candleMode;
  const hasRsi = candleMode && rsi.some((v) => v !== null);
  // 보조 지표가 없으면 가격이 세로를 다 쓴다 — 빈 칸을 남겨두면 차트만 납작해진다
  const priceRatio = hasVolume || hasRsi ? PANE.price : 1;
  const priceH = plotH * priceRatio - (hasVolume || hasRsi ? PANE_GAP : 0);
  const volumeH = hasVolume ? plotH * PANE.volume - PANE_GAP : 0;
  const rsiH = hasRsi ? plotH * PANE.rsi : 0;
  const priceTop = PAD.top;
  const volumeTop = priceTop + priceH + PANE_GAP;
  const rsiTop = volumeTop + volumeH + (hasVolume ? PANE_GAP : 0);

  // --- 가격 축 ---
  const closes = candleMode ? candles!.map((c) => c.closeKrw) : points.map((p) => p.priceKrw);
  const maValues = movingAverages
    .flatMap((m) => m.points)
    .filter((v): v is number => v !== null);
  const rawValues = candleMode
    ? [...candles!.flatMap((c) => [c.highKrw, c.lowKrw]), ...maValues]
    : closes;
  let min = Math.min(...rawValues);
  let max = Math.max(...rawValues);
  const mid = (min + max) / 2;
  const minSpan = (mid * MIN_RANGE_PCT) / 100;
  if (max - min < minSpan) {
    min = mid - minSpan / 2;
    max = mid + minSpan / 2;
  }
  const span = max - min || 1;

  const x = (i: number) => PAD.left + (count === 1 ? plotW / 2 : (i / (count - 1)) * plotW);
  const yPrice = (v: number) => priceTop + (1 - (v - min) / span) * priceH;

  const current = closes[closes.length - 1];
  const first = candleMode ? candles![0].openKrw : closes[0];
  const tone = current >= first ? UP : DOWN;

  // --- 거래량 축 ---
  const volumes = candleMode ? candles!.map((c) => c.simulatedVolume) : [];
  const volumeMax = volumes.length ? Math.max(...volumes) : 1;
  const yVolume = (v: number) => volumeTop + volumeH * (1 - v / volumeMax);

  // --- RSI 축 (0~100 고정) ---
  const yRsi = (v: number) => rsiTop + rsiH * (1 - v / 100);

  // --- 매물대 — 표시된 봉 전체의 가격대별 거래량 분포 (stock CandleChart와 공용 계산) ---
  const profile = candleMode
    ? computeVolumeProfile(
        candles!.map((c) => ({
          high: c.highKrw,
          low: c.lowKrw,
          close: c.closeKrw,
          volume: c.simulatedVolume,
        })),
      )
    : null;

  // 봉 폭 — 봉 사이 간격의 62%
  const gap = count > 1 ? plotW / (count - 1) : plotW * 0.5;
  const bodyW = Math.max(1, Math.min(gap * 0.62, 14));

  const line = closes.map((v, i) => `${x(i).toFixed(1)},${yPrice(v).toFixed(1)}`).join(" ");
  const priceTicks = niceTicks(min, max);

  // 뉴스 눈금 — 라인 모드에서만. 창 밖 틱은 버린다
  const firstTick = points[0]?.tick ?? 0;
  const marks = (candleMode || !markers ? [] : markers)
    .map((m) => ({ ...m, index: m.tick - firstTick }))
    .filter((m) => m.index >= 0 && m.index < count);

  const shapePoints =
    candleMode || !pattern
      ? null
      : pattern.points
          .filter(([i]) => i >= 0 && i < count)
          .map(([i, price]) => `${x(i).toFixed(1)},${yPrice(price).toFixed(1)}`)
          .join(" ");

  const hoverIndex = hover !== null && hover >= 0 && hover < count ? hover : null;

  const handleMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = e.clientX - rect.left - PAD.left;
    const index = count === 1 ? 0 : Math.round((rel / plotW) * (count - 1));
    onHover(Math.max(0, Math.min(count - 1, index)));
  };

  return (
    <svg
      width={width}
      height={height}
      className="select-none"
      role="img"
      aria-label={`가격 추이 ${won(Math.round(min))}원 ~ ${won(Math.round(max))}원, 현재 ${won(current)}원`}
      onMouseMove={handleMove}
      onMouseLeave={() => onHover(null)}
    >
      <defs>
        <linearGradient id="game-chart-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={tone} stopOpacity={0.18} />
          <stop offset="100%" stopColor={tone} stopOpacity={0} />
        </linearGradient>
      </defs>

      {/* 가격 눈금 — 가로 격자 + 오른쪽 라벨. 이게 없으면 "지금 얼마인지"를 못 읽는다 */}
      {priceTicks.map((v) => (
        <g key={v}>
          <line
            x1={PAD.left}
            y1={yPrice(v)}
            x2={PAD.left + plotW}
            y2={yPrice(v)}
            stroke="currentColor"
            strokeWidth={1}
            opacity={0.08}
          />
          <text
            x={width - PAD.right + 6}
            y={yPrice(v) + 3.5}
            fontSize={10}
            fill="currentColor"
            opacity={0.55}
            className="tabular-nums"
          >
            {won(Math.round(v))}
          </text>
        </g>
      ))}

      {/* 기준선 — 구간 시작가. 지금이 그보다 위인지 아래인지가 한눈에 보인다 */}
      <line
        x1={PAD.left}
        y1={yPrice(first)}
        x2={PAD.left + plotW}
        y2={yPrice(first)}
        stroke="currentColor"
        strokeWidth={1}
        strokeDasharray="2 5"
        opacity={0.3}
      />

      {/* 매물대 — 어느 가격대에서 거래가 밀집했나(팩트 표시). 캔들 뒤에 깔린다 */}
      {profile &&
        profile.bins.map((bin, i) => {
          if (bin.volume <= 0) return null;
          const top = Math.max(priceTop, yPrice(bin.high));
          const bottom = Math.min(priceTop + priceH, yPrice(bin.low));
          if (bottom - top < 1) return null; // 축 최소 범위 보정으로 밀려난 구간
          const barW = (bin.volume / profile.maxVolume) * plotW * 0.16;
          return (
            <rect
              key={`vp-${i}`}
              x={PAD.left + plotW - barW}
              y={top + 0.5}
              width={barW}
              height={Math.max(1, bottom - top - 1)}
              fill={
                i === profile.pocIndex
                  ? "rgba(153, 27, 27, 0.30)" // 최다 거래 구간만 강조
                  : "rgba(107, 114, 128, 0.16)"
              }
            />
          );
        })}

      {/* 가격 — 봉 또는 라인 */}
      {candleMode ? (
        candles!.map((c, i) => {
          const rising = c.closeKrw >= c.openKrw;
          const top = yPrice(Math.max(c.openKrw, c.closeKrw));
          const bottom = yPrice(Math.min(c.openKrw, c.closeKrw));
          const color = rising ? UP : DOWN;
          return (
            <g key={c.gameDay}>
              <line
                x1={x(i)}
                y1={yPrice(c.highKrw)}
                x2={x(i)}
                y2={yPrice(c.lowKrw)}
                stroke={color}
                strokeWidth={1}
              />
              <rect
                x={x(i) - bodyW / 2}
                y={top}
                width={bodyW}
                /* 시가=종가인 날에도 몸통이 보이도록 최소 높이를 준다 */
                height={Math.max(1.5, bottom - top)}
                fill={color}
              />
            </g>
          );
        })
      ) : (
        <>
          <polygon
            points={`${line} ${PAD.left + plotW},${priceTop + priceH} ${PAD.left},${priceTop + priceH}`}
            fill="url(#game-chart-fill)"
          />
          <polyline
            points={line}
            fill="none"
            stroke={tone}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </>
      )}

      {/* 이동평균선 — null 구간은 선을 끊는다(0으로 잇지 않는다) */}
      {candleMode &&
        movingAverages.map((ma) => {
          const segments: string[] = [];
          let run: string[] = [];
          ma.points.forEach((v, i) => {
            if (v === null) {
              if (run.length > 1) segments.push(run.join(" "));
              run = [];
            } else {
              run.push(`${x(i).toFixed(1)},${yPrice(v).toFixed(1)}`);
            }
          });
          if (run.length > 1) segments.push(run.join(" "));
          return segments.map((seg, k) => (
            <polyline
              key={`${ma.period}-${k}`}
              points={seg}
              fill="none"
              stroke={MA_COLOR[ma.period] ?? "#94A3B8"}
              strokeWidth={1.2}
              opacity={0.9}
            />
          ));
        })}

      {/* 형태 오버레이 — 어깨·넥라인을 잇는 보조선 */}
      {shapePoints && (
        <polyline
          points={shapePoints}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          strokeDasharray="5 3"
          opacity={0.55}
          strokeLinejoin="round"
        />
      )}

      {/* 뉴스 발생 지점 */}
      {marks.map((m) => (
        <line
          key={`${m.tick}-${m.positive}`}
          x1={x(m.index)}
          y1={yPrice(closes[m.index])}
          x2={x(m.index)}
          y2={Math.min(yPrice(closes[m.index]) + 14, priceTop + priceH)}
          stroke={m.positive ? UP : DOWN}
          strokeWidth={2}
          opacity={0.7}
          strokeLinecap="round"
        />
      ))}

      {/* ── 현재가 ── 사용자가 차트에서 가장 먼저 찾는 값이다.
          수평 점선 + 오른쪽 축 배지로 못 놓치게 한다 */}
      <line
        x1={PAD.left}
        y1={yPrice(current)}
        x2={width - PAD.right}
        y2={yPrice(current)}
        stroke={tone}
        strokeWidth={1}
        strokeDasharray="3 3"
        opacity={0.85}
      />
      <rect
        x={width - PAD.right + 1}
        y={yPrice(current) - 8}
        width={PAD.right - 3}
        height={16}
        rx={3}
        fill={tone}
      />
      <text
        x={width - PAD.right + 5}
        y={yPrice(current) + 3.5}
        fontSize={10}
        fontWeight={600}
        fill="#fff"
        className="tabular-nums"
      >
        {won(current)}
      </text>
      <circle cx={x(count - 1)} cy={yPrice(current)} r={3} fill={tone} />

      {/* ── 거래량 ── */}
      {hasVolume &&
        candles!.map((c, i) => (
          <rect
            key={`v-${c.gameDay}`}
            x={x(i) - bodyW / 2}
            y={yVolume(c.simulatedVolume)}
            width={bodyW}
            height={Math.max(1, volumeTop + volumeH - yVolume(c.simulatedVolume))}
            fill={c.closeKrw >= c.openKrw ? UP : DOWN}
            opacity={0.45}
          />
        ))}
      {hasVolume && (
        <text x={PAD.left + 2} y={volumeTop + 9} fontSize={9} fill="currentColor" opacity={0.5}>
          거래량 (게임 규칙)
        </text>
      )}

      {/* ── RSI ── 30/70 기준선과 함께 그린다 */}
      {hasRsi && (
        <>
          {[RSI_OVERSOLD, RSI_OVERBOUGHT].map((level) => (
            <line
              key={level}
              x1={PAD.left}
              y1={yRsi(level)}
              x2={PAD.left + plotW}
              y2={yRsi(level)}
              stroke="currentColor"
              strokeWidth={1}
              strokeDasharray="3 4"
              opacity={0.2}
            />
          ))}
          {(() => {
            const segments: string[] = [];
            let run: string[] = [];
            rsi.forEach((v, i) => {
              if (v === null) {
                if (run.length > 1) segments.push(run.join(" "));
                run = [];
              } else {
                run.push(`${x(i).toFixed(1)},${yRsi(v).toFixed(1)}`);
              }
            });
            if (run.length > 1) segments.push(run.join(" "));
            return segments.map((seg, k) => (
              <polyline
                key={`rsi-${k}`}
                points={seg}
                fill="none"
                stroke="#7C3AED"
                strokeWidth={1.2}
              />
            ));
          })()}
          <text x={PAD.left + 2} y={rsiTop + 9} fontSize={9} fill="currentColor" opacity={0.5}>
            RSI (14)
          </text>
        </>
      )}

      {/* ── 크로스헤어 ── 짚은 지점의 값을 읽게 한다 */}
      {hoverIndex !== null && (
        <>
          <line
            x1={x(hoverIndex)}
            y1={PAD.top}
            x2={x(hoverIndex)}
            y2={height - PAD.bottom}
            stroke="currentColor"
            strokeWidth={1}
            opacity={0.35}
          />
          <circle cx={x(hoverIndex)} cy={yPrice(closes[hoverIndex])} r={3.5} fill={tone} />
          <rect
            x={width - PAD.right + 1}
            y={yPrice(closes[hoverIndex]) - 8}
            width={PAD.right - 3}
            height={16}
            rx={3}
            fill="currentColor"
            opacity={0.85}
          />
          <text
            x={width - PAD.right + 5}
            y={yPrice(closes[hoverIndex]) + 3.5}
            fontSize={10}
            fontWeight={600}
            fill="#fff"
            className="tabular-nums"
          >
            {won(closes[hoverIndex])}
          </text>
        </>
      )}

      {/* 가로축 라벨 — 봉 모드는 게임일, 라인 모드는 틱 */}
      {[0, Math.floor((count - 1) / 2), count - 1]
        .filter((i, k, arr) => arr.indexOf(i) === k && i >= 0)
        .map((i) => (
          <text
            key={`x-${i}`}
            x={Math.min(Math.max(x(i), 14), PAD.left + plotW - 14)}
            y={height - 5}
            fontSize={9}
            fill="currentColor"
            opacity={0.5}
            textAnchor="middle"
            className="tabular-nums"
          >
            {candleMode
              ? `${candles![i].gameDay}일차`
              : `${Math.floor(points[i].tick / TICKS_PER_GAME_DAY)}일차`}
          </text>
        ))}
    </svg>
  );
}
