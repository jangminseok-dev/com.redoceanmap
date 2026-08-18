"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import type { ChartPattern, PriceBar, StockForecast, StockNewsItem } from "@/lib/types";
import { useThemeStore } from "@/lib/uiStore";
import { computeVolumeProfile } from "@/lib/volumeProfile";

// lightweight-charts는 CSS 변수를 받지 못한다 — 테마별 색을 JS 옵션으로 직접 준다.
// 값은 globals.css의 라이트/다크 토큰과 짝이다(핸드오프 §차트·지도 대응표).
// 한국 관례: 상승 빨강 / 하락 파랑 (StockCard·방향 배지와 동일).
function chartColors(dark: boolean) {
  return dark
    ? {
        up: "#F87171",
        down: "#60A5FA",
        ma20: "#E8B45A",
        ma50: "#B69CF4",
        rsi: "#2DD4BF",
        rsiGuide: "#4A463C",
        pattern: "#A39B8B",
        text: "#A39B8B",
        border: "#322E26",
        grid: "rgba(242, 237, 227, 0.06)",
        brand: "#E5484D",
        volUp: "rgba(248, 113, 113, 0.28)",
        volDown: "rgba(96, 165, 250, 0.28)",
        median: "#A39B8B",
        profilePoc: "rgba(229, 72, 77, 0.30)",
        profileBin: "rgba(163, 155, 139, 0.14)",
        fcZone: "rgba(229, 72, 77, 0.06)",
        fcCone: "rgba(248, 113, 113, 0.13)",
      }
    : {
        up: "#DC2626",
        down: "#2563EB",
        ma20: "#D97706",
        ma50: "#7C3AED",
        rsi: "#0D9488",
        rsiGuide: "#D1D5DB",
        pattern: "#6B7280",
        text: "#6B7280",
        border: "#EBE8DF",
        grid: "rgba(235, 232, 223, 0.6)",
        brand: "#991B1B",
        volUp: "rgba(220, 38, 38, 0.28)",
        volDown: "rgba(37, 99, 235, 0.28)",
        median: "#6B7280",
        profilePoc: "rgba(153, 27, 27, 0.30)",
        profileBin: "rgba(107, 114, 128, 0.16)",
        fcZone: "rgba(153, 27, 27, 0.045)",
        fcCone: "rgba(220, 38, 38, 0.13)",
      };
}
type ChartColors = ReturnType<typeof chartColors>;

type CandleChartProps = {
  bars: PriceBar[]; // ts 오름차순
  support?: number | null;
  resistance?: number | null;
  forecast?: StockForecast | null; // 예측 밴드 — 1d 타임프레임에서만 전달된다
  quotePrice?: number | null; // 준실시간(지연) 현재가 — 마지막 봉 갱신용
  sessionTz?: string; // 거래소 타임존 — 세션 날짜 판정용 (한국 "Asia/Seoul" · 미국 "America/New_York")
  rangeDays?: number | null; // 초기 표시 구간(달력일). null = 전체
  news?: StockNewsItem[]; // 감성 마커용 — 강한 기사만 캔들 위에 찍는다
  intraday?: boolean; // 5분봉 등 분 단위 — 시간축에 시각을 표시할지
  pattern?: ChartPattern | null; // 강조할 형태 하나 — 여러 개를 겹치면 캔들이 보조선에 덮인다
};

// 감성 마커로 찍을 최소 강도·최대 개수 — 약한 기사까지 찍으면 캔들이 가려진다
const MARKER_MIN_ABS_SENTIMENT = 0.3;
const MARKER_LIMIT = 20;

const pct = (v: number) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;

function sma(bars: PriceBar[], period: number) {
  const out: { time: UTCTimestamp; value: number }[] = [];
  let sum = 0;
  for (let i = 0; i < bars.length; i++) {
    sum += bars[i].close;
    if (i >= period) sum -= bars[i - period].close;
    if (i >= period - 1) {
      out.push({ time: toTime(bars[i].ts), value: sum / period });
    }
  }
  return out;
}

