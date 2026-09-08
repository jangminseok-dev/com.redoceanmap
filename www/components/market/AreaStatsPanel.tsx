"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, ChevronDown, Compass, Gauge, Store, TrendingUp, Users } from "lucide-react";
import { fetchAreaStats } from "@/lib/api";
import type { QuarterStat } from "@/lib/types";
import AreaScoreCard from "./AreaScoreCard";
import AreaFitnessCard from "./AreaFitnessCard";
import SalesTrendChart from "./SalesTrendChart";
import PopulationCharts from "./PopulationCharts";
import StorePanel from "./StorePanel";

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof TrendingUp;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="flex items-center gap-1.5 text-xs font-semibold text-foreground-muted uppercase tracking-wide mb-2">
        <Icon size={13} strokeWidth={2} />
        {title}
      </h3>
      {children}
    </section>
  );
}

// 상권 자료 패널 — ?trdar 를 키로 원시 수치 API를 조회해 차트를 그린다
export default function AreaStatsPanel({
  trdarCode,
  serviceCode,
}: {
  trdarCode: string;
  serviceCode?: string;
}) {
  // REACT_RULES 패턴 B — 조회 축은 단일 객체 하나로 둔다(뒤에 필터가 더 붙는다)
  const [view, setView] = useState<{ quarters: 4 | 8 | 20 }>({ quarters: 8 });
  const { data, isLoading, isError } = useQuery({
    queryKey: ["area-stats", trdarCode, serviceCode, view.quarters],
    queryFn: () => fetchAreaStats(trdarCode, serviceCode, view.quarters),
    enabled: !!trdarCode,
  });

  if (!trdarCode) {
    return (
      <p className="p-4 text-sm text-foreground-muted">
        지도에서 상권을 선택하거나 채팅으로 추천받으면 통계가 표시됩니다.
      </p>
    );
  }
  if (isLoading) {
    return (
      <div className="p-4 flex flex-col gap-3">
        <div className="skeleton h-6 w-2/3 rounded-md" />
        <div className="skeleton h-40 rounded-xl" />
        <div className="skeleton h-32 rounded-xl" />
        <div className="skeleton h-24 rounded-xl" />
      </div>
    );
  }
  if (isError || !data) {
    return <p className="p-4 text-sm text-foreground-muted">상권 통계를 불러오지 못했습니다.</p>;
  }

  return (
    <div className="p-4 flex flex-col gap-5">
      <div>
        <p className="text-xs text-foreground-muted">{data.districtName}</p>
        <h2 className="text-base font-semibold mt-0.5">{data.trdarName}</h2>
        {data.serviceName && (
          <p className="text-xs text-foreground-muted mt-1">
            기준 업종 <span className="font-medium text-foreground">{data.serviceName}</span>
            {" · "}서울시 상권분석서비스
          </p>
        )}
      </div>

      {/* 20분기를 쌓아두고 4분기만 보던 것을 연다 — 8분기면 YoY 짝이 4쌍 생긴다 */}
      <div className="flex items-center gap-1 px-1">
        <span className="text-xs text-foreground-muted mr-1">구간</span>
        {([4, 8, 20] as const).map((q) => (
          <button
            key={q}
            onClick={() => setView({ quarters: q })}
            className={`px-2 py-0.5 rounded-full text-xs font-medium transition-colors ${
              view.quarters === q
                ? "bg-brand/10 text-brand"
                : "text-foreground-muted hover:text-foreground"
            }`}
          >
            {q}분기
          </button>
        ))}
      </div>

      {/* I-6 2단계 노출 — 핵심(요약 타일 + 종합점수)을 먼저 주고, 나머지 지표는 접는다.
          365의 간단/상세 UX: 초보는 1단계에서 결론이 서고, 깊이 볼 사람만 연다 */}
      <CoreTiles series={data.series} />

      <Section icon={Gauge} title="상권 종합점수">
        <AreaScoreCard trdarCode={trdarCode} quarters={view.quarters} />
      </Section>

      {/* 입지 적합도 — 업종은 선택값 우선, 없으면 stats가 고른 최대 매출 업종(null이면 생략) */}
      {(serviceCode ?? data.serviceCode) && (
        <Section icon={Compass} title={`입지 적합도 · ${data.serviceName ?? ""}`}>
          <AreaFitnessCard trdarCode={trdarCode} serviceCode={(serviceCode ?? data.serviceCode) as string} />
        </Section>
      )}

      <details className="group">
        <summary className="flex cursor-pointer list-none select-none items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-foreground-muted">
          <ChevronDown size={13} className="transition-transform group-open:rotate-180" />
          전체 지표 더 보기
        </summary>
        <div className="mt-4 flex flex-col gap-5">
          <Section icon={TrendingUp} title="분기 매출 추이">
            <SalesTrendChart series={data.series} />
          </Section>

          <Section icon={Users} title="유동인구 (최신 분기)">
            <PopulationCharts latest={data.latest} />
          </Section>

          <Section icon={Store} title="점포 현황">
            <StorePanel series={data.series} latest={data.latest} />
          </Section>

          <Section icon={BarChart3} title="유동인구 추이">
            <FloatingTrend series={data.series} />
          </Section>
        </div>
      </details>

      {/* I-9 — 못 하는 것을 먼저 말한다(정확도 경쟁 대신 한계 명시, ROADMAP).
          창업자가 결국 물을 축(임대료)이 비어 있음을 숨기지 않는다 */}
      <p className="border-t border-border pt-3 text-xs text-foreground-muted leading-relaxed">
        이 자료가 다루지 않는 것: 임대료·권리금(공공 API가 없어 미제공), 개별 매장 매출(카드사
        실결제가 아닌 서울시 추정 집계예요). 데이터는 분기 단위라 최신 분기와 지금 사이에
        1~2분기 시차가 있어요.
      </p>
    </div>
  );
}

