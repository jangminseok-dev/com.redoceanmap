"use client";

import { ChevronDown } from "lucide-react";
import type { SignalContribution, StockAnalyzeResult } from "@/lib/types";
import { formatPrice } from "@/lib/currency";
import InsightList from "@/components/common/InsightList";
import SignalBreakdown from "./SignalBreakdown";

const fmt = (v: number, digits = 2) =>
  v.toLocaleString("ko-KR", { maximumFractionDigits: digits });

// 백엔드 stock_narrator.py와 같은 임계값 — 화면 라벨과 해설 문장이 어긋나지 않게 맞춘다
const RSI_OVERSOLD = 30;
const RSI_OVERBOUGHT = 70;
const BB_LOW = 0.2;
const BB_HIGH = 0.8;
const VOLUME_SURGE = 1.5;
const VOLUME_QUIET = 0.7;
// 추세 × 거래량 교차 검증 임계값 — 게임 signal.py의 같은 판정과 맞춘 값
const VOLUME_CONFIRM = 1.1;
const VOLUME_DOUBT = 0.8;
const MOMENTUM_MIN = 0.15;
const ATR_HIGH = 4.0;
// 이 이상은 "추세"가 아니라 상장 초기 구간이 기준에 잡힌 것 — 숫자를 그대로 믿게 두지 않는다
const MOMENTUM_ABSURD = 5.0;

type Tone = "up" | "down" | "flat";

type Stat = {
  label: string;
  value: string;
  hint: string;
  tone: Tone;
  // 0~1 상대 위치 — 상·하한이 정해진 지표에만 게이지를 그린다
  gauge?: { position: number; marks: number[] };
  // 이 타일이 대응하는 신호 키. 가중치 0이면 판정에 안 쓰인 참고 지표라 기본은 접는다.
  signal?: SignalContribution["key"];
};

const TONE_TEXT: Record<Tone, string> = {
  up: "text-up",
  down: "text-down",
  flat: "text-foreground-muted",
};
const TONE_BG: Record<Tone, string> = {
  up: "bg-up",
  down: "bg-down",
  flat: "bg-foreground-muted",
};

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

