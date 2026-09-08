"use client";

import { fmtDay } from "./format";

/** 되감기 — 판단이 있는 날짜들 위를 오간다. 순수 프론트(저장된 판단만 읽는다). */
export default function TimeScrubber({
  dates,
  index,
  onChange,
}: {
  dates: string[]; // 오름차순
  index: number;
  onChange: (index: number) => void;
}) {
  if (dates.length === 0) return null;
  const current = dates[index] ?? dates[dates.length - 1];
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-foreground-muted shrink-0">{fmtDay(dates[0])}</span>
      <input
        type="range"
        min={0}
        max={dates.length - 1}
        value={index}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label="판단 날짜 되감기"
        className="flex-1 accent-[var(--brand)]"
      />
      <span className="text-xs text-foreground-muted shrink-0">{fmtDay(dates[dates.length - 1])}</span>
      <span className="ml-1 shrink-0 rounded-full bg-brand/10 px-2.5 py-1 text-xs font-medium text-brand tabular-nums">
        {new Date(current).toLocaleDateString("ko-KR", { year: "numeric", month: "numeric", day: "numeric" })}
      </span>
    </div>
  );
}