// RSI(14, Wilder 평활) — 백엔드 IndicatorCalculator와 같은 방식
function rsiSeries(bars: PriceBar[], period = 14) {
  const out: { time: UTCTimestamp; value: number }[] = [];
  if (bars.length < period + 1) return out;
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const diff = bars[i].close - bars[i - 1].close;
    if (diff > 0) avgGain += diff;
    else avgLoss -= diff;
  }
  avgGain /= period;
  avgLoss /= period;
  const toRsi = () => (avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
  out.push({ time: toTime(bars[period].ts), value: toRsi() });
  for (let i = period + 1; i < bars.length; i++) {
    const diff = bars[i].close - bars[i - 1].close;
    avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
    out.push({ time: toTime(bars[i].ts), value: toRsi() });
  }
  return out;
}

// 마지막 봉 이후 horizon 거래일(주말 제외)의 미래 타임스탬프 — 매 거래일을 다 돌려준다.
// 시작·끝 2점만 주면 안 된다: lightweight-charts의 시간축은 실제 시간이 아니라 데이터
// 포인트 인덱스 간격이라, 중간 점이 없으면 5거래일 예측이 봉 하나 폭으로 찌그러진다.
function futureTimes(lastTs: string, tradingDays: number): UTCTimestamp[] {
  const d = new Date(lastTs);
  const out: UTCTimestamp[] = [];
  while (out.length < tradingDays) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() !== 0 && d.getDay() !== 6) out.push((d.getTime() / 1000) as UTCTimestamp);
  }
  return out;
}

const toTime = (ts: string) => (new Date(ts).getTime() / 1000) as UTCTimestamp;

// 거래소 세션 날짜 키(YYYY-MM-DD) — UTC 날짜로 비교하면 한국 종목(KST 세션)이
// 최대 하루 어긋나, 어제 자리에 오늘 현재가로 만든 임시 봉이 생긴다.
const sessionDayKey = (d: Date, tz: string) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: tz }).format(d);

// 기사 발행 시각을 같거나 그 다음 봉에 붙여 마커로 만든다 — 장외·주말 발행분도
// "다음 개장 첫 봉"으로 밀어 붙인다(뉴스 라벨링과 같은 관례).
function toNewsMarkers(
  bars: PriceBar[],
  news: StockNewsItem[],
  colors: ChartColors,
): SeriesMarker<UTCTimestamp>[] {
  if (bars.length === 0) return [];
  const barTimes = bars.map((b) => toTime(b.ts));
  const strong = news
    .filter(
      (n) =>
        n.publishedAt !== null &&
        n.sentiment !== null &&
        Math.abs(n.sentiment) >= MARKER_MIN_ABS_SENTIMENT,
    )
    .sort((a, b) => Date.parse(b.publishedAt!) - Date.parse(a.publishedAt!))
    .slice(0, MARKER_LIMIT);

  const taken = new Set<number>();
  const markers: SeriesMarker<UTCTimestamp>[] = [];
  for (const item of strong) {
    const published = Date.parse(item.publishedAt!) / 1000;
    const hit = barTimes.find((t) => t >= published) ?? barTimes[barTimes.length - 1];
    if (taken.has(hit)) continue; // 한 봉에 여러 기사면 가장 최근 것만 — 마커 겹침 방지
    taken.add(hit);
    const positive = item.sentiment! > 0;
    markers.push({
      time: hit,
      position: positive ? "belowBar" : "aboveBar",
      shape: positive ? "arrowUp" : "arrowDown",
      color: positive ? colors.up : colors.down,
      text: item.title.length > 20 ? `${item.title.slice(0, 20)}…` : item.title,
    });
  }
  return markers.sort((a, b) => a.time - b.time);
}

type ConeGeometry = {
  start: UTCTimestamp; // 마지막 봉 = 예측 시작
  end: UTCTimestamp; // horizon 거래일 뒤
  base: number; // 시작 가격
  low: number; // 하위 25%(또는 ATR 하단) 가격
  high: number; // 상위 25%(또는 ATR 상단) 가격
  label: string;
};

type ChartRefs = {
  chart: IChartApi;
  candles: ISeriesApi<"Candlestick">;
  volume: ISeriesApi<"Histogram">;
  ma20: ISeriesApi<"Line">;
  ma50: ISeriesApi<"Line">;
  rsi: ISeriesApi<"Line">;
  bandLines: ISeriesApi<"Line">[];
  priceLines: IPriceLine[];
  markers: ISeriesMarkersPluginApi<Time>;
};

