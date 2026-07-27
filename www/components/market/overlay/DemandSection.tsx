"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AreaDetail } from "@/lib/types";
import { formatMoney, formatPop } from "./format";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border px-2.5 py-2">
      <p className="text-[10px] text-foreground-muted">{label}</p>
      <p className="text-sm font-semibold mt-0.5">{value}</p>
    </div>
  );
}

// 상주(좌, 음수 변환) vs 직장(우) 인구를 연령대 축으로 맞댄 diverging 차트
export default function DemandSection({
  demand,
  facility,
}: {
  demand: NonNullable<AreaDetail["demand"]>;
  facility: AreaDetail["facility"];
}) {
  const { resident, working, households, apartment } = demand;
  // "여기 사람이 왜 오는가" — 외부 유입 앵커만 추린다(0인 항목은 칩 자체를 만들지 않는다)
  const anchors: [string, number][] = facility
    ? ([
        ["지하철역", facility.subwayStations],
        ["버스정거장", facility.busStops],
        ["대학", facility.universities],
        ["백화점", facility.departmentStores],
        ["병원", facility.hospitals],
      ] as [string, number][]).filter(([, n]) => n > 0)
    : [];

  const bands = resident?.byAge.length ? resident.byAge : working?.byAge ?? [];
  const pyramid = bands.map((row) => {
    const workingRow = working?.byAge.find((w) => w.band === row.band);
    const residentRow = resident?.byAge.find((r) => r.band === row.band);
    return {
      band: row.band === "60+" ? "60+" : `${row.band}대`,
      resident: -((residentRow?.male ?? 0) + (residentRow?.female ?? 0)),
      working: (workingRow?.male ?? 0) + (workingRow?.female ?? 0),
    };
  });
  const hasPyramid = pyramid.some((p) => p.resident !== 0 || p.working !== 0);

  return (
    <div className="flex flex-col gap-3">
      {(resident || working) && (
        <div className="flex gap-3 text-xs text-foreground-muted">
          {resident && <span>상주 <b className="text-foreground">{formatPop(resident.total)}명</b></span>}
          {working && <span>직장 <b className="text-foreground">{formatPop(working.total)}명</b></span>}
        </div>
      )}
      {hasPyramid && (
        <div>
          <p className="text-xs text-foreground-muted mb-1.5">
            연령대별 <span className="text-[#2563EB]">상주</span> · <span className="text-brand">직장</span> 인구
          </p>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={pyramid}
                layout="vertical"
                stackOffset="sign"
                margin={{ top: 0, right: 8, bottom: 0, left: 0 }}
              >
                <CartesianGrid stroke="#EBE8DF" strokeDasharray="3 3" horizontal={false} />
                <XAxis
                  type="number"
                  tickFormatter={(v) => formatPop(Math.abs(Number(v)))}
                  tick={{ fontSize: 10, fill: "#6B7280" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="band"
                  tick={{ fontSize: 10, fill: "#6B7280" }}
                  axisLine={false}
                  tickLine={false}
                  width={34}
                />
                <Tooltip
                  formatter={(v, name) => [
                    `${Math.abs(Number(v)).toLocaleString("ko-KR")}명`,
                    name === "resident" ? "상주" : "직장",
                  ]}
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #EBE8DF" }}
                  cursor={{ fill: "rgba(153, 27, 27, 0.06)" }}
                />
                <ReferenceLine x={0} stroke="#9CA3AF" />
                <Bar dataKey="resident" stackId="pop" fill="#2563EB" fillOpacity={0.7} maxBarSize={14} />
                <Bar dataKey="working" stackId="pop" fill="#991B1B" fillOpacity={0.8} maxBarSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
      <div className="grid grid-cols-3 gap-2">
        {households && (
          <StatCard
            label="배후 가구"
            value={`${formatPop(households.total)}가구${
              households.total > 0
                ? ` · 아파트 ${Math.round((households.apartment / households.total) * 100)}%`
                : ""
            }`}
          />
        )}
        {apartment && <StatCard label="아파트 단지" value={`${apartment.complexCount}개`} />}
        {apartment && apartment.avgPrice > 0 && (
          <StatCard label="평균 매매가" value={formatMoney(apartment.avgPrice)} />
        )}
      </div>
      {anchors.length > 0 && (
        <div>
          <p className="text-xs text-foreground-muted mb-1.5">외부 유입 앵커</p>
          <div className="flex flex-wrap gap-1.5">
            {anchors.map(([label, n]) => (
              <span
                key={label}
                className="text-[11px] px-2 py-1 rounded-full bg-brand/10 text-brand font-medium"
              >
                {label} {n}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
