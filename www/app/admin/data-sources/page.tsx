"use client";

import { useQuery } from "@tanstack/react-query";
import { Database } from "lucide-react";
import { fetchAdminDataSources, formatAge, formatLatestLabel } from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import Empty from "@/components/admin/Empty";

// 데이터셋 key → 부가 설명 (수집 경로는 백엔드/cron 소관 — 어드민은 열람만)
const NOTES: Record<string, string> = {
  trade_area: "서울 열린데이터광장 · 상권 차원",
  estimated_sales: "서울 열린데이터광장 · 분기 팩트",
  store: "서울 열린데이터광장 · 분기 팩트",
  floating_population: "서울 열린데이터광장 · 분기 팩트",
  market_news: "Google News RSS · 일 단위 수집",
  business_permits: "서울 열린데이터광장 인허가 · 주 1회",
  recommendations: "AI 추천 파이프라인 산출물",
  price_bars: "yfinance OHLCV · 자동 수집",
  news_articles: "Google News RSS · 30분 주기",
  news_labels: "EXAONE 7.8B 라벨링 · 야간 배치",
  fundamental_snapshots: "yfinance + DART · 주 1회",
  forecast_snapshots: "예측 동결 스냅샷 · 매일 14:00",
};

// 신선도 배지 — 판정은 백엔드(admin 도메인 서비스)가 하고 여기선 표시만 한다.
const FRESHNESS: Record<string, { label: string; cls: string }> = {
  fresh: { label: "정상", cls: "bg-emerald-50 text-emerald-700" },
  late: { label: "지연", cls: "bg-amber-50 text-amber-700" },
  stale: { label: "정지", cls: "bg-rose-50 text-rose-700" },
  unknown: { label: "수집 이력 없음", cls: "bg-foreground/5 text-foreground-muted" },
  unscheduled: { label: "정적 데이터", cls: "bg-foreground/5 text-foreground-muted" },
};

export default function DataSourcesPage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-data-sources"],
    queryFn: fetchAdminDataSources,
  });

  const datasets = data?.datasets ?? [];

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight">데이터 소스</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          데이터셋별 적재 현황 (수집은 스크립트·자동화 파이프라인이 수행)
        </p>
      </div>

      {isPending && <BlockSkeleton rows={4} />}
      {isError && <Empty msg="적재 현황을 불러오지 못했습니다." />}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {datasets.map((d) => (
          <div key={d.key} className="rounded-2xl bg-surface border border-border p-5">
            <div className="flex items-start gap-3">
              <span className="grid place-items-center w-10 h-10 rounded-xl bg-brand/10 text-brand shrink-0">
                <Database size={18} strokeWidth={1.9} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold truncate">{d.name}</p>
                <p className="text-xs text-foreground-muted">{NOTES[d.key] ?? d.key}</p>
              </div>
              <span
                className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium shrink-0 ${
                  (FRESHNESS[d.freshness] ?? FRESHNESS.unknown).cls
                }`}
              >
                {(FRESHNESS[d.freshness] ?? FRESHNESS.unknown).label}
              </span>
            </div>

            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-foreground-muted">레코드</span>
              <span className="font-medium tabular-nums">{d.row_count.toLocaleString()} 행</span>
            </div>
            <div className="mt-2 flex items-center justify-between text-sm">
              <span className="text-foreground-muted">기대 주기</span>
              <span className="font-medium">{d.expected ?? "주기 없음"}</span>
            </div>
            <div className="mt-2 flex items-center justify-between text-sm">
              <span className="text-foreground-muted">
                {d.expected ? "최신 수집" : "최신 시점"}
              </span>
              <span className="font-medium tabular-nums">
                {d.expected ? formatAge(d.age_seconds) : formatLatestLabel(d.latest_label)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
