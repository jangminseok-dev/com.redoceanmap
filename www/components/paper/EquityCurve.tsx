"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PaperBenchmarkPoint, PaperEquityPoint, PaperTrade } from "@/lib/types";
import { fmtDay, fmtKrw } from "./format";

type SeriesMap = Record<string, PaperEquityPoint[]>; // key → 곡선(as_of 오름차순)

const LINE_STYLE: Record<string, { stroke: string; dash?: string; label: string }> = {
  exaone: { stroke: "var(--brand)", label: "AI 판단" },
  signal: { stroke: "var(--foreground-muted)", dash: "4 3", label: "지표 규칙" },
  me: { stroke: "var(--up)", label: "나" },
  spy: { stroke: "var(--foreground)", dash: "1 3", label: "SPY 보유" },
};

/**
 * 자산 곡선 — 여러 계정과 SPY 기준선을 한 축에 겹친다. 리플레이 구간은 음영, 선택 계정의 체결은
 * 점(마커)으로 찍고, 되감기로 고른 날짜에 세로선을 긋는다.
 */
export default function EquityCurve({
  series,
  spy,
  markerKey,
  trades,
  replayUntil,
  selectedDate,
  onPickDate,
}: {
  series: SeriesMap;
  spy: PaperBenchmarkPoint[];
  markerKey: string; // 마커를 찍을 계정(series의 키)
  trades: PaperTrade[];
  replayUntil: string | null;
  selectedDate: string | null;
  onPickDate?: (date: string) => void;
}) {
  const byDate = new Map<string, Record<string, number | string>>();
  const put = (date: string, key: string, v: number) => {
    const row = byDate.get(date) ?? { date };
    row[key] = v;
    byDate.set(date, row);
  };
  for (const [key, points] of Object.entries(series)) points.forEach((p) => put(p.as_of, key, p.equity_krw));
  spy.forEach((p) => put(p.as_of, "spy", p.equity_krw));
  const data = [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  if (data.length === 0) {
    return <p className="text-sm text-foreground-muted">아직 평가 기록이 없습니다.</p>;
  }

  // 마커 y값 = 그 체결일의 선택 계정 평가액(없으면 직전 평가). 세션이 아닌 캘린더 날짜로 맞춘다.
  const equityOn = (date: string) => {
    const pts = series[markerKey] ?? [];
    let last: number | undefined;
    for (const p of pts) {
      if (p.as_of > date) break;
      last = p.equity_krw;
    }
    return last;
  };
  const markers = trades
    .map((t) => ({ t, date: t.ts.slice(0, 10) }))
    .map(({ t, date }) => ({ t, date, y: equityOn(date) }))
    .filter((m): m is { t: PaperTrade; date: string; y: number } => m.y !== undefined);

  const firstDate = String(data[0].date);
  const keys = Object.keys(series).filter((k) => LINE_STYLE[k]);

  return (
    <div className="h-64 sm:h-80">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
          onClick={(state) => {
            const label = state?.activeLabel;
            if (label && onPickDate) onPickDate(String(label));
          }}
        >
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tickFormatter={fmtDay} tick={{ fontSize: 10, fill: "var(--foreground-muted)" }} axisLine={{ stroke: "var(--border)" }} tickLine={false} minTickGap={24} />
          <YAxis tickFormatter={(v) => fmtKrw(Number(v))} tick={{ fontSize: 10, fill: "var(--foreground-muted)" }} axisLine={false} tickLine={false} width={56} domain={["auto", "auto"]} />
          <Tooltip
            labelFormatter={(l) => String(l)}
            formatter={(v, name) => [fmtKrw(Number(v)), LINE_STYLE[String(name)]?.label ?? String(name)]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)", backgroundColor: "var(--surface)", color: "var(--foreground)" }}
          />
          {replayUntil && (
            <ReferenceArea x1={firstDate} x2={replayUntil} fill="var(--foreground)" fillOpacity={0.04} strokeOpacity={0} />
          )}
          {selectedDate && <ReferenceLine x={selectedDate} stroke="var(--brand)" strokeDasharray="2 2" />}
          {keys.map((k) => (
            <Line key={k} type="monotone" dataKey={k} name={k} stroke={LINE_STYLE[k].stroke} strokeDasharray={LINE_STYLE[k].dash} strokeWidth={k === markerKey ? 2.2 : 1.4} dot={false} connectNulls isAnimationActive={false} />
          ))}
          {spy.length > 0 && (
            <Line type="monotone" dataKey="spy" name="spy" stroke={LINE_STYLE.spy.stroke} strokeDasharray={LINE_STYLE.spy.dash} strokeWidth={1.2} dot={false} connectNulls isAnimationActive={false} />
          )}
          {markers.map(({ t, date, y }) => (
            <ReferenceDot
              key={t.id}
              x={date}
              y={y}
              r={4}
              fill={t.action === "BUY" || t.action === "COVER" ? "var(--up)" : "var(--down)"}
              stroke="var(--surface)"
              strokeWidth={1.5}
              onClick={() => onPickDate?.(date)}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
