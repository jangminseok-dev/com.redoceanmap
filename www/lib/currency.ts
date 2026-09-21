// 티커로 통화를 정한다 — 한국 6자리(거래소 접미 포함)는 원, 그 외는 달러.
// 백엔드 chat 컨텍스트(_currency_unit)와 같은 규칙이다.
export const currencyUnit = (symbol: string): "원" | "달러" => {
  const base = symbol.split(".")[0];
  return base.length === 6 && /^\d+$/.test(base) ? "원" : "달러";
};

// 원화는 소수점 없이(조정가 때문에 "356,107.27원"처럼 의미 없는 자리가 보였다 — 백엔드 stock_report._p와 같은 규칙)
export const formatPrice = (value: number, symbol: string): string => {
  const unit = currencyUnit(symbol);
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: unit === "원" ? 0 : 2 })}${unit}`;
};

/** 거래대금 — 원 단위로 쓰면 자릿수를 셀 수 없어 통화별 관습 단위로 접는다.
 *  통화가 종목마다 다르므로(워치리스트 대부분이 미국) **이 값끼리 비교·정렬하지 않는다.** */
export const formatTurnover = (value: number, symbol: string): string => {
  if (currencyUnit(symbol) === "원") {
    return value >= 1e12
      ? `${(value / 1e12).toFixed(1)}조원`
      : `${Math.round(value / 1e8).toLocaleString("ko-KR")}억원`;
  }
  return value >= 1e9
    ? `$${(value / 1e9).toFixed(1)}B`
    : `$${Math.round(value / 1e6).toLocaleString("ko-KR")}M`;
};
