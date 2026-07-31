"use client";

import { useMemo } from "react";
import type { GamePricePoint } from "@/lib/types";

// 한국 관례: 상승 빨강 / 하락 파랑 (CandleChart와 동일)
const UP = "#DC2626";
const DOWN = "#2563EB";

// SVG 내부 좌표계 — 실제 크기는 CSS가 정한다(viewBox 스케일링).
const W = 600;
const H = 200;
const PAD_Y = 8;

type Props = {
  points: GamePricePoint[]; // tick 오름차순
  /** 리스트 안의 미니 차트 — 축·라벨 없이 선만 그린다 */
  compact?: boolean;
  className?: string;
};

/**
 * 게임 시세 라인 차트.
 *
 * lightweight-charts를 쓰지 않는 이유: 게임 시세는 틱 단위 종가 하나뿐이라 캔들·거래량·
 * 지표 축이 필요 없고, 종목 12개에 인스턴스를 12개 만들 이유는 더 없다. 폴리라인 하나면 된다.
 * 값은 전부 서버가 계산해 내려준 것이다 — 프론트는 가격을 만들지 않는다(game-harness §1-6).
 */
export default function GamePriceLine({ points, compact = false, className }: Props) {
  const shape = useMemo(() => {
    if (points.length < 2) return null;

    const prices = points.map((p) => p.priceKrw);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const span = max - min || 1; // 완전 평평한 구간에서 0으로 나누지 않는다
    const usable = H - PAD_Y * 2;

    const x = (i: number) => (i / (points.length - 1)) * W;
    const y = (price: number) => PAD_Y + (1 - (price - min) / span) * usable;

    const line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.priceKrw).toFixed(1)}`).join(" ");
    const rising = prices[prices.length - 1] >= prices[0];

    return {
      line,
      // 면적은 선 아래를 채워 방향을 읽기 쉽게 한다
      area: `${line} ${W},${H} 0,${H}`,
      color: rising ? UP : DOWN,
      min,
      max,
      last: prices[prices.length - 1],
      lastY: y(prices[prices.length - 1]),
    };
  }, [points]);

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
      aria-label={`가격 추이 ${shape.min.toLocaleString()}원 ~ ${shape.max.toLocaleString()}원`}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={shape.color} stopOpacity={compact ? 0.18 : 0.22} />
          <stop offset="100%" stopColor={shape.color} stopOpacity={0} />
        </linearGradient>
      </defs>

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

      {!compact && (
        <>
          {/* 현재가 지점 — preserveAspectRatio none이라 원은 찌그러진다. 짧은 선분을 쓴다 */}
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
          <line
            x1="0"
            y1={shape.lastY}
            x2={W}
            y2={shape.lastY}
            stroke={shape.color}
            strokeWidth={1}
            strokeDasharray="4 4"
            opacity={0.35}
            vectorEffect="non-scaling-stroke"
          />
        </>
      )}
    </svg>
  );
}
