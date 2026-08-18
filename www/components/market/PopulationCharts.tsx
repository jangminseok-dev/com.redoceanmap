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
import type { AreaStatsDetail } from "@/lib/types";

const formatPop = (v: number) => {
  if (Math.abs(v) >= 1e4) return `${(v / 1e4).toFixed(0)}만`;
  return v.toLocaleString("ko-KR");
};

function PopBarChart({ data }: { data: { label: string; value: number }[] }) {
  return (
    <div className="h-32">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "var(--foreground-muted)" }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={formatPop}
            tick={{ fontSize: 10, fill: "var(--foreground-muted)" }}
            axisLine={false}
            tickLine={false}
            width={36}
          />
          <Tooltip
            formatter={(v) => [`${Number(v).toLocaleString("ko-KR")}명`, "유동인구"]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)", backgroundColor: "var(--surface)", color: "var(--foreground)" }}
            cursor={{ fill: "rgb(var(--heat-rgb) / 0.06)" }}
          />
          <Bar dataKey="value" fill="var(--brand)" radius={[3, 3, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function PopulationCharts({ latest }: { latest: AreaStatsDetail["latest"] }) {
  const { floatingByAge: age, floatingByTime: time } = latest;
  if (!age && !time) {
    return <p className="text-sm text-foreground-muted">유동인구 데이터가 없습니다.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {age && (
        <div>
          <p className="text-xs text-foreground-muted mb-1.5">연령대별</p>
          <PopBarChart
            data={[
              { label: "10대", value: age.age10 },
              { label: "20대", value: age.age20 },
              { label: "30대", value: age.age30 },
              { label: "40대", value: age.age40 },
              { label: "50대", value: age.age50 },
              { label: "60+", value: age.age60Plus },
            ]}
          />
        </div>
      )}
      {time && (
        <div>
          <p className="text-xs text-foreground-muted mb-1.5">
            시간대별 <span className="text-xs">(시간당 평균)</span>
          </p>
          {/* 구간 폭이 제각각이라(0-6시 6시간, 11-14시 3시간) 원값을 그대로 그리면 막대가
              정반대를 말한다. 미아사거리 실측: 총합은 0-6시가 최고지만 시간당으로는 최하위
              (13,665명/h)이고 실제 최고는 14-17시(16,356명/h)다. 시간당으로 나눠 그린다. */}
          <PopBarChart
            data={[
              { label: "0-6시", value: Math.round(time.t00_06 / 6) },
              { label: "6-11시", value: Math.round(time.t06_11 / 5) },
              { label: "11-14시", value: Math.round(time.t11_14 / 3) },
              { label: "14-17시", value: Math.round(time.t14_17 / 3) },
              { label: "17-21시", value: Math.round(time.t17_21 / 4) },
              { label: "21-24시", value: Math.round(time.t21_24 / 3) },
            ]}
          />
        </div>
      )}
    </div>
  );
}
