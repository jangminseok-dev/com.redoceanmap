"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Store, Users, Sparkles, Database } from "lucide-react";
import { fetchAdminDashboard, formatLatestLabel, type AdminMonthCount } from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import Empty from "@/components/admin/Empty";
import Kpi from "@/components/admin/Kpi";

/* ────────────────────────── 작은 차트 ────────────────────────── */

function AreaTrend({ monthly }: { monthly: AdminMonthCount[] }) {
  if (monthly.length < 2) {
    return (
      <p className="h-44 grid place-items-center text-sm text-foreground-muted">
        추이를 그리기에 데이터가 아직 부족합니다.
      </p>
    );
  }
  const values = monthly.map((m) => m.count);
  const w = 560;
  const h = 180;
  const pad = 8;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const xs = (i: number) => pad + (i * (w - pad * 2)) / (values.length - 1);
  const ys = (v: number) => h - pad - ((v - min) / span) * (h - pad * 2);
  const line = values.map((v, i) => `${i === 0 ? "M" : "L"}${xs(i)},${ys(v)}`).join(" ");
  const fill = `${line} L${xs(values.length - 1)},${h} L${xs(0)},${h} Z`;

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-44" preserveAspectRatio="none">
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#991B1B" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#991B1B" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={fill} fill="url(#trendFill)" />
        <path d={line} fill="none" stroke="#991B1B" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
        {values.map((v, i) => (
          <circle key={i} cx={xs(i)} cy={ys(v)} r="2.5" fill="#991B1B" />
        ))}
      </svg>
      <div className="mt-2 flex justify-between text-[11px] text-foreground-muted">
        {monthly.map((m) => (
          <span key={m.month}>{Number(m.month.slice(5))}월</span>
        ))}
      </div>
    </div>
  );
}

/* ────────────────────────── 페이지 ────────────────────────── */

export default function AdminDashboard() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: fetchAdminDashboard,
  });

  if (isPending)
    return (
      <div className="max-w-7xl mx-auto">
        <BlockSkeleton rows={6} />
      </div>
    );
  if (isError || !data) return <Empty msg="대시보드를 불러오지 못했습니다." />;

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      {/* 헤더 */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight">대시보드</h1>
        <p className="mt-1 text-sm text-foreground-muted">서울 상권 분석 서비스 현황</p>
      </div>

      {/* KPI 카드 — 모바일 2열 → lg 4열 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <Kpi icon={Store} label="등록 상권" value={data.area_count.toLocaleString()} />
        <Kpi
          icon={Users}
          label="전체 회원"
          value={data.member_total.toLocaleString()}
          sub={`이번 달 신규 ${data.member_new_this_month.toLocaleString()}`}
        />
        <Kpi
          icon={Sparkles}
          label="오늘 추천"
          value={data.recommendation_today.toLocaleString()}
          sub={`누적 ${data.recommendation_total.toLocaleString()}`}
        />
        <Kpi icon={Database} label="최신 데이터 분기" value={formatLatestLabel(data.latest_quarter)} />
      </div>

      {/* 메인 그리드 — 모바일 1열 → lg 3열(2:1) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-5">
        {/* 좌측 2/3 */}
        <div className="lg:col-span-2 space-y-4 sm:space-y-5">
          {/* 추천 추이 */}
          <section className="rounded-2xl bg-surface border border-border p-4 sm:p-5">
            <h2 className="font-semibold">추천 추이</h2>
            <p className="text-xs text-foreground-muted mt-0.5">최근 12개월 AI 추천 건수</p>
            <div className="mt-4">
              <AreaTrend monthly={data.monthly} />
            </div>
          </section>

          {/* 인기 업종 분포 */}
          <section className="rounded-2xl bg-surface border border-border p-4 sm:p-5">
            <h2 className="font-semibold">인기 업종 분포</h2>
            <p className="text-xs text-foreground-muted mt-0.5">추천된 상권의 주력 업종</p>
            <div className="mt-4 space-y-3">
              {data.top_categories.length === 0 && (
                <p className="text-sm text-foreground-muted">아직 추천 기록이 없습니다.</p>
              )}
              {data.top_categories.map((c) => {
                const pct = data.recommendation_total
                  ? Math.round((c.count / data.recommendation_total) * 100)
                  : 0;
                return (
                  <div key={c.category}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-foreground/80">{c.category}</span>
                      <span className="font-medium tabular-nums">{pct}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-brand/10 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-brand"
                        style={{ width: `${Math.min(pct * 2.6, 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        {/* 우측 1/3 — 최근 추천 */}
        <section className="rounded-2xl bg-surface border border-border p-4 sm:p-5 h-fit">
          <h2 className="font-semibold">최근 추천</h2>
          <ol className="mt-4 space-y-4">
            {data.recent.length === 0 && (
              <p className="text-sm text-foreground-muted">아직 추천 기록이 없습니다.</p>
            )}
            {data.recent.map((r) => (
              <li key={r.id}>
                <Link
                  href={`/market?trdar=${r.trdar_code}`}
                  className="relative flex gap-3 group"
                  title="서비스 지도에서 열기"
                >
                  <span className="grid place-items-center w-8 h-8 rounded-full bg-brand/10 text-brand shrink-0">
                    <Sparkles size={14} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm leading-snug font-medium group-hover:text-brand transition-colors">
                      {r.trdar_name} <span className="font-normal text-foreground-muted">· {r.category}</span>
                    </p>
                    <p className="text-xs text-foreground-muted mt-0.5">
                      {r.district_name} · {r.created_at.slice(0, 10)}
                    </p>
                  </div>
                </Link>
              </li>
            ))}
          </ol>

          {/* 분석 질문 수요 — 워치리스트 편입 스크립트만 보던 지표.
              "무엇을 수집할지"를 사용자 질문이 정한다는 걸 운영자도 봐야 한다. */}
          <h2 className="font-semibold mt-6 pt-5 border-t border-border">질문 많은 종목</h2>
          <p className="text-xs text-foreground-muted mt-0.5">최근 30일 · 워치리스트 자동 편입 후보</p>
          <ol className="mt-3 space-y-2">
            {data.stock_demands.length === 0 && (
              <p className="text-sm text-foreground-muted">최근 30일 분석 질문이 없습니다.</p>
            )}
            {data.stock_demands.map((d, i) => (
              <li key={d.ticker} className="flex items-center gap-2.5 text-sm">
                <span className="w-4 text-xs text-foreground-muted tabular-nums">{i + 1}</span>
                <span className="font-medium">{d.ticker}</span>
                <span className="ml-auto text-xs text-foreground-muted tabular-nums">
                  {d.ask_count}회 · {d.last_asked_at.slice(5, 10)}
                </span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}

