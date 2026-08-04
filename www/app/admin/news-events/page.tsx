"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Newspaper } from "lucide-react";
import { fetchAdminNewsEventStudy, type AdminEventBucket } from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import Empty from "@/components/admin/Empty";
import Kpi from "@/components/admin/Kpi";

const signed = (v: number, unit = "%") => `${v > 0 ? "+" : ""}${v.toFixed(2)}${unit}`;
const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

export default function NewsEventStudyPage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-news-event-study"],
    queryFn: fetchAdminNewsEventStudy,
  });

  const report = data?.report ?? null;

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight">뉴스 이벤트 연구</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          LLM 라벨(이벤트 유형·감성)이 실제 주가 반응과 관계가 있는지 —{" "}
          <span className="font-medium text-foreground">news_labels × price_bars</span> 조인.
          라벨러의 쓸모를 재는 연구이지 투자 정보가 아닙니다.
        </p>
      </div>

      {isPending && <BlockSkeleton rows={6} />}
      {isError && (
        <section className="rounded-2xl bg-surface border border-border">
          <Empty msg="연구 리포트를 불러오지 못했습니다." />
        </section>
      )}
      {!isPending && !isError && report === null && (
        <section className="rounded-2xl bg-surface border border-border">
          <Empty msg="아직 실행 이력이 없습니다. scripts/study_news_events.py를 실행해 주세요." />
        </section>
      )}

      {report && (
        <>
          {/* 표본 경고를 KPI보다 위에 둔다 — 수치를 먼저 읽고 경고를 나중에 보면 늦다 */}
          {report.warnings.length > 0 && (
            <section className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3">
              <div className="flex items-start gap-2">
                <AlertTriangle size={16} className="text-amber-700 mt-0.5 shrink-0" />
                <div className="text-sm text-amber-900 space-y-1">
                  {report.warnings.map((w) => (
                    <p key={w}>{w}</p>
                  ))}
                  <p className="text-xs opacity-80">
                    이 수치는 검증된 결과가 아닙니다. 사용자 화면에 노출하지 않습니다.
                  </p>
                </div>
              </div>
            </section>
          )}

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Kpi icon={Newspaper} label="표본" value={report.total.toLocaleString()} />
            <Kpi icon={Newspaper} label="지평" value={`${report.horizon_days}일`} />
            <Kpi
              icon={Newspaper}
              label="기준선(전체 평균)"
              value={signed(report.baseline_pct)}
            />
            <Kpi
              icon={Newspaper}
              label="최다 주 비중"
              value={pct(report.top_week_share)}
            />
          </div>

          <BucketTable
            title="이벤트 유형별"
            hint="초과 = 평균 − 기준선. 절대 수익률은 표본 기간의 시장 방향을 그대로 반영하므로 초과분으로 읽습니다."
            rows={report.by_event}
          />
          <BucketTable title="감성대별" hint="라벨의 방향성이 실제 반응과 맞는지" rows={report.by_sentiment} />

          <p className="text-xs text-foreground-muted">
            실행 {new Date(report.ran_at).toLocaleString("ko-KR")} · 지평 {report.horizon_days}일
          </p>
        </>
      )}
    </div>
  );
}

function BucketTable({
  title,
  hint,
  rows,
}: {
  title: string;
  hint: string;
  rows: AdminEventBucket[];
}) {
  if (!rows.length) return null;
  return (
    <section className="rounded-2xl bg-surface border border-border p-4">
      <h2 className="font-semibold">{title}</h2>
      <p className="text-xs text-foreground-muted mt-0.5">{hint}</p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-foreground-muted border-b border-border">
              <th className="text-left font-normal py-1.5">구분</th>
              <th className="text-right font-normal py-1.5">표본</th>
              <th className="text-right font-normal py-1.5">평균</th>
              <th className="text-right font-normal py-1.5">초과</th>
              <th className="text-right font-normal py-1.5">양(+) 비율</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.key} className="border-b border-border/60 last:border-0">
                <td className="py-1.5">
                  {b.key}
                  {!b.reliable && (
                    <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded-full bg-foreground/5 text-foreground-muted">
                      표본 부족
                    </span>
                  )}
                </td>
                <td className="text-right tabular-nums py-1.5">{b.n.toLocaleString()}</td>
                <td className="text-right tabular-nums py-1.5 text-foreground-muted">
                  {signed(b.avg_return_pct)}
                </td>
                <td
                  className={`text-right tabular-nums py-1.5 font-semibold ${
                    b.excess_pct > 0 ? "text-emerald-600" : b.excess_pct < 0 ? "text-rose-600" : ""
                  }`}
                >
                  {signed(b.excess_pct, "%p")}
                </td>
                <td className="text-right tabular-nums py-1.5">{pct(b.positive_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
