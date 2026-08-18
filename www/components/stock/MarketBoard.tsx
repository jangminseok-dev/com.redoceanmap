"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { fetchStockBoard } from "@/lib/api";
import { formatPrice, formatTurnover } from "@/lib/currency";
import SymbolMark from "@/components/common/SymbolMark";
import type { StockBoardRow } from "@/lib/types";

// 좌측 목록의 방향 필터 — 종목이 늘면 상승 신호만 훑는 동작이 기본이 된다(레퍼런스 토스 필터 칩)
const FILTERS = [
  { key: "ALL", label: "전체" },
  { key: "UP", label: "상승" },
  { key: "DOWN", label: "하락" },
] as const;
type FilterKey = (typeof FILTERS)[number]["key"];

const DIRECTION_META = {
  UP: { label: "상승", icon: TrendingUp, className: "text-up bg-up-weak border-up/20" },
  DOWN: { label: "하락", icon: TrendingDown, className: "text-down bg-down-weak border-down/20" },
  NEUTRAL: { label: "중립", icon: Minus, className: "text-foreground-muted bg-surface border-border" },
} as const;

const signedPct = (v: number) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;

// 등락률 배경 하이라이트 — 값보다 방향이 먼저 읽히게 한다(DESIGN.md §2 Direction roles)
function toneBox(v: number | null | undefined) {
  if (v === null || v === undefined) return "text-foreground-muted";
  if (v > 0) return "text-up bg-up-weak";
  if (v < 0) return "text-down bg-down-weak";
  return "text-foreground-muted";
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
        stroke={rising ? "var(--up)" : "var(--down)"}
        strokeWidth={1.25}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

function BoardRow({
  row,
  rank,
  compact,
  active,
  onSelect,
}: {
  row: StockBoardRow;
  rank: number;
  compact: boolean; // 320px 좌측 컬럼 — 스파크라인·신호·평소대비를 접는다
  active: boolean;
  onSelect: (symbol: string) => void;
}) {
  const meta = DIRECTION_META[row.direction] ?? DIRECTION_META.NEUTRAL;
  const DirectionIcon = meta.icon;
  const rising =
    row.sparkline.length >= 2 && row.sparkline[row.sparkline.length - 1] >= row.sparkline[0];

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(row.ticker)}
        aria-current={active ? "true" : undefined}
        // 활성 행 — 면 + 좌측 2px 브랜드 보더. 색을 넓게 칠하지 않고 위치로 말한다(핸드오프 §3)
        className={`relative w-full flex items-center gap-3 px-4 py-2.5 text-left border-b border-border transition-colors ${
          active ? "bg-accent shadow-[inset_2px_0_0_var(--brand)]" : "hover:bg-accent"
        }`}
      >
        <span className="w-5 shrink-0 text-xs tabular-nums text-foreground-muted">{rank}</span>
        <SymbolMark name={row.name} />

        <span className="flex-1 min-w-0">
          <span className="block text-sm font-medium truncate">{row.name}</span>
          <span className="block text-xs text-foreground-muted truncate">{row.ticker}</span>
        </span>

        {!compact && (
          <span className="hidden sm:block">
            <Sparkline values={row.sparkline} rising={rising} />
          </span>
        )}

        <span className="w-24 shrink-0 text-right text-sm font-medium tabular-nums">
          {formatPrice(row.price, row.ticker)}
        </span>

        {/* 등락액 — 토스 표 컨벤션(현재가·등락액·등락률). 등락률로 역산한 근사치다 */}
        {!compact && (
          <span
            className={`hidden xl:block w-24 shrink-0 text-right text-sm tabular-nums ${
              row.change_pct == null
                ? "text-foreground-muted"
                : row.change_pct > 0
                  ? "text-up"
                  : row.change_pct < 0
                    ? "text-down"
                    : "text-foreground-muted"
            }`}
          >
            {row.change_pct != null
              ? `${row.change_pct > 0 ? "+" : ""}${formatPrice(row.price - row.price / (1 + row.change_pct), row.ticker)}`
              : "—"}
          </span>
        )}

        <span
          className={`w-[72px] shrink-0 text-right text-sm font-medium tabular-nums px-1.5 py-0.5 rounded-md ${toneBox(row.change_pct)}`}
        >
          {row.change_pct != null ? signedPct(row.change_pct) : "—"}
        </span>

        {!compact && (
          <>
            {/* 거래대금 — 통화가 섞이므로 값끼리 비교하지 않는다. 종목별 규모를 읽는 용도다. */}
            <span className="hidden xl:block w-24 shrink-0 text-right text-xs tabular-nums text-foreground-muted">
              {row.turnover != null ? formatTurnover(row.turnover, row.ticker) : "—"}
            </span>

            <span
              className={`hidden lg:inline-flex w-[104px] shrink-0 items-center justify-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium ${meta.className}`}
            >
              <DirectionIcon size={11} strokeWidth={2} />
              {meta.label} {row.score >= 0 ? "+" : ""}
              {row.score.toFixed(2)}
            </span>

            <span className="hidden lg:block w-20 shrink-0 text-right text-xs tabular-nums text-foreground-muted">
              {row.edge_pct != null ? (
                <>
                  평소 {row.edge_pct >= 0 ? "+" : ""}
                  {(row.edge_pct * 100).toFixed(0)}%p
                </>
              ) : (
                "—"
              )}
            </span>
          </>
        )}
      </button>
    </li>
  );
}

