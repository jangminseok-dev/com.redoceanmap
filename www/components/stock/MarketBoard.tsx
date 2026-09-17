"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchStockBoard } from "@/lib/api";
import { formatPrice, formatTurnover } from "@/lib/currency";
import SymbolMark from "@/components/common/SymbolMark";
import type { RiskStat, StockBoardRow } from "@/lib/types";

// 좌측 목록의 위험 필터(2026-09-17 재설계). 방향(오를까·내릴까) 신호는 겹침 보정 재검증에서 최근 5년 평소와
// 구별되지 않아 보드에서 내렸다. 같은 기준으로 검증 구간(2021~)에서도 유지된 변동성·낙폭 위험만 주 신호로 둔다.
const FILTERS = [
  { key: "ALL", label: "전체" },
  { key: "CAUTION", label: "변동성·낙폭 주의" },
  { key: "CALM", label: "안정 구간" },
] as const;
type FilterKey = (typeof FILTERS)[number]["key"];

const isCaution = (r: StockBoardRow) => r.drawdown_risk === "HIGH" || r.vol_state === "HIGH";
const isCalm = (r: StockBoardRow) => r.vol_state === "LOW";

// 행의 위험 배지 — 낙폭 위험이 변동성보다 먼저(더 구체적인 경고). 판정 불가는 봉이 모자란 종목.
// 색은 가격 방향색(up 빨강·down 파랑)을 쓰지 않는다 — 위험 배지가 "상승/하락"으로 읽힌다.
function riskMeta(r: StockBoardRow) {
  if (r.drawdown_risk === "HIGH")
    return { label: "낙폭 위험 높음", stat: "drop_high", className: "text-destructive bg-destructive/10 border-destructive/30" };
  if (r.vol_state === "HIGH")
    return { label: "변동성 확대 주의", stat: "vol_high", className: "text-destructive bg-surface border-destructive/20" };
  if (r.drawdown_risk === "LOW")
    return { label: "안정 구간", stat: "drop_low", className: "text-brand bg-surface border-brand/30" };
  if (r.vol_state === "LOW")
    return { label: "변동성 낮음", stat: "vol_low", className: "text-brand bg-surface border-brand/20" };
  if (r.vol_state === "NORMAL")
    return { label: "보통", stat: null, className: "text-foreground-muted bg-surface border-border" };
  return { label: "판정 불가", stat: null, className: "text-foreground-muted bg-surface border-border" };
}

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
  stats,
}: {
  row: StockBoardRow;
  stats: Partial<Record<RiskStat["key"], RiskStat>>;
  rank: number;
  compact: boolean; // 320px 좌측 컬럼 — 스파크라인·신호·평소대비를 접는다
  active: boolean;
  onSelect: (symbol: string) => void;
}) {
  const risk = riskMeta(row);
  const stat = risk.stat ? stats[risk.stat as RiskStat["key"]] : undefined;
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

            {/* 위험 배지 + 현재 변동성 위치 — 방향이 아니라 앞으로 20거래일 얼마나 흔들릴지다 */}
            <span
              className="hidden lg:flex w-[128px] shrink-0 flex-col items-center gap-0.5"
              title={
                row.rv20 != null && row.rv_percentile != null
                  ? `최근 20일 변동성 연 ${Math.round(row.rv20 * 100)}% — 이 종목의 지난 1년 중 ${Math.round(row.rv_percentile * 100)}% 위치예요.`
                    + (row.trend === "DOWN" ? " 가격이 200일 이동평균 아래예요." : row.trend === "UP" ? " 50·200일 이동평균 위 상승 흐름이에요." : "")
                  : "위험 신호를 판정할 일봉(약 1년치)이 아직 모자라요."
              }
            >
              <span className={`inline-flex items-center justify-center px-2 py-0.5 rounded-full border text-xs font-medium ${risk.className}`}>
                {risk.label}
              </span>
              {row.rv20 != null && row.rv_percentile != null && (
                <span className="text-[11px] tabular-nums text-foreground-muted">
                  변동성 {Math.round(row.rv20 * 100)}% · 1년 중 {Math.round(row.rv_percentile * 100)}%
                </span>
              )}
            </span>

            {/* 이 상태의 검증 실측 — 검증 구간(2021~)에서 평소와 갈라진 신호만 수치를 싣는다 */}
            <span
              className="hidden lg:flex w-28 shrink-0 flex-col items-end text-xs tabular-nums text-foreground-muted"
              title={stat ? `${stat.label}일 때 ${stat.outcome_label}: ${Math.round((stat.test_rate ?? 0) * 100)}% (평소 ${Math.round((stat.base_rate ?? 0) * 100)}%) — 과거 검증 구간 실측이며 이번 결과를 보장하지 않아요.` : undefined}
            >
              {stat && stat.validated && stat.test_rate != null && stat.base_rate != null ? (
                <>
                  <span>
                    {stat.key.startsWith("vol") ? "변동성 확대" : "-10% 하락"} {Math.round(stat.test_rate * 100)}%
                  </span>
                  <span className="text-[11px]">평소 {Math.round(stat.base_rate * 100)}%</span>
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
  const filtered = filter === "ALL" ? rows : rows.filter(filter === "CAUTION" ? isCaution : isCalm);
  const counts = { caution: rows.filter(isCaution).length, calm: rows.filter(isCalm).length };
  const statList = boardQ.data?.risk_stats ?? [];
  const stats = Object.fromEntries(statList.map((s) => [s.key, s])) as Partial<Record<RiskStat["key"], RiskStat>>;
  const validated = statList.filter((s) => s.validated && s.test_rate != null && s.base_rate != null);

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
        <span className="ml-auto text-xs text-foreground-muted">위험 신호순</span>
      </div>
      {compact && asOf && (
        <p className="px-4 pb-1.5 text-xs text-foreground-muted">
          신호 {day(asOf)} 기준{priceAsOf && ` · 가격 ${day(priceAsOf)} 종가`}
        </p>
      )}

      {/* 신호 요약 — 보드 행을 세어 만든다(새 요청 없음). 표가 길어 위에서 전체 그림이 안 잡히던 자리다.
          "주식 분석" 제목은 뺐다 — 레일에서 주식이 활성이라 어디인지는 이미 알고 있다. */}
      {!compact && rows.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-2 px-4 pt-4 pb-1">
            <SummaryTile label="변동성·낙폭 주의" count={counts.caution} className="text-destructive" />
            <SummaryTile label="안정 구간(변동성 낮음)" count={counts.calm} className="text-brand" />
          </div>
          {/* 신호의 뜻과 검증 실측 — 방향이 아니라 앞으로 20거래일 얼마나 흔들릴지다. 수치는 주간 리포트의 검증 구간 값 */}
          <div className="px-4 pb-1 text-xs text-foreground-muted leading-relaxed">
            <p>
              오를지·내릴지(방향)는 과거 검증에서 평소와 구별되지 않아 보여 드리지 않아요. 대신 검증 구간에서도 맞았던
              위험 신호를 보여 줘요 — 최근 크게 흔들린 종목은 한동안 계속 크게 흔들리는 성질(변동성 군집)이에요.
            </p>
            {validated.length > 0 && (
              <ul className="mt-1 space-y-0.5">
                {validated.map((s) => (
                  <li key={s.key}>
                    · {s.label}: {s.outcome_label} {Math.round((s.test_rate ?? 0) * 100)}% (평소{" "}
                    {Math.round((s.base_rate ?? 0) * 100)}%{s.lift != null && `, ${s.lift.toFixed(1)}배`})
                  </li>
                ))}
                <li className="text-[11px]">
                  검증 구간 {boardQ.data?.risk_test_period ?? "2021~"} · 겹치는 20일 창은 독립 표본으로 세지 않았어요 ·
                  과거 실측이며 이번 결과를 보장하지 않아요
                </li>
              </ul>
            )}
          </div>
        </>
      )}

      <div className="flex flex-wrap items-baseline gap-x-2 px-4 pt-4 pb-2">
        <h3 className="text-base font-semibold">오늘의 위험 신호 보드</h3>
        {!compact && (
          <span className="text-xs text-foreground-muted">
            워치리스트 · 주의가 필요한 순 · 향후 20거래일
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
              <span className="w-[128px] shrink-0 text-center">위험 신호(20일)</span>
              <span className="w-28 shrink-0 text-right">검증 실측</span>
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
                stats={stats}
              />
            ))}
          </ul>
          {filtered.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-foreground-muted">
              지금은 이 조건에 해당하는 종목이 없어요. 전체를 눌러 둘러보세요.
            </p>
          )}

          {!compact && (
            <p className="px-4 py-3 text-xs text-foreground-muted leading-relaxed">
              매수·매도 추천이 아니라 앞으로 20거래일 동안 가격이 얼마나 흔들릴 수 있는지의 위험 신호입니다.
              &lsquo;변동성&rsquo;은 최근 20일 하루 등락폭을 1년 기준으로 환산한 값, &lsquo;1년 중&rsquo;은 이 종목 지난 1년
              안에서의 위치입니다. 검증 실측은 매주 다시 계산하며, 검증 구간에서 성질이 사라지면 수치를 내립니다. 가격은
              최근 수집 종가라 실시간이 아닙니다.
            </p>
          )}
        </>
      )}
    </div>
  );
}
