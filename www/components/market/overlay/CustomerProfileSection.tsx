"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AreaDetail } from "@/lib/types";
import { formatMoney } from "./format";

const AGE_LABELS: [string, string][] = [
  ["age10", "10대"], ["age20", "20대"], ["age30", "30대"],
  ["age40", "40대"], ["age50", "50대"], ["age60Plus", "60+"],
];

export default function CustomerProfileSection({
  salesMix,
}: {
  salesMix: NonNullable<AreaDetail["salesMix"]>;
}) {
  const { male, female } = salesMix.byGender;
  const genderTotal = male + female;
  const malePct = genderTotal > 0 ? Math.round((male / genderTotal) * 100) : null;
  const ageData = AGE_LABELS.map(([key, label]) => ({
    label,
    value: salesMix.byAge[key] ?? 0,
  }));
  // 매출 최다층과 객단가 최고층은 다를 수 있다 — "방문은 20대, 지갑은 40대"
  const topTicket = (() => {
    const counts = salesMix.countByAge;
    if (!counts) return null;
    let best: { label: string; per: number } | null = null;
    for (const [key, label] of AGE_LABELS) {
      const n = counts[key] ?? 0;
      // 표본이 극소한 층이 허위 최고가로 뽑히는 것을 막는다(전체 건수의 5% 미만 제외)
      if (n <= 0 || n < salesMix.monthlyCount * 0.05) continue;
      const per = (salesMix.byAge[key] ?? 0) / n;
      if (!best || per > best.per) best = { label, per };
    }
    return best;
  })();

  return (
    <div className="flex flex-col gap-3">
      {malePct !== null && (
        <div>
          <div className="flex justify-between text-xs text-foreground-muted mb-1">
            <span>남성 {malePct}%</span>
            <span>여성 {100 - malePct}%</span>
          </div>
          <div className="flex h-2 rounded-full overflow-hidden bg-border">
            <div className="bg-down/70" style={{ width: `${malePct}%` }} />
            <div className="bg-up/70" style={{ width: `${100 - malePct}%` }} />
          </div>
        </div>
      )}
      <div>
        <p className="text-xs text-foreground-muted mb-1.5">
          연령대별 매출
          {topTicket && (
            <span className="ml-1.5 opacity-80">
              · 객단가 최고 {topTicket.label} {(topTicket.per / 10000).toFixed(1)}만원
            </span>
          )}
        </p>
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={ageData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: "var(--foreground-muted)" }}
                axisLine={{ stroke: "var(--border)" }}
                tickLine={false}
              />
              <YAxis
                tickFormatter={formatMoney}
                tick={{ fontSize: 10, fill: "var(--foreground-muted)" }}
                axisLine={false}
                tickLine={false}
                width={44}
              />
              <Tooltip
                formatter={(v) => [formatMoney(Number(v)), "매출"]}
                contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)", backgroundColor: "var(--surface)", color: "var(--foreground)" }}
                cursor={{ fill: "rgb(var(--heat-rgb) / 0.06)" }}
              />
              <Bar dataKey="value" fill="var(--brand)" radius={[3, 3, 0, 0]} maxBarSize={28} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
