"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { QuarterStat } from "@/lib/types";

export const formatQuarter = (yq: number) => `${String(yq).slice(2, 4)}년 ${String(yq).slice(4)}Q`;

// 원화 축약 — 상권 매출은 억 단위가 일반적
export const formatWon = (v: number) => {
  const abs = Math.abs(v);
  if (abs >= 1e8) return `${(v / 1e8).toFixed(1)}억`;
  if (abs >= 1e4) return `${Math.round(v / 1e4).toLocaleString("ko-KR")}만`;
  return v.toLocaleString("ko-KR");
};

export default function SalesTrendChart({ series }: { series: QuarterStat[] }) {
  const points = series
    .filter((q) => q.monthlySales !== null)
    .map((q) => ({ quarter: formatQuarter(q.yearQuarter), sales: q.monthlySales as number }));

  if (points.length === 0) {
    return <p className="text-sm text-foreground-muted">매출 데이터가 없습니다.</p>;
  }
  // 분기 1개뿐이면 라인 대신 단일 스탯으로 열화 렌더
  if (points.length === 1) {
    return (
      <div className="bg-surface border border-border rounded-lg px-3 py-2.5">
        <div className="text-xs text-foreground-muted">{points[0].quarter} 월 매출 (추정)</div>
        <div className="text-base font-bold mt-0.5">{formatWon(points[0].sales)}원</div>
      </div>
    );
  }

  return (
    <div className="h-40">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#EBE8DF" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="quarter"
            tick={{ fontSize: 10, fill: "#6B7280" }}
            axisLine={{ stroke: "#EBE8DF" }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={formatWon}
            tick={{ fontSize: 10, fill: "#6B7280" }}
            axisLine={false}
            tickLine={false}
            width={44}
          />
          <Tooltip
            formatter={(v) => [`${formatWon(Number(v))}원`, "월 매출"]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #EBE8DF" }}
          />
          <Line
            type="monotone"
            dataKey="sales"
            stroke="#991B1B"
            strokeWidth={2}
            dot={{ r: 3, fill: "#991B1B" }}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
