import type { StockAnalyzeResult, StockForecast } from "@/lib/types";

// 확률이 기준선을 이 정도는 넘어야 "평소와 다르다"고 말한다
const EDGE_MIN_PP = 3;

const DIRECTION_WORD: Record<StockAnalyzeResult["direction"], string> = {
  UP: "상승",
  DOWN: "하락",
  NEUTRAL: "중립",
};

/** 결론 한 줄 — 방향 신호와 과거 통계를 합쳐 하나로 말한다.
 *  판정·확률·확신도를 따로 띄우면 "상승 36%" vs "평소와 다르지 않음"처럼 서로 반박한다.
 *  StockHero·챗 카드가 같은 결론을 쓰도록 단일 소스로 둔다. */
export function verdict(
  analyze: StockAnalyzeResult,
  forecast?: StockForecast,
): { headline: string; detail: string } {
  const p = forecast?.probability;
  const edgePp = p ? Math.round(p.up_rate * 100) - Math.round(p.baseline_up_rate * 100) : null;
  const word = DIRECTION_WORD[analyze.direction];

  if (analyze.direction === "NEUTRAL") {
    return {
      headline: "지금은 방향을 말하기 어렵습니다",
      detail: "지표들이 서로 상쇄돼 한쪽으로 기울지 않았습니다.",
    };
  }
  // up_rate는 **그 방향의 적중률**이다(2026-08-28) — DOWN이면 "변동성 초과 하락" 비율.
  // verdict.py와 같은 규칙이어야 카드와 히어로가 어긋나지 않는다.
  const moved = analyze.direction === "UP" ? "올랐" : "내렸";

  if (edgePp === null || !p?.ready || Math.abs(edgePp) < EDGE_MIN_PP) {
    return {
      headline: `${word} 쪽 신호가 있지만, 근거는 약합니다`,
      detail:
        edgePp === null
          ? "과거 통계로 검증할 표본이 아직 없습니다."
          : `과거 같은 신호일 때 실제로 ${moved}던 비율이 평소와 사실상 같았습니다(차이 ${edgePp >= 0 ? "+" : ""}${edgePp}%p).`,
    };
  }
  return {
    headline: `${word} 쪽 신호이고, 과거 이 신호일 때 실제로 ${moved}던 비율이 평소보다 ${edgePp >= 0 ? "+" : ""}${edgePp}%p 높았습니다`,
    detail: `표본 ${p.sample_size}회 · 95% 구간 ${Math.round(p.ci_low * 100)}~${Math.round(p.ci_high * 100)}%.`,
  };
}

// 백엔드 position_profile.py와 같은 라벨 축 — 화면 문구와 해설이 어긋나지 않게 맞춘다
const RSI_ZONE_WORD: Record<NonNullable<StockForecast["position"]>["rsi_zone"], string> = {
  oversold: "과매도",
  neutral: "중립",
  overbought: "과매수",
};

/** 지금 어느 국면인가 — 고점 대비 낙폭 + RSI 구간. 예측이 아니라 현재 상태 서술. */
export function positionLine(forecast?: StockForecast): string | null {
  const p = forecast?.position;
  if (!p) return null;
  const drop = Math.round(p.drawdown_from_high_pct * 1000) / 10;
  const room = Math.round(p.above_support_pct * 1000) / 10;
  return `60일 고점 대비 ${drop >= 0 ? "+" : ""}${drop}% · 저점보다 ${room >= 0 ? "+" : ""}${room}% 위 · RSI ${Math.round(p.rsi)}(${RSI_ZONE_WORD[p.rsi_zone]})`;
}

/** 더 떨어지면 어디까지였고 회복은 됐나 — 하락을 단정하지 않고 같은 신호의 실측 분포로만 말한다.
 *  백엔드가 하락 방향을 예측하지 않는 이유(검증 실패)를 화면에서도 "확률 단정"으로 바꾸지 않는다. */
export function downsideLine(forecast?: StockForecast): string | null {
  const d = forecast?.downside;
  if (!d || d.trough_median_pct === null) return null;
  const trough = Math.round(d.trough_median_pct * 1000) / 10;
  const worst = d.trough_q25_pct === null ? null : Math.round(d.trough_q25_pct * 1000) / 10;
  const head = `과거 같은 신호에서 장중 최대 낙폭 중앙값 ${trough}%${worst === null ? "" : ` (나쁜 쪽 25%는 ${worst}%)`}`;
  if (d.dip_samples === 0) return `${head}. 기준가 아래로 내려간 사례는 없었습니다.`;
  if (d.recovery_rate === null) return `${head}.`;
  const days =
    d.recovery_days_median === null
      ? ""
      : ` 회복까지 중앙값 ${Math.round(d.recovery_days_median)}거래일.`;
  return `${head}. 내려간 ${d.dip_samples}회 중 ${Math.round(d.recovery_rate * 100)}%가 기준가를 회복했습니다.${days}`;
}

/** 신호 세기 — "확신도 36%"는 초보자가 확률로 오독한다. 확률이 아니라는 게 드러나는 표기로 바꾼다. */
export function strength(analyze: StockAnalyzeResult): string {
  const score = Math.abs(analyze.score ?? 0);
  const threshold = analyze.up_threshold ?? 0.3;
  if (score < threshold) return "약";
  if (score < threshold * 2) return "보통";
  return "강";
}
