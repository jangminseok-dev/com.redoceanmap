"use client";

import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AreaDetail } from "@/lib/types";
import { formatMoney } from "./format";

const TOP_N = 5;

export default function SpendingSection({
  spending,
}: {
  spending: NonNullable<AreaDetail["spending"]>;
}) {
  const top = spending.byCategory.slice(0, TOP_N);
  const rest = spending.byCategory.slice(TOP_N);
  const data = [
    ...top.map((c) => ({ label: c.label, value: c.amount })),
    ...(rest.length > 0
      ? [{ label: "기타", value: rest.reduce((sum, c) => sum + c.amount, 0) }]
      : []),
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2">
        {spending.monthlyAvgIncome !== null && (
          <div className="rounded-lg border border-border px-2.5 py-2">
            <p className="text-[10px] text-foreground-muted">월평균 소득</p>
            <p className="text-sm font-semibold mt-0.5">{formatMoney(spending.monthlyAvgIncome)}</p>
          </div>
        )}
        {spending.totalExpenditure !== null && (
          <div className="rounded-lg border border-border px-2.5 py-2">
            <p className="text-[10px] text-foreground-muted">지출 총액</p>
            <p className="text-sm font-semibold mt-0.5">{formatMoney(spending.totalExpenditure)}</p>
          </div>
        )}
        {/* 소득 금액은 2020년부터 원천이 끊겼다 — 구간의 서울 내 상대 위치로 대신한다.
            구간 숫자(1~10)는 그 자체로 의미가 없어 백분위만 보여준다. */}
        {spending.incomePercentile !== null && (
          <div className="rounded-lg border border-border px-2.5 py-2">
            <p className="text-[10px] text-foreground-muted">배후 소득 위치</p>
            <p className="text-sm font-semibold mt-0.5">
              서울 상권 상위 {Math.max(1, Math.round((1 - spending.incomePercentile) * 100))}%
            </p>
          </div>
        )}
      </div>
      {data.length > 0 && (
        <div>
          <p className="text-xs text-foreground-muted mb-1.5">카테고리별 지출</p>
          <div style={{ height: data.length * 26 + 8 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="label"
                  tick={{ fontSize: 10, fill: "#6B7280" }}
                  axisLine={false}
                  tickLine={false}
                  width={52}
                />
                <Tooltip
                  formatter={(v) => [formatMoney(Number(v)), "지출"]}
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #EBE8DF" }}
                  cursor={{ fill: "rgba(153, 27, 27, 0.06)" }}
                />
                <Bar dataKey="value" fill="#991B1B" fillOpacity={0.8} radius={[0, 3, 3, 0]} maxBarSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