function buildStats(a: StockAnalyzeResult, symbol: string): Stat[] {
  const trendGap = a.ma50 > 0 ? (a.ma20 - a.ma50) / a.ma50 : 0;
  const price = (v: number) => formatPrice(v, symbol);

  return [
    {
      label: "RSI(14)",
      signal: "rsi",
      value: fmt(a.rsi, 1),
      hint: a.rsi <= RSI_OVERSOLD ? "과매도 — 반등 여지" : a.rsi >= RSI_OVERBOUGHT ? "과열 — 조정 주의" : "중립 구간",
      tone: a.rsi <= RSI_OVERSOLD ? "down" : a.rsi >= RSI_OVERBOUGHT ? "up" : "flat",
      gauge: { position: clamp01(a.rsi / 100), marks: [0.3, 0.7] },
    },
    {
      label: "밴드 위치 (볼린저)",
      signal: "bollinger",
      value: fmt(a.bb_percent_b),
      hint:
        a.bb_percent_b <= BB_LOW
          ? "밴드 하단 — 단기 과매도권"
          : a.bb_percent_b >= BB_HIGH
            ? "밴드 상단 — 단기 과열권"
            : "밴드 중앙",
      tone: a.bb_percent_b <= BB_LOW ? "down" : a.bb_percent_b >= BB_HIGH ? "up" : "flat",
      gauge: { position: clamp01(a.bb_percent_b), marks: [BB_LOW, BB_HIGH] },
    },
    {
      label: "거래량비 (5/20일)",
      value: `${fmt(a.volume_ratio)}x`,
      // 가격 방향 + 거래량 증가 = 신뢰, 방향은 있는데 거래량 감소 = 의심.
      // 방향(정/역배열)이 없으면 판정하지 않는다 — 방향 없는 신뢰도는 무의미하다.
      hint:
        (a.volume_ratio >= VOLUME_SURGE
          ? "평소보다 급증"
          : a.volume_ratio <= VOLUME_QUIET
            ? "평소보다 한산"
            : "평소 수준") +
        (() => {
          const trending =
            (a.price > a.ma20 && a.ma20 > a.ma50) || (a.price < a.ma20 && a.ma20 < a.ma50);
          if (!trending) return "";
          if (a.volume_ratio >= VOLUME_CONFIRM) return " · 추세 방향에 거래량 동반(신뢰)";
          if (a.volume_ratio <= VOLUME_DOUBT) return " · 추세 대비 거래량 감소(의심)";
          return "";
        })(),
      tone: a.volume_ratio >= VOLUME_SURGE ? "up" : a.volume_ratio <= VOLUME_QUIET ? "down" : "flat",
      // 1.0(평소)이 한가운데 오도록 0~2배 구간에 놓는다
      gauge: { position: clamp01(a.volume_ratio / 2), marks: [VOLUME_QUIET / 2, VOLUME_SURGE / 2] },
    },
    {
      label: "자금 흐름 (OBV)",
      signal: "obv",
      value: fmt(a.obv_slope, 3),
      hint: a.obv_slope > 0 ? "자금 유입 우위" : a.obv_slope < 0 ? "자금 유출 우위" : "수급 중립",
      tone: a.obv_slope > 0 ? "up" : a.obv_slope < 0 ? "down" : "flat",
    },
    {
      label: "1년 추세 (모멘텀)",
      signal: "momentum",
      // 상장·분할 1년 이내 종목은 기준 시점이 상장 초기라 수백~수천 %가 찍힌다(SNDK +5,364%).
      // 계산은 맞지만 "중장기 추세"로 읽을 수 없는 값이라 그대로 두지 않는다.
      value: Math.abs(a.momentum_12_1) >= MOMENTUM_ABSURD
        ? `${a.momentum_12_1 > 0 ? ">+" : "<-"}${MOMENTUM_ABSURD * 100}%`
        : `${fmt(a.momentum_12_1 * 100, 1)}%`,
      hint:
        Math.abs(a.momentum_12_1) >= MOMENTUM_ABSURD
          ? "상장 1년 내 종목일 수 있어 해석 불가"
          : a.momentum_12_1 >= MOMENTUM_MIN
            ? "중장기 상승 추세"
            : a.momentum_12_1 <= -MOMENTUM_MIN
              ? "중장기 하락 추세"
              : "중장기 방향성 약함",
      tone:
        Math.abs(a.momentum_12_1) >= MOMENTUM_ABSURD
          ? "flat"
          : a.momentum_12_1 >= MOMENTUM_MIN
            ? "up"
            : a.momentum_12_1 <= -MOMENTUM_MIN
              ? "down"
              : "flat",
    },
    {
      label: "ATR (변동성)",
      value: `${fmt(a.atr_pct * 100, 1)}%`,
      hint: a.atr_pct * 100 >= ATR_HIGH ? "급등락 주의" : "변동성 보통",
      tone: a.atr_pct * 100 >= ATR_HIGH ? "up" : "flat",
    },
    {
      label: "20일 평균가",
      signal: "trend",
      value: price(a.ma20),
      hint:
        trendGap >= 0.02
          ? `50일선 위 +${fmt(trendGap * 100, 1)}% (상승 배열)`
          : trendGap <= -0.02
            ? `50일선 아래 ${fmt(trendGap * 100, 1)}% (하락 배열)`
            : "50일선과 근접",
      tone: trendGap >= 0.02 ? "up" : trendGap <= -0.02 ? "down" : "flat",
    },
    {
      label: "50일 평균가",
      value: price(a.ma50),
      hint: "중기 추세 기준선",
      tone: "flat",
    },
    {
      label: "60일 최저",
      value: price(a.support),
      hint: `현재가 대비 ${fmt((a.support / a.price - 1) * 100, 1)}% · 최저 봉이 창을 벗어나면 점프`,
      tone: "down",
    },
    {
      label: "60일 최고",
      value: price(a.resistance),
      hint: `현재가 대비 +${fmt((a.resistance / a.price - 1) * 100, 1)}% · 최고 봉이 창을 벗어나면 점프`,
      tone: "up",
    },
  ];
}

