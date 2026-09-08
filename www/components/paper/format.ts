// 모의투자 화면 공용 포맷 — 자산은 원화, 체결가는 종목 통화(원/달러 혼재)
import { currencyUnit } from "@/lib/currency";

export const fmtKrw = (v: number) => {
  const abs = Math.abs(v);
  if (abs >= 1e8) return `${(v / 1e8).toFixed(2)}억원`;
  if (abs >= 1e4) return `${Math.round(v / 1e4).toLocaleString("ko-KR")}만원`;
  return `${Math.round(v).toLocaleString("ko-KR")}원`;
};

export const fmtPct = (v: number | null | undefined, digits = 1) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(digits)}%`;

export const fmtPrice = (v: number, ticker: string) =>
  currencyUnit(ticker) === "원"
    ? `${Math.round(v).toLocaleString("ko-KR")}원`
    : `$${v.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}`;

export const fmtDay = (iso: string) =>
  new Date(iso).toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });

export const ACTION_LABEL: Record<string, string> = {
  BUY: "매수",
  SELL: "매도",
  SHORT: "숏 진입",
  COVER: "숏 청산",
};

// 롱 진입·숏 청산은 상승 방향, 매도·숏 진입은 하락 방향 — 색은 방향 토큰 둘뿐(DESIGN.md §7)
export const ACTION_TONE: Record<string, string> = {
  BUY: "text-up bg-up-weak",
  COVER: "text-up bg-up-weak",
  SELL: "text-down bg-down-weak",
  SHORT: "text-down bg-down-weak",
};

export const KIND_LABEL: Record<string, string> = {
  exaone: "EXAONE",
  signal: "지표 규칙",
};
