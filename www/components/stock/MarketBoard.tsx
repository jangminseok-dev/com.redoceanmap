"use client";

import { useQuery } from "@tanstack/react-query";
import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { fetchStockBoard, fetchStockQuote } from "@/lib/api";
import { formatPrice } from "@/lib/currency";
import type { StockBoardRow } from "@/lib/types";

// 한국 관례: 상승 빨강 / 하락 파랑 (차트·방향 배지와 동일)
const UP = "#DC2626";
const DOWN = "#2563EB";

// 지수는 수집 대상이 아니다(price_bars는 레짐 판정용 SPY·^VIX만 담는다) —
// 서버 20초 공유 캐시가 붙은 quote를 그대로 재사용한다.
const INDICES = [
  { symbol: "^GSPC", label: "S&P 500" },
  { symbol: "^IXIC", label: "나스닥" },
  { symbol: "^KS11", label: "코스피" },
  { symbol: "KRW=X", label: "원/달러" },
];

const DIRECTION_META = {
  UP: { label: "상승", icon: TrendingUp, className: "text-red-600 bg-red-50 border-red-200" },
  DOWN: { label: "하락", icon: TrendingDown, className: "text-blue-600 bg-blue-50 border-blue-200" },
  NEUTRAL: { label: "중립", icon: Minus, className: "text-foreground-muted bg-surface border-border" },
} as const;

const signedPct = (v: number) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;

function changeClass(v: number | null | undefined) {
  if (v === null || v === undefined) return "text-foreground-muted";
  return v > 0 ? "text-red-600" : v < 0 ? "text-blue-600" : "text-foreground-muted";
}