function StatTile({ stat }: { stat: Stat }) {
  return (
    <div className="bg-surface border border-border rounded-lg px-3 py-2.5">
      <div className="text-xs text-foreground-muted">{stat.label}</div>
      <div className="text-sm font-semibold mt-0.5 tabular-nums">{stat.value}</div>
      {stat.gauge && (
        <div className="relative mt-1.5 h-1 rounded-full bg-border/70">
          {stat.gauge.marks.map((mark) => (
            <div
              key={mark}
              className="absolute inset-y-0 w-px bg-foreground-muted/50"
              style={{ left: `${mark * 100}%` }}
            />
          ))}
          <div
            className={`absolute top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full ${TONE_BG[stat.tone]}`}
            style={{ left: `calc(${stat.gauge.position * 100}% - 3px)` }}
          />
        </div>
      )}
      <div className={`mt-1 text-xs leading-tight ${TONE_TEXT[stat.tone]}`}>{stat.hint}</div>
    </div>
  );
}

export default function IndicatorPanel({
  analyze,
  symbol,
  expert,
}: {
  analyze?: StockAnalyzeResult;
  symbol: string;
  expert: boolean;
}) {
  if (!analyze) {
    return (
      <div className="p-4 grid grid-cols-2 gap-2">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="skeleton h-14 rounded-lg" />
        ))}
      </div>
    );
  }

  const stats = buildStats(analyze, symbol);
  // 판정에 실제로 들어간 지표(가중치 ≠ 0)와 참고용을 가른다 — 열 개를 같은 크기로 늘어놓으면
  // 어느 것이 결론을 만들었는지 알 수 없다. 전문가 모드에서는 구분 없이 전부 편다.
  const weighted = new Set(
    (analyze.signals ?? []).filter((s) => s.weight !== 0).map((s) => s.key),
  );
  const used = expert ? stats : stats.filter((s) => s.signal && weighted.has(s.signal));
  const reference = expert ? [] : stats.filter((s) => !used.includes(s));

  return (
    <div className="p-4 flex flex-col gap-3">
      <SignalBreakdown analyze={analyze} />

      {analyze.insights && analyze.insights.length > 0 && (
        <div className="bg-surface border border-border rounded-lg px-3 py-2.5">
          <InsightList insights={analyze.insights} />
        </div>
      )}

      {used.length > 0 && (
        <div>
          {!expert && (
            <p className="mb-1.5 text-xs text-foreground-muted">이번 판정에 쓰인 지표</p>
          )}
          <div className="grid grid-cols-2 gap-2">
            {used.map((stat) => (
              <StatTile key={stat.label} stat={stat} />
            ))}
          </div>
        </div>
      )}

      {reference.length > 0 && (
        <details className="group">
          <summary className="flex items-center gap-1 text-xs text-foreground-muted cursor-pointer list-none select-none">
            <ChevronDown size={12} className="transition-transform group-open:rotate-180" />
            판정에 반영되지 않은 참고 지표 {reference.length}개
          </summary>
          <div className="mt-1.5 grid grid-cols-2 gap-2">
            {reference.map((stat) => (
              <StatTile key={stat.label} stat={stat} />
            ))}
          </div>
        </details>
      )}

      <div className="bg-surface border border-border rounded-lg px-3 py-2.5">
        <div className="text-xs text-foreground-muted">뉴스 감성</div>
        <div className="text-sm font-semibold mt-0.5">
          {analyze.sentiment_label}{" "}
          <span className="text-xs font-normal text-foreground-muted">
            ({analyze.sentiment > 0 ? "+" : ""}{fmt(analyze.sentiment)})
          </span>
        </div>
        {/* 기준선(최근 30일 라벨 평균)이 없으면 절대값이 그대로 신호에 들어간다 —
            상시 낙관 편향을 걸러내는 장치가 꺼진 상태라 이를 숨기지 않는다. */}
        <div className="mt-1 text-xs leading-tight text-amber-700">
          {analyze.sentiment_baseline == null
            ? "30일 기준선 없음 — 편향 보정 없이 반영됨(수집 대상 종목이 아닙니다)"
            : `30일 평균 ${analyze.sentiment_baseline > 0 ? "+" : ""}${fmt(analyze.sentiment_baseline)} 대비 편차로 반영됨`}
        </div>
      </div>
    </div>
  );
}
