"use client";

import { useQuery } from "@tanstack/react-query";
import { FlaskConical, MapPin, Rows3 } from "lucide-react";
import { fetchAdminMarketBacktest } from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import Empty from "@/components/admin/Empty";
import Kpi from "@/components/admin/Kpi";

const COMPONENT_LABEL: Record<string, string> = {
  sales_growth: "매출 성장",
  floating_growth: "유동인구 성장",
  store_health: "개폐업 건강도",
  persistence: "영업 지속성",
};

const signedP = (v: number | null, digits = 2, unit = "%p") =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}${unit}`;

const pct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);

const quarterLabel = (yq: number) => `${String(yq).slice(0, 4)}년 ${String(yq).slice(4)}분기`;

export default function MarketBacktestPage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-market-backtest"],
    queryFn: fetchAdminMarketBacktest,
  });

  const report = data?.report ?? null;

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight">상권 검증</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          상권 점수 워크포워드 백테스트 — 분기 t 등급이 t+1 실제 결과(상대 유동인구 QoQ)를 갈랐는지
        </p>
      </div>

      {isPending && <BlockSkeleton rows={6} />}
      {isError && (
        <section className="rounded-2xl bg-surface border border-border">
          <Empty msg="상권 백테스트 리포트를 불러오지 못했습니다." />
        </section>
      )}
      {!isPending && !isError && report === null && (
        <section className="rounded-2xl bg-surface border border-border">
          <Empty msg="아직 백테스트 실행 이력이 없습니다. scripts/backtest_area_score.py를 실행해 주세요." />
        </section>
      )}

      {report && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <Kpi icon={Rows3} label="관측 수" value={report.n_observations.toLocaleString()} sub="(상권 × 분기)" />
            <Kpi icon={MapPin} label="상권 수" value={report.n_areas.toLocaleString()} />
            <Kpi
              icon={FlaskConical}
              label="평가 분기"
              value={String(report.base_quarters.length)}
              sub={
                report.base_quarters.length > 0
                  ? `${quarterLabel(report.base_quarters[0])} ~ ${quarterLabel(report.base_quarters[report.base_quarters.length - 1])}`
                  : undefined
              }
            />
            <Kpi label="마지막 실행" value={report.ran_at.slice(0, 10)} sub={report.ran_at.slice(11, 16)} />
          </div>

          <section className="rounded-2xl bg-surface border border-border overflow-hidden">
            <div className="px-5 py-3 border-b border-border">
              <h2 className="text-sm font-semibold">등급별 다음 분기 실제 결과</h2>
              <p className="mt-0.5 text-xs text-foreground-muted">
                결과 = t+1 유동인구 QoQ(상권 − 서울, %p) · 매출 QoQ는 2025년 표본만(저표본 참고치)
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-foreground-muted border-b border-border bg-background/60">
                    <th className="font-medium px-5 py-2.5">등급</th>
                    <th className="font-medium px-4 py-2.5 text-right">관측</th>
                    <th className="font-medium px-4 py-2.5 text-right">평균</th>
                    <th className="font-medium px-4 py-2.5 text-right">중앙값</th>
                    <th className="font-medium px-4 py-2.5 text-right">양(+) 비율</th>
                    <th className="font-medium px-5 py-2.5 text-right">평균 매출 QoQ</th>
                  </tr>
                </thead>
                <tbody>
                  {report.grade_outcomes.map((g) => (
                    <tr key={g.grade} className="border-b border-border last:border-0">
                      <td className="px-5 py-3 font-medium">{g.grade}</td>
                      <td className="px-4 py-3 text-right text-foreground-muted tabular-nums">{g.n.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{signedP(g.avg_rel_floating_qoq)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-foreground-muted">{signedP(g.median_rel_floating_qoq)}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{pct(g.positive_share)}</td>
                      <td className="px-5 py-3 text-right tabular-nums text-foreground-muted">
                        {signedP(g.avg_sales_qoq, 2, "%")}
                        {g.sales_n > 0 && (
                          <span className="ml-1.5 inline-flex px-1.5 py-0.5 rounded-full text-xs bg-amber-50 text-amber-700">
                            n={g.sales_n.toLocaleString()}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl bg-surface border border-border overflow-hidden">
            <div className="px-5 py-3 border-b border-border">
              <h2 className="text-sm font-semibold">컴포넌트별 예측력</h2>
              <p className="mt-0.5 text-xs text-foreground-muted">
                Spearman ρ = 컴포넌트 점수(t)와 결과(t+1)의 순위 상관 · 스프레드 = 점수 상위 20% − 하위 20% 결과 차이
              </p>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-foreground-muted border-b border-border bg-background/60">
                  <th className="font-medium px-5 py-2.5">컴포넌트</th>
                  <th className="font-medium px-4 py-2.5 text-right">표본</th>
                  <th className="font-medium px-4 py-2.5 text-right">Spearman ρ</th>
                  <th className="font-medium px-5 py-2.5 text-right">5분위 스프레드</th>
                </tr>
              </thead>
              <tbody>
                {report.component_predictiveness.map((c) => (
                  <tr key={c.key} className="border-b border-border last:border-0">
                    <td className="px-5 py-3 font-medium">{COMPONENT_LABEL[c.key] ?? c.key}</td>
                    <td className="px-4 py-3 text-right text-foreground-muted tabular-nums">{c.n.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{c.spearman == null ? "—" : c.spearman.toFixed(3)}</td>
                    <td className="px-5 py-3 text-right tabular-nums">{signedP(c.top_minus_bottom_quintile)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
