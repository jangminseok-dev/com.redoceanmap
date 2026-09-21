import type { StockAnalyzeResult, StockForecast } from "@/lib/types";

// 확률이 기준선을 이 정도는 넘어야 "평소와 다르다"고 말한다
const EDGE_MIN_PP = 3;

// 종합 점수가 이 안쪽이면 "지표가 서로 상쇄됐다"고 말한다 — 백엔드 chat verdict.py와 동일
const OFFSET_BAND = 0.1;

type Risk = NonNullable<StockForecast["risk"]>;
type RiskKey = Risk["evidence"][number]["key"];

// 위험 상태의 결과 문구 — 검증 리포트 키별. verdict.py와 동일
const OUTCOME: Record<RiskKey, string> = {
  drop_high: "20거래일 안에 -10% 이상 떨어진 적이 있는 비율이",
  drop_low: "20거래일 안에 -10% 이상 떨어진 적이 있는 비율이",
  vol_high: "20거래일 안에 변동성이 더 커진 비율이",
  vol_low: "20거래일 안에 변동성이 더 커진 비율이",
};

const pct = (v: number) => Math.round(v * 100);

/** 중립인 실제 이유 — 상쇄 / 하락 쪽(미검증이라 말하지 않음) / 상승 쪽 기준 미달 / 관망 규칙. */
function directionNote(analyze: StockAnalyzeResult): string {
  const score = analyze.score;
  if (score === undefined) return "방향은 과거 검증에서 평소와 구별되지 않아 말하지 않아요.";
  const t = analyze.up_threshold || 0.3;
  if (Math.abs(score) <= OFFSET_BAND) return "방향 지표는 서로 상쇄돼 어느 쪽으로도 기울지 않았어요.";
  if (score < 0)
    return "방향 지표는 하락 쪽이지만, 하락 신호는 과거 검증을 통과하지 못해 방향으로 말하지 않아요.";
  if (score < t)
    return `방향 지표는 상승 쪽이지만 기준에 못 미쳐요(점수 ${score.toFixed(2)} · 기준 ${t.toFixed(2)}).`;
  return "방향 점수는 기준을 넘었지만 관망 규칙(실적 발표·변동성·거래량)에 걸려 방향으로 말하지 않아요.";
}

/** 낙폭이 변동성보다 먼저 — 보드 배지(MarketBoard)와 같은 우선순위. */
function riskLead(risk: Risk): { headline: string; state: string; key: RiskKey | null } {
  const top = Math.max(1, 100 - pct(risk.rv_percentile));
  if (risk.drawdown_risk === "HIGH")
    return {
      headline: "큰 낙폭 위험이 평소보다 높은 상태예요",
      state: "변동성이 크고 주가가 200일선 아래예요.",
      key: "drop_high",
    };
  if (risk.vol_state === "HIGH")
    return {
      headline: "앞으로 20거래일, 평소보다 크게 출렁일 가능성이 높은 상태예요",
      state: `최근 변동성이 자기 1년 중 상위 ${top}%예요.`,
      key: "vol_high",
    };
  if (risk.drawdown_risk === "LOW")
    return {
      headline: "큰 낙폭 위험이 평소보다 낮은 안정 구간이에요",
      state: "변동성이 낮고 상승 추세예요.",
      key: "drop_low",
    };
  if (risk.vol_state === "LOW")
    return {
      headline: "당분간 크게 출렁일 가능성이 낮은 상태예요",
      state: `최근 변동성이 자기 1년 중 하위 ${Math.max(1, pct(risk.rv_percentile))}%예요.`,
      key: "vol_low",
    };
  return {
    headline: "변동성·낙폭 위험은 평소 수준이에요",
    state: `최근 변동성이 자기 1년 분포의 중간쯤(상위 ${top}%)이에요.`,
    key: null,
  };
}

/** 중립이면 검증된 위험 상태를 결론으로 앞세운다(2026-09-21) — 방향 판정의 73%가 중립이라 같은 문장이
 *  네 번 중 세 번 떴고, "서로 상쇄돼"는 그중 26%에서만 사실이었다. 근거는 verdict.py 독스트링. */
function neutralVerdict(
  analyze: StockAnalyzeResult,
  forecast?: StockForecast,
): { headline: string; detail: string } {
  const note = directionNote(analyze);
  const risk = forecast?.risk;
  if (!risk) return { headline: "지금은 방향을 말하기 어렵습니다", detail: note };
  const lead = riskLead(risk);
  const parts = [lead.state];
  const proof = risk.evidence.find((e) => e.key === lead.key);
  if (proof)
    parts.push(
      `과거 이 상태에서 ${OUTCOME[proof.key]} ${pct(proof.test_rate)}%였어요(평소 ${pct(proof.base_rate)}%).`,
    );
  parts.push(note);
  return { headline: lead.headline, detail: parts.join(" ") };
}

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

  if (analyze.direction === "NEUTRAL") return neutralVerdict(analyze, forecast);
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
