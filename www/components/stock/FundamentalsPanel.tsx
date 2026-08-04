"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchFundamentals } from "@/lib/api";
import type { FundamentalSnapshot } from "@/lib/types";
import InsightList from "@/components/common/InsightList";

const SOURCE_LABEL: Record<string, string> = { yfinance: "야후", dart: "DART" };

// 큰 금액(시총·FCF)은 조/억 단위로 축약
function formatBigMoney(v: number | null) {
  if (v === null) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e12) return `${(v / 1e12).toFixed(1)}조`;
  if (abs >= 1e8) return `${(v / 1e8).toFixed(0)}억`;
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
}

const fmt = (v: number | null, digits = 2) =>
  v === null ? "—" : v.toLocaleString("ko-KR", { maximumFractionDigits: digits });

const ROWS: { label: string; render: (s: FundamentalSnapshot) => string }[] = [
  { label: "PER", render: (s) => fmt(s.per) },
  { label: "PBR", render: (s) => fmt(s.pbr) },
  { label: "ROE", render: (s) => (s.roe === null ? "—" : `${(s.roe * 100).toFixed(1)}%`) },
  { label: "부채비율", render: (s) => fmt(s.debtToEquity) },
  { label: "FCF", render: (s) => formatBigMoney(s.fcf) },
  { label: "시가총액", render: (s) => formatBigMoney(s.marketCap) },
  { label: "EPS", render: (s) => fmt(s.eps, 0) },
  { label: "BPS", render: (s) => fmt(s.bps, 0) },
];

export default function FundamentalsPanel({ symbol }: { symbol: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["fundamentals", symbol],
    queryFn: () => fetchFundamentals(symbol),
    enabled: !!symbol,
  });

  if (isLoading) {
    return (
      <div className="p-4 flex flex-col gap-2">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="skeleton h-10 rounded-lg" />
        ))}
      </div>
    );
  }
  const snapshots = data?.snapshots ?? [];
  if (isError || snapshots.length === 0) {
    return (
      <p className="p-4 text-sm text-foreground-muted">
        수집된 펀더멘털이 없습니다. 워치리스트 종목은 주 1회 수집됩니다.
      </p>
    );
  }

  return (
    <div className="p-4">
      {data?.insights && data.insights.length > 0 && (
        <div className="mb-3 bg-surface border border-border rounded-lg px-3 py-2.5">
          <InsightList insights={data.insights} />
        </div>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-foreground-muted">
            <th className="text-left font-normal pb-2">지표</th>
            {snapshots.map((s) => (
              <th key={s.source} className="text-right font-normal pb-2">
                {SOURCE_LABEL[s.source] ?? s.source}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.label} className="border-t border-border">
              <td className="py-2 text-foreground-muted">{row.label}</td>
              {snapshots.map((s) => (
                <td key={s.source} className="py-2 text-right font-medium">
                  {row.render(s)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-foreground-muted">
        기준일 {snapshots.map((s) => `${SOURCE_LABEL[s.source] ?? s.source} ${s.asOf}`).join(" · ")}.
        한국 종목의 PER/PBR은 DART 재무제표로 자체 계산됩니다.
      </p>
    </div>
  );
}
