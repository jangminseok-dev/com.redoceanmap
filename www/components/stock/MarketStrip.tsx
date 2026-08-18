"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchStockQuote } from "@/lib/api";
import { Marquee } from "@/components/ui/marquee";

// 지수는 수집 대상이 아니다(price_bars는 레짐 판정용 SPY·^VIX만 담는다) —
// 서버 20초 공유 캐시가 붙은 quote를 그대로 재사용한다.
const INDICES = [
  { symbol: "^KS11", label: "코스피" },
  { symbol: "^KQ11", label: "코스닥" },
  { symbol: "^GSPC", label: "S&P 500" },
  { symbol: "^IXIC", label: "나스닥" },
  { symbol: "KRW=X", label: "원/달러" },
  { symbol: "^VIX", label: "VIX" },
];

const signedPct = (v: number) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;

function IndexChip({ symbol, label }: { symbol: string; label: string }) {
  const { data } = useQuery({
    queryKey: ["quote", symbol],
    queryFn: () => fetchStockQuote(symbol),
    retry: false,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
  // 조회 실패한 지수는 조용히 빠진다 — 스트립은 장식이고 아래 본체가 정보다
  if (!data) return null;

  return (
    <span className="inline-flex items-baseline gap-1.5 whitespace-nowrap text-xs">
      <span className="text-foreground-muted">{label}</span>
      <span className="font-semibold tabular-nums">
        {data.price.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}
      </span>
      {data.change_pct != null && (
        <span className={`tabular-nums ${data.change_pct > 0 ? "text-up" : data.change_pct < 0 ? "text-down" : "text-foreground-muted"}`}>
          {signedPct(data.change_pct)}
        </span>
      )}
    </span>
  );
}

// 시장 티커 스트립 — 스테이지 최상단 상주(레퍼런스 토스증권 하단 지수 스트립).
// 흐르게 두면 폭과 무관해져 375px에서도 잘리지 않는다.
export default function MarketStrip() {
  return (
    <div className="shrink-0 h-8 flex items-center border-b border-border overflow-hidden">
      <Marquee duration="50s" className="[--gap:2rem]">
        {INDICES.map((index) => (
          <IndexChip key={index.symbol} {...index} />
        ))}
      </Marquee>
    </div>
  );
}