export default function CandleChart({
  bars,
  support,
  resistance,
  forecast,
  quotePrice,
  sessionTz = "America/New_York",
  rangeDays,
  news,
  intraday = false,
  pattern,
}: CandleChartProps) {
  // 테마 전환 시 차트를 통째로 재구성한다 — layout·시리즈·priceLine에 색이 흩어져 있어
  // 부분 재색칠보다 재생성이 단순하고, 전환은 드문 사용자 액션이라 비용이 문제되지 않는다.
  const dark = useThemeStore((s) => s.theme) === "dark";
  const C = chartColors(dark);

  const containerRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<SVGSVGElement>(null);
  const profileRef = useRef<SVGSVGElement>(null); // 매물대 — 콘의 display 토글과 독립
  const refs = useRef<ChartRefs | null>(null);
  // 예측 밴드가 미래로 뻗은 끝점 — 표시 구간을 밴드까지 포함시켜야 밴드가 화면에 들어온다
  const bandEndRef = useRef<UTCTimestamp | null>(null);
  // 예측 콘을 오버레이로 칠하기 위한 기하 정보(가격·시각). 화면 좌표 변환은 그릴 때 한다.
  const coneRef = useRef<ConeGeometry | null>(null);
  // setData가 봉을 원복해도 최신 quote를 재적용할 수 있게 ref로 보관
  const quoteRef = useRef<number | null>(null);
  quoteRef.current = quotePrice ?? null;
  // 저장 봉에 없는 "오늘" 임시 봉 — quote 갱신 간 open/고저 유지용
  const provisionalRef = useRef<{ time: number; open: number; high: number; low: number } | null>(null);
  const prevBarsRef = useRef<PriceBar[] | null>(null);
  const prevBandEndRef = useRef<UTCTimestamp | null>(null);

  // 지연 현재가 반영 — 마지막 저장 봉이 오늘 봉일 때만 병합하고,
  // 오늘 봉이 아직 없으면(야간 수집 전) 임시 봉을 덧붙인다. 과거 봉은 왜곡하지 않는다.
  const applyQuote = (r: ChartRefs) => {
    const price = quoteRef.current;
    if (!price || bars.length === 0) return;
    const last = bars[bars.length - 1];
    // 세션 날짜는 거래소 타임존으로 판정한다 — UTC 날짜 비교는 KST 세션과 어긋나
    // "어제" 자리에 오늘 현재가로 만든 임시 봉이 생겼다(한국 종목 오전 재현).
    const lastKey = sessionDayKey(new Date(last.ts), sessionTz);
    const todayKey = sessionDayKey(new Date(), sessionTz);
    if (todayKey === lastKey) {
      r.candles.update({
        time: toTime(last.ts),
        open: last.open,
        high: Math.max(last.high, price),
        low: Math.min(last.low, price),
        close: price,
      });
    } else if (todayKey > lastKey) {
      const dow = new Date(`${todayKey}T00:00:00Z`).getUTCDay();
      if (dow === 0 || dow === 6) return; // 거래소 기준 주말 — 유령 봉 방지
      // 임시 봉 시각은 실봉과 같은 관례(세션 자정 기준 ts)를 유지한다 —
      // 마지막 실봉 ts + 달력일 차이. 다음날 실봉이 적재되면 같은 시각으로 덮인다.
      const diffDays = Math.round(
        (Date.parse(todayKey) - Date.parse(lastKey)) / 86_400_000,
      );
      const time = (toTime(last.ts) + diffDays * 86_400) as UTCTimestamp;
      const prev = provisionalRef.current?.time === time ? provisionalRef.current : null;
      const bar = {
        time,
        open: prev?.open ?? price,
        high: Math.max(prev?.high ?? price, price),
        low: Math.min(prev?.low ?? price, price),
        close: price,
      };
      provisionalRef.current = { time, open: bar.open, high: bar.high, low: bar.low };
      r.candles.update(bar);
    }
  };

  // 예측 콘 오버레이 — 점선 3개만으로는 "여기가 예측 구간"이라는 게 읽히지 않는다.
  // lightweight-charts는 두 시리즈 사이 채우기를 지원하지 않으므로 차트 좌표를 받아
  // SVG로 직접 칠한다. 팬·줌·리사이즈마다 다시 그려야 해서 React 상태가 아닌 DOM 직접 갱신이다.
  const drawCone = () => {
    const svg = overlayRef.current;
    const r = refs.current;
    if (!svg || !r) return;

    const hide = () => svg.style.setProperty("display", "none");
    const cone = coneRef.current;
    if (!cone) return hide();

    const scale = r.chart.timeScale();
    const x0 = scale.timeToCoordinate(cone.start);
    const x1 = scale.timeToCoordinate(cone.end);
    const yBase = r.candles.priceToCoordinate(cone.base);
    const yLow = r.candles.priceToCoordinate(cone.low);
    const yHigh = r.candles.priceToCoordinate(cone.high);
    // 예측 구간이 화면 밖으로 밀려나면(과거 쪽으로 팬) 조용히 숨긴다
    if (x0 === null || x1 === null || yBase === null || yLow === null || yHigh === null) {
      return hide();
    }

    svg.style.removeProperty("display");
    const set = (id: string, attrs: Record<string, string | number>) => {
      const el = svg.querySelector(`#${id}`);
      if (el) for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
    };

    // 캔들 페인 높이 — RSI 서브차트·시간축까지 음영이 흘러내리지 않게 자른다
    const height = r.chart.panes()[0]?.getHeight() ?? svg.clientHeight;
    // 미래 구간 배경 음영 — 봉이 끊기는 지점부터가 예측이라는 걸 한눈에 보이게 한다
    set("fc-zone", { x: x0, y: 0, width: Math.max(0, x1 - x0), height });
    set("fc-cone", {
      points: `${x0},${yBase} ${x1},${yHigh} ${x1},${yLow}`,
    });
    set("fc-divider", { x1: x0, y1: 0, x2: x0, y2: height });

    const text = svg.querySelector("#fc-label-text");
    const box = svg.querySelector("#fc-label-box");
    if (text instanceof SVGTextElement && box) {
      text.textContent = cone.label;
      const boxWidth = text.getComputedTextLength() + 12;
      // 예측 구간은 늘 오른쪽 끝이라 라벨이 그대로 두면 가격축 밖으로 잘린다 — 폭 안으로 당긴다
      const boxX = Math.min(x0 + 6, scale.width() - boxWidth - 4);
      box.setAttribute("x", String(boxX));
      box.setAttribute("y", "6");
      box.setAttribute("width", String(boxWidth));
      text.setAttribute("x", String(boxX + 6));
      text.setAttribute("y", "19");
    }
  };

  // 매물대 — 표시 구간의 봉만 집계해 오른쪽 가장자리에 가로 막대로 그린다.
  // 구간을 바꾸면 분포도 함께 바뀐다(보는 기간의 거래 밀집이 곧 그 기간의 매물대).
  // 팬·줌·리사이즈마다 다시 그려야 해서 콘과 같은 DOM 직접 갱신이다.
  const drawProfile = () => {
    const svg = profileRef.current;
    const r = refs.current;
    if (!svg || !r) return;
    const group = svg.querySelector("#vp-bins");
    if (!group) return;
    while (group.firstChild) group.removeChild(group.firstChild);

    const range = r.chart.timeScale().getVisibleRange();
    const visible = range
      ? bars.filter((b) => {
          const t = toTime(b.ts);
          return t >= (range.from as number) && t <= (range.to as number);
        })
      : bars;
    const profile = computeVolumeProfile(visible);
    if (!profile) return;

    const paneWidth = r.chart.timeScale().width();
    const paneHeight = r.chart.panes()[0]?.getHeight() ?? svg.clientHeight;
    const maxBarWidth = paneWidth * 0.16; // 캔들을 가리지 않는 상한
    for (let i = 0; i < profile.bins.length; i++) {
      const bin = profile.bins[i];
      if (bin.volume <= 0) continue;
      const yHigh = r.candles.priceToCoordinate(bin.high);
      const yLow = r.candles.priceToCoordinate(bin.low);
      if (yHigh === null || yLow === null) continue;
      const top = Math.max(0, Math.min(yHigh, yLow));
      const bottom = Math.min(paneHeight, Math.max(yHigh, yLow));
      if (bottom - top < 1) continue; // 가격축 밖으로 밀린 구간
      const width = (bin.volume / profile.maxVolume) * maxBarWidth;
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", String(paneWidth - width));
      rect.setAttribute("y", String(top + 0.5));
      rect.setAttribute("width", String(width));
      rect.setAttribute("height", String(Math.max(1, bottom - top - 1)));
      rect.setAttribute(
        "fill",
        // 최다 거래 구간만 강조 — "여기서 가장 많이 거래됐다"는 팩트 표시
        i === profile.pocIndex ? C.profilePoc : C.profileBin,
      );
      group.appendChild(rect);
    }
  };

  // 표시 구간 적용 — 전체(fitContent)로 두면 5거래일 예측 밴드가 오른쪽 끝 실오라기가 된다.
  const applyRange = (r: ChartRefs) => {
    const scale = r.chart.timeScale();
    if (bars.length === 0) return;
    if (!rangeDays) {
      scale.fitContent();
      return;
    }
    const lastBar = toTime(bars[bars.length - 1].ts);
    const to = Math.max(lastBar, bandEndRef.current ?? lastBar) as UTCTimestamp;
    const from = Math.max(toTime(bars[0].ts), to - rangeDays * 86_400) as UTCTimestamp;
    if (from >= to) {
      scale.fitContent(); // 보유 봉이 프리셋보다 짧음 — 있는 만큼 다 보여준다
      return;
    }
    scale.setVisibleRange({ from, to });
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { color: "transparent" },
        textColor: C.text,
        fontFamily:
          "'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
        panes: { separatorColor: C.border, enableResize: false },
      },
      grid: {
        vertLines: { color: C.grid },
        horzLines: { color: C.grid },
      },
      rightPriceScale: { borderColor: C.border },
      // 일봉에 시간을 켜면 축·크로스헤어에 "04:00:00"이 붙어 읽기만 나빠진다
      timeScale: { borderColor: C.border, timeVisible: intraday },
      crosshair: { horzLine: { labelBackgroundColor: C.brand }, vertLine: { labelBackgroundColor: C.brand } },
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: C.up,
      downColor: C.down,
      wickUpColor: C.up,
      wickDownColor: C.down,
      borderVisible: false,
    });
    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    const lineDefaults = { lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false } as const;
    const ma20 = chart.addSeries(LineSeries, { color: C.ma20, ...lineDefaults });
    const ma50 = chart.addSeries(LineSeries, { color: C.ma50, ...lineDefaults });

    // RSI 서브차트 — pane 1
    const rsi = chart.addSeries(LineSeries, { color: C.rsi, ...lineDefaults }, 1);
    rsi.createPriceLine({ price: 70, color: C.rsiGuide, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "" });
    rsi.createPriceLine({ price: 30, color: C.rsiGuide, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "" });
    chart.panes()[1]?.setHeight(80);

    refs.current = {
      chart, candles, volume, ma20, ma50, rsi,
      bandLines: [], priceLines: [], markers: createSeriesMarkers(candles),
    };

    // 팬·줌·리사이즈마다 예측 콘·매물대를 차트 좌표에 다시 맞춘다
    const redraw = () => {
      drawCone();
      drawProfile();
    };
    chart.timeScale().subscribeVisibleTimeRangeChange(redraw);
    const observer = new ResizeObserver(redraw);
    observer.observe(el);

    return () => {
      observer.disconnect();
      chart.timeScale().unsubscribeVisibleTimeRangeChange(redraw);
      chart.remove();
      refs.current = null;
    };
    // dark — 테마 전환 시 재생성. 아래 데이터 이펙트들도 dark를 의존성에 갖고 있어
    // 같은 커밋에서 (정의 순서대로) 이 이펙트 다음에 실행돼 데이터를 다시 채운다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dark]);

  useEffect(() => {
    const r = refs.current;
    if (!r) return;

    r.candles.setData(
      bars.map((b) => ({ time: toTime(b.ts), open: b.open, high: b.high, low: b.low, close: b.close })),
    );
    r.volume.setData(
      bars.map((b) => ({
        time: toTime(b.ts),
        value: b.volume,
        color: b.close >= b.open ? C.volUp : C.volDown,
      })),
    );
    r.ma20.setData(sma(bars, 20));
    r.ma50.setData(sma(bars, 50));
    r.rsi.setData(rsiSeries(bars));

    r.priceLines.forEach((line) => r.candles.removePriceLine(line));
    r.priceLines = [];
    const lineOptions = { lineWidth: 1, lineStyle: 2, axisLabelVisible: true } as const;
    if (support) {
      r.priceLines.push(
        r.candles.createPriceLine({ price: support, color: C.down, title: "60일 최저", ...lineOptions }),
      );
    }
    if (resistance) {
      r.priceLines.push(
        r.candles.createPriceLine({ price: resistance, color: C.up, title: "60일 최고", ...lineOptions }),
      );
    }

    // 예측 밴드 — 마지막 봉에서 horizon 거래일 뒤로 분위수(또는 ATR 콘)를 점선 투영.
    // 가격축 라벨은 달지 않는다 — 지지/저항/현재가와 겹쳐 우측이 읽을 수 없게 뭉친다.
    // 실제 범위는 좌상단 범례에 한 줄로 적는다.
    r.bandLines.forEach((s) => r.chart.removeSeries(s));
    r.bandLines = [];
    bandEndRef.current = null;
    coneRef.current = null;
    const band = forecast?.band;
    if (band && bars.length > 0) {
      const lastBar = bars[bars.length - 1];
      const start = { time: toTime(lastBar.ts), value: lastBar.close };
      const steps = futureTimes(lastBar.ts, forecast.horizon_days);
      const end = steps[steps.length - 1];
      bandEndRef.current = end;
      coneRef.current = {
        start: start.time,
        end,
        base: lastBar.close,
        low: lastBar.close * (1 + band.q25_pct),
        high: lastBar.close * (1 + band.q75_pct),
        label: `${forecast.horizon_days}일 예측 범위 ${pct(band.q25_pct)} ~ ${pct(band.q75_pct)}`,
      };
      const targets: { pct: number; color: string; width: 1 | 2 }[] =
        band.source === "quantile"
          ? [
              { pct: band.q75_pct, color: C.up, width: 2 },
              { pct: band.median_pct, color: C.median, width: 1 },
              { pct: band.q25_pct, color: C.down, width: 2 },
            ]
          : [
              { pct: band.q75_pct, color: C.up, width: 2 },
              { pct: band.q25_pct, color: C.down, width: 2 },
            ];
      for (const t of targets) {
        const series = r.chart.addSeries(LineSeries, {
          color: t.color,
          lineWidth: t.width,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        // 목표 수익률까지 거래일마다 선형 보간 — 축이 인덱스 간격이라 중간 점이 곧 가로 폭이다
        series.setData([
          start,
          ...steps.map((time, i) => ({
            time,
            value: lastBar.close * (1 + t.pct * ((i + 1) / steps.length)),
          })),
        ]);
        r.bandLines.push(series);
      }
    }

    // 형태 보조선 — 어깨·넥라인을 잇는다. 밴드와 같은 배열에 넣어 정리 경로를 공유한다.
    if (pattern && bars.length > 0) {
      const shape = pattern.points
        .filter(([i]) => i >= 0 && i < bars.length)
        .map(([i, price]) => ({ time: toTime(bars[i].ts), value: price }));
      if (shape.length >= 2) {
        const series = r.chart.addSeries(LineSeries, {
          color: C.pattern,
          lineWidth: 2,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        series.setData(shape);
        r.bandLines.push(series);
      }
    }

    // setData가 봉을 원복하므로 quote를 재적용한다(임시 봉 추적은 리셋)
    provisionalRef.current = null;
    applyQuote(r);

    // 줌 리셋은 봉 데이터 자체가 바뀔 때만 — forecast/analyze 지연 도착이 뷰를 뺏지 않게.
    // 단 밴드가 뒤늦게 도착하면 표시 구간 오른쪽 끝이 밴드 밖이므로 그때는 한 번 더 맞춘다.
    if (prevBarsRef.current !== bars || prevBandEndRef.current !== bandEndRef.current) {
      applyRange(r);
      prevBarsRef.current = bars;
      prevBandEndRef.current = bandEndRef.current;
    }
    drawCone(); // 가격축 자동 스케일이 바뀌었을 수 있다 — 구간 이동이 없어도 다시 그린다
    drawProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bars, support, resistance, forecast, pattern, dark]);

  // 뉴스 감성 마커 — 봉/뉴스/테마가 바뀔 때만 재계산
  useEffect(() => {
    const r = refs.current;
    if (r) r.markers.setMarkers(toNewsMarkers(bars, news ?? [], C));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bars, news, dark]);

  // 타임프레임 전환 — 차트는 재생성하지 않으므로 시간축 옵션만 갈아끼운다
  useEffect(() => {
    refs.current?.chart.applyOptions({ timeScale: { timeVisible: intraday } });
  }, [intraday]);

  // 기간 프리셋 전환 — 데이터는 그대로 두고 표시 구간만 옮긴다
  useEffect(() => {
    const r = refs.current;
    if (r) applyRange(r);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rangeDays]);

  // 준실시간 현재가 — 마지막 봉만 갱신(전체 setData 없이 깜빡임 방지)
  useEffect(() => {
    const r = refs.current;
    if (r) applyQuote(r);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quotePrice, bars]);

  return (
    <div className="relative flex-1 min-h-0">
      <div ref={containerRef} className="absolute inset-0" />
      {/* 예측 콘 — 차트 좌표에 맞춰 drawCone()이 DOM을 직접 갱신한다(팬·줌마다 재계산) */}
      {/* w-full h-full 필수 — inset-0만으로는 SVG가 기본 300×150에 머물러 도형이 잘린다 */}
      <svg
        ref={overlayRef}
        className="absolute inset-0 w-full h-full z-0 pointer-events-none"
        style={{ display: "none" }}
        aria-hidden
      >
        <rect id="fc-zone" fill={C.fcZone} />
        <polygon id="fc-cone" fill={C.fcCone} />
        <line id="fc-divider" stroke={C.brand} strokeWidth={1} strokeDasharray="3 3" opacity={0.5} />
        <rect id="fc-label-box" height={17} rx={4} fill={C.brand} />
        <text id="fc-label-text" fill="#FFFFFF" fontSize={10.5} fontWeight={600} />
      </svg>
      {/* 매물대 — drawProfile()이 표시 구간 봉을 집계해 rect를 직접 채운다 */}
      <svg
        ref={profileRef}
        className="absolute inset-0 w-full h-full z-0 pointer-events-none"
        aria-hidden
      >
        <g id="vp-bins" />
      </svg>
      {/* 범례 — 375px에서는 예측 라벨·축 라벨과 겹쳐 서로를 지운다(2026-08-17 시각 검증). 숨긴다. */}
      <div className="absolute left-3 top-2 z-10 hidden sm:flex items-center gap-3 text-xs text-foreground-muted pointer-events-none">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5" style={{ background: C.ma20 }} /> MA20
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5" style={{ background: C.ma50 }} /> MA50
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5" style={{ background: C.rsi }} /> RSI(14)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2.5" style={{ background: C.profileBin }} />
          매물대(표시 구간 거래 밀집)
        </span>
        {/* 범위 숫자는 차트 위 알약이 이미 말한다 — 여기는 산출 방식만 (중복 표기 방지) */}
        {forecast?.band && (
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 border-t border-dashed border-foreground-muted" />
            예측 산출:{" "}
            {forecast.band.source === "quantile"
              ? `과거 실적 분위수 · 중앙 ${pct(forecast.band.median_pct)}`
              : "변동성(ATR) 기반"}
          </span>
        )}
        {news && news.length > 0 && <span>▲▼ 감성 강한 뉴스</span>}
      </div>
      {/* lightweight-charts 라이선스 고지 */}
      <a
        href="https://www.tradingview.com/"
        target="_blank"
        rel="noopener noreferrer"
        className="absolute right-2 bottom-1 z-10 text-xs text-foreground-muted/70 hover:text-foreground-muted"
      >
        Charts by TradingView
      </a>
    </div>
  );
}