function SummaryTile({
  label,
  count,
  className,
}: {
  label: string;
  count: number;
  className: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2.5">
      <p className="text-xs text-foreground-muted">{label}</p>
      <p className={`text-data-xl tabular-nums ${className}`}>
        {count}
        <span className="ml-0.5 text-sm font-normal text-foreground-muted">개</span>
      </p>
    </div>
  );
}

export default function MarketBoard({
  onSelect,
  compact = false,
  selected = null,
}: {
  onSelect: (symbol: string) => void;
  /** 좌측 320px 컬럼에서 쓰는 축약형 — 지수 티커·요약·각주를 접고 표만 남긴다 */
  compact?: boolean;
  selected?: string | null;
}) {
  const boardQ = useQuery({
    queryKey: ["stock-board"],
    queryFn: () => fetchStockBoard(),
    staleTime: 10 * 60_000, // 스냅샷은 일 1회 갱신 — 재방문마다 다시 받을 이유가 없다
  });
  const [filter, setFilter] = useState<FilterKey>("ALL"); // 상태는 이 하나뿐이다

  const rows = boardQ.data?.rows ?? [];
  const filtered = filter === "ALL" ? rows : rows.filter((r) => r.direction === filter);
  const counts = rows.reduce(
    (acc, row) => ({ ...acc, [row.direction]: acc[row.direction] + 1 }),
    { UP: 0, DOWN: 0, NEUTRAL: 0 } as Record<StockBoardRow["direction"], number>,
  );

  // 신호는 스냅샷(일 1회)에서, 가격은 그 뒤 더 쌓인 최신 봉에서 온다 — 한 날짜로 뭉뚱그리면
  // "기준 7/21"인데 가격은 7/22인 화면이 된다. 두 날짜가 다르면 둘 다 적는다.
  const asOf = boardQ.data?.rows[0]?.as_of;
  const priceAsOf = boardQ.data?.rows[0]?.price_as_of;
  const day = (iso: string) =>
    new Date(iso).toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
  const sameDay = asOf && priceAsOf && day(asOf) === day(priceAsOf);

  return (
    // 스크롤은 WorkspaceShell이 잡는다 — 여기서 또 잡으면 이중 스크롤이 된다.
    // 지수 티커는 MarketStrip으로 분리됐다(스테이지 최상단 상주 — 페이지가 배치한다).
    <div>
      {/* 방향 필터 — 알약 칩(낮은 위계, Button 스케일과 섞지 않는다) */}
      <div className="flex items-center gap-1.5 px-4 pt-3 pb-1">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            aria-pressed={filter === f.key}
            className={`inline-flex items-center h-7 px-2.5 rounded-full text-xs font-medium transition-colors duration-150 ${
              filter === f.key
                ? "bg-brand text-white"
                : "border border-border text-foreground-muted hover:bg-accent hover:text-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto text-xs text-foreground-muted">신호순</span>
      </div>
      {compact && asOf && (
        <p className="px-4 pb-1.5 text-xs text-foreground-muted">
          신호 {day(asOf)} 기준{priceAsOf && ` · 가격 ${day(priceAsOf)} 종가`}
        </p>
      )}

      {/* 신호 요약 — 보드 행을 세어 만든다(새 요청 없음). 표가 길어 위에서 전체 그림이 안 잡히던 자리다.
          "주식 분석" 제목은 뺐다 — 레일에서 주식이 활성이라 어디인지는 이미 알고 있다. */}
      {!compact && rows.length > 0 && (
        <div className="grid grid-cols-3 gap-2 px-4 pt-4 pb-1">
          <SummaryTile label="상승 신호" count={counts.UP} className="text-up" />
          <SummaryTile label="하락 신호" count={counts.DOWN} className="text-down" />
          <SummaryTile label="중립" count={counts.NEUTRAL} className="text-foreground-muted" />
        </div>
      )}

      <div className="flex flex-wrap items-baseline gap-x-2 px-4 pt-4 pb-2">
        <h3 className="text-base font-semibold">오늘의 신호 보드</h3>
        {!compact && (
          <span className="text-xs text-foreground-muted">
            워치리스트 · 신호가 뚜렷한 순
            {boardQ.data && ` · ${boardQ.data.horizon_days}일 예측`}
            {asOf && ` · 신호 ${day(asOf)} 기준`}
            {priceAsOf && !sameDay && ` · 가격 ${day(priceAsOf)} 종가`}
          </span>
        )}
      </div>

      {boardQ.isLoading && (
        <div className="flex flex-col gap-1.5 px-4">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="skeleton h-12 rounded-lg" />
          ))}
        </div>
      )}

      {boardQ.data && boardQ.data.rows.length === 0 && (
        <p className="px-4 py-6 text-center text-sm text-foreground-muted">
          아직 쌓인 예측 스냅샷이 없습니다. 채팅으로 종목을 직접 열어보세요.
        </p>
      )}

      {boardQ.isError && (
        <p className="px-4 py-6 text-center text-sm text-foreground-muted">
          신호 보드를 불러오지 못했습니다. 채팅으로 종목을 직접 열어보세요.
        </p>
      )}

      {boardQ.data && boardQ.data.rows.length > 0 && (
        <>
          {/* 컬럼 라벨 — lg에서만. 좁은 폭에서는 열이 접혀 라벨이 값과 어긋난다. */}
          {!compact && (
            <div className="hidden lg:flex items-center gap-3 px-4 pb-1.5 text-xs text-foreground-muted">
              <span className="w-5 shrink-0">#</span>
              <span className="w-6 shrink-0" />
              <span className="flex-1">종목</span>
              <span className="w-16 shrink-0" />
              <span className="w-24 shrink-0 text-right">현재가</span>
              <span className="hidden xl:block w-24 shrink-0 text-right">등락액</span>
              <span className="w-[72px] shrink-0 text-right">등락률</span>
              <span className="hidden xl:block w-24 shrink-0 text-right">거래대금</span>
              <span className="w-[104px] shrink-0 text-center">신호</span>
              <span className="w-20 shrink-0 text-right">평소 대비</span>
            </div>
          )}

          <ul className="flex flex-col border-t border-border">
            {/* 순위는 필터와 무관하게 전체 신호순 위치를 유지한다 — "상승만 보기"에서도 3위는 3위다 */}
            {filtered.map((row) => (
              <BoardRow
                key={row.ticker}
                row={row}
                rank={rows.indexOf(row) + 1}
                compact={compact}
                active={row.ticker === selected}
                onSelect={onSelect}
              />
            ))}
          </ul>
          {filtered.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-foreground-muted">
              {filter === "UP" ? "상승" : "하락"} 신호인 종목이 지금은 없어요. 전체를 눌러 다른
              신호를 둘러보세요.
            </p>
          )}

          {!compact && (
            <p className="px-4 py-3 text-xs text-foreground-muted leading-relaxed">
              매수 추천 순위가 아니라 지표 신호가 뚜렷한 순서입니다. &lsquo;평소 대비&rsquo;는 과거 같은
              신호에서의 상승 비율과 평소 상승률의 차이로, 과거 통계이며 미래를 보장하지 않습니다. 가격은
              최근 수집 종가라 실시간이 아닙니다.
            </p>
          )}
        </>
      )}
    </div>
  );
}
