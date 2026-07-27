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

// 구간 분포를 한 줄 띠로 — 세그먼트가 곧 비중이라 축·범례 없이도 구성이 읽힌다.
// 1% 미만 구간은 렌더하지 않는다(1px 조각이 색만 어지럽힌다).
function BandBar({
  label,
  bands,
  order,
}: {
  label: string;
  bands: Record<string, number>;
  order: [string, string, string][]; // [키, 표시명, 색]
}) {
  const total = order.reduce((s, [k]) => s + (bands[k] ?? 0), 0);
  if (total <= 0) return null;
  const segments = order
    .map(([k, name, color]) => ({ name, color, share: (bands[k] ?? 0) / total }))
    .filter((s) => s.share >= 0.01);
  return (
    <div>
      <p className="text-xs text-foreground-muted mb-1.5">{label}</p>
      <div className="flex h-2.5 rounded-full overflow-hidden bg-black/5">
        {segments.map((s) => (
          <div
            key={s.name}
            style={{ width: `${s.share * 100}%`, backgroundColor: s.color }}
            title={`${s.name} ${Math.round(s.share * 100)}%`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-2.5 gap-y-1 mt-1.5">
        {segments.map((s) => (
          <span key={s.name} className="inline-flex items-center gap-1 text-[10px] text-foreground-muted">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: s.color }} />
            {s.name} {Math.round(s.share * 100)}%
          </span>
        ))}
      </div>
    </div>
  );
}

// 저가→고가, 소형→대형 순서로 색이 짙어진다(순서 자체가 정보라 임의 색을 쓰지 않는다)
const PRICE_ORDER: [string, string, string][] = [
  ["under1b", "1억 미만", "#FDE68A"],
  ["b1", "1억대", "#FCD34D"],
  ["b2", "2억대", "#FBBF24"],
  ["b3", "3억대", "#F59E0B"],
  ["b4", "4억대", "#D97706"],
  ["b5", "5억대", "#B45309"],
  ["over6b", "6억 이상", "#78350F"],
];
const AREA_ORDER: [string, string, string][] = [
  ["under66", "66㎡ 미만", "#BFDBFE"],
  ["a66", "66~99㎡", "#93C5FD"],
  ["a99", "99~132㎡", "#60A5FA"],
  ["a132", "132~165㎡", "#3B82F6"],
  ["a165", "165㎡ 이상", "#1D4ED8"],
];

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
        // 성격 축 — 유입의 종류. 시설 13종을 그대로 세지 않고 묶은 값이다
        ["철도·터미널", facility.gateway],
        ["학교", facility.schools],
        ["극장·숙박", facility.nightlife],
        ["생활시설", facility.convenience],
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
      {apartment?.priceBands && (
        <BandBar label="배후 아파트 가격대" bands={apartment.priceBands} order={PRICE_ORDER} />
      )}
      {apartment?.areaBands && (
        <BandBar label="평형 구성" bands={apartment.areaBands} order={AREA_ORDER} />
      )}
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