function IndexChip({ symbol, label }: { symbol: string; label: string }) {
  const { data } = useQuery({
    queryKey: ["quote", symbol],
    queryFn: () => fetchStockQuote(symbol),
    retry: false,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
  // 조회 실패한 지수는 조용히 빠진다 — 스트립은 장식이고 보드가 본체다
  if (!data) return null;

  return (
    <span className="inline-flex items-baseline gap-1.5 whitespace-nowrap">
      <span className="text-foreground-muted">{label}</span>
      <span className="font-semibold tabular-nums">
        {data.price.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}
      </span>
      {data.change_pct != null && (
        <span className={`tabular-nums ${changeClass(data.change_pct)}`}>
          {signedPct(data.change_pct)}
        </span>
      )}
    </span>
  );
}

function Sparkline({ values, rising }: { values: number[]; rising: boolean }) {
  if (values.length < 2) return <span className="inline-block w-16" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * 64},${23 - ((v - min) / span) * 22}`)
    .join(" ");

  return (
    <svg width={64} height={24} viewBox="0 0 64 24" className="shrink-0" aria-hidden>
      <polyline
        points={points}
        fill="none"
        stroke={rising ? UP : DOWN}
        strokeWidth={1.25}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

function BoardRow({ row, onSelect }: { row: StockBoardRow; onSelect: (symbol: string) => void }) {
  const meta = DIRECTION_META[row.direction] ?? DIRECTION_META.NEUTRAL;
  const DirectionIcon = meta.icon;
  const rising = row.sparkline.length >= 2 && row.sparkline[row.sparkline.length - 1] >= row.sparkline[0];

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(row.ticker)}
        className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left hover:bg-accent transition-colors"
      >
        <span className="w-28 shrink-0 min-w-0">
          <span className="block text-sm font-medium truncate">{row.name}</span>
          <span className="block text-[11px] text-foreground-muted truncate">{row.ticker}</span>
        </span>
        <Sparkline values={row.sparkline} rising={rising} />
        <span className="w-24 shrink-0 text-right text-sm tabular-nums">
          {formatPrice(row.price, row.ticker)}
        </span>
        <span className={`w-16 shrink-0 text-right text-xs tabular-nums ${changeClass(row.change_pct)}`}>
          {row.change_pct != null ? signedPct(row.change_pct) : "—"}
        </span>
        <span
          className={`w-24 shrink-0 inline-flex items-center justify-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium ${meta.className}`}
        >
          <DirectionIcon size={11} strokeWidth={2} />
          {meta.label} {row.score >= 0 ? "+" : ""}{row.score.toFixed(2)}
        </span>
        <span className="w-20 shrink-0 text-right text-[11px] tabular-nums text-foreground-muted">
          {row.edge_pct != null ? (
            <>
              평소 {row.edge_pct >= 0 ? "+" : ""}
              {(row.edge_pct * 100).toFixed(0)}%p
            </>
          ) : (
            "—"
          )}
        </span>
      </button>
    </li>
  );
}

export default function MarketBoard({ onSelect }: { onSelect: (symbol: string) => void }) {
  const boardQ = useQuery({
    queryKey: ["stock-board"],
    queryFn: () => fetchStockBoard(),
    staleTime: 10 * 60_000, // 스냅샷은 일 1회 갱신 — 재방문마다 다시 받을 이유가 없다
  });

  // 신호는 스냅샷(일 1회)에서, 가격은 그 뒤 더 쌓인 최신 봉에서 온다 — 한 날짜로 뭉뚱그리면
  // "기준 7/21"인데 가격은 7/22인 화면이 된다. 두 날짜가 다르면 둘 다 적는다.
  const asOf = boardQ.data?.rows[0]?.as_of;
  const priceAsOf = boardQ.data?.rows[0]?.price_as_of;
  const day = (iso: string) =>
    new Date(iso).toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
  const sameDay = asOf && priceAsOf && day(asOf) === day(priceAsOf);

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="flex items-center gap-4 px-4 py-2 border-b border-border overflow-x-auto text-xs">
        {INDICES.map((index) => (
          <IndexChip key={index.symbol} {...index} />
        ))}
      </div>

      <div className="px-6 pt-6 pb-4 text-center">
        <h2 className="text-lg font-semibold">주식 분석 워크스페이스</h2>
        <p className="mt-1.5 text-sm text-foreground-muted">
          아래 보드에서 고르거나, 오른쪽 채팅에 종목명·티커를 물어보세요
        </p>
      </div>

      <div className="px-4 pb-6">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 px-3 pb-1.5">
          <h3 className="text-sm font-semibold">오늘의 신호 보드</h3>
          <span className="text-[11px] text-foreground-muted">
            워치리스트 · 신호가 뚜렷한 순
            {boardQ.data && ` · ${boardQ.data.horizon_days}일 예측`}
            {asOf && ` · 신호 ${day(asOf)} 기준`}
            {priceAsOf && !sameDay && ` · 가격 ${day(priceAsOf)} 종가`}
          </span>
        </div>

        {boardQ.isLoading && (
          <div className="flex flex-col gap-1.5 px-3">
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="skeleton h-11 rounded-lg" />
            ))}
          </div>
        )}

        {boardQ.data && boardQ.data.rows.length === 0 && (
          <p className="px-3 py-6 text-center text-sm text-foreground-muted">
            아직 쌓인 예측 스냅샷이 없습니다. 위에서 종목을 직접 열어보세요.
          </p>
        )}

        {boardQ.isError && (
          <p className="px-3 py-6 text-center text-sm text-foreground-muted">
            신호 보드를 불러오지 못했습니다. 위에서 종목을 직접 열어보세요.
          </p>
        )}

        {boardQ.data && boardQ.data.rows.length > 0 && (
          <>
            <ul className="flex flex-col">
              {boardQ.data.rows.map((row) => (
                <BoardRow key={row.ticker} row={row} onSelect={onSelect} />
              ))}
            </ul>
            <p className="mt-3 px-3 text-[11px] text-foreground-muted leading-relaxed">
              매수 추천 순위가 아니라 지표 신호가 뚜렷한 순서입니다. &lsquo;평소 대비&rsquo;는 과거 같은
              신호에서의 상승 비율과 평소 상승률의 차이로, 과거 통계이며 미래를 보장하지 않습니다.
              가격은 최근 수집 종가라 실시간이 아닙니다.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