// 핵심 요약 3타일 — 매출 흐름·폐업률·하루 방문(테스트 판정의 "핵심 4개" 중 점수 카드 제외분).
// 값이 없는 축은 "—"로 정직하게 비운다(추정치로 채우지 않는다).
function CoreTiles({ series }: { series: QuarterStat[] }) {
  const withSales = series.filter((q) => q.monthlySales !== null);
  const cur = withSales.length >= 1 ? withSales[withSales.length - 1] : null;
  const prev = withSales.length >= 2 ? withSales[withSales.length - 2] : null;
  const qoq =
    cur && prev && prev.monthlySales
      ? ((cur.monthlySales! - prev.monthlySales!) / prev.monthlySales!) * 100
      : null;
  const closure = [...series].reverse().find((q) => q.closureRate !== null) ?? null;
  const foot = [...series].reverse().find((q) => q.totalFloatingPop !== null) ?? null;

  return (
    <div className="grid grid-cols-3 gap-2">
      <CoreTile
        label="매출 (전분기 대비)"
        value={qoq !== null ? `${qoq > 0 ? "+" : ""}${qoq.toFixed(1)}%` : "—"}
        tone={qoq === null ? "" : qoq > 0 ? "text-up" : qoq < 0 ? "text-down" : ""}
      />
      <CoreTile
        label="분기 폐업률"
        value={closure?.closureRate !== null && closure ? `${closure.closureRate}%` : "—"}
        caption={closure?.closureCount != null ? `${closure.closureCount}곳 폐업` : undefined}
      />
      <CoreTile
        label="하루 평균 방문"
        value={
          foot?.totalFloatingPop != null
            ? `${Math.round(foot.totalFloatingPop / 91).toLocaleString("ko-KR")}명`
            : "—"
        }
      />
    </div>
  );
}

function CoreTile({ label, value, caption, tone = "" }: {
  label: string;
  value: string;
  caption?: string;
  tone?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface px-2.5 py-2">
      <p className="text-xs text-foreground-muted">{label}</p>
      <p className={`mt-0.5 text-sm font-semibold tabular-nums ${tone}`}>{value}</p>
      {caption && <p className="text-xs text-foreground-muted">{caption}</p>}
    </div>
  );
}

function FloatingTrend({ series }: { series: QuarterStat[] }) {
  const points = series.filter((q) => q.totalFloatingPop !== null);
  if (points.length === 0) {
    return <p className="text-sm text-foreground-muted">데이터가 없습니다.</p>;
  }
  const max = Math.max(...points.map((q) => q.totalFloatingPop as number));
  return (
    <div className="flex items-end gap-2 h-20">
      {points.map((q) => (
        // h-full 필수 — 부모가 items-end라 컬럼 높이가 content 기준이 되고,
        // 그러면 막대의 height:%가 0으로 무너져 차트가 통째로 빈 화면이 된다.
        <div key={q.yearQuarter} className="flex-1 h-full flex flex-col justify-end items-center gap-1">
          <div
            className="w-full max-w-10 bg-brand/70 rounded-t"
            style={{ height: `${Math.max(8, ((q.totalFloatingPop as number) / max) * 100)}%` }}
            title={`${(q.totalFloatingPop as number).toLocaleString("ko-KR")}명`}
          />
          <span className="text-xs text-foreground-muted">
            {String(q.yearQuarter).slice(4)}Q
          </span>
        </div>
      ))}
    </div>
  );
}
