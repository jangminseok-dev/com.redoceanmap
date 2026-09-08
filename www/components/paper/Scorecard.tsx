import type { PaperScoreBucket, PaperScorecard } from "@/lib/types";

const REASON_LABEL: Record<string, string> = { news: "뉴스 근거", indicator: "지표 근거", mixed: "뉴스+지표", none: "근거 없음", total: "전체" };
const ACTION_LABEL: Record<string, string> = { BUY: "롱 진입", SHORT: "숏 진입" };

function Row({ b, label, min }: { b: PaperScoreBucket; label: string; min: number }) {
  return (
    <li className="flex items-center gap-3 py-2 text-sm">
      <span className="flex-1">{label}</span>
      <span className="text-xs text-foreground-muted tabular-nums">n={b.n}</span>
      {b.hit_rate == null ? (
        <span className="rounded-full bg-border/40 px-2 py-0.5 text-[11px] text-foreground-muted">
          표본 {min}건 전 — 숫자 비노출
        </span>
      ) : (
        <span className="tabular-nums">
          <span className="font-semibold">{Math.round(b.hit_rate * 100)}%</span>
          <span className="ml-1 text-xs text-foreground-muted">
            (95% {Math.round((b.ci_low ?? 0) * 100)}~{Math.round((b.ci_high ?? 0) * 100)}%)
          </span>
        </span>
      )}
    </li>
  );
}

/** 판단 사후 채점 — 진입 주문의 5거래일 적중률. 표본이 차기 전엔 배지만 보이고 숫자는 감춘다. */
export default function Scorecard({ card }: { card: PaperScorecard }) {
  return (
    <div>
      <p className="text-xs text-foreground-muted leading-relaxed">
        적중은 5거래일 실현 수익률이 변동성 문턱(ATR×√5×0.25)을 넘은 경우로, 예측 스냅샷 채점과 같은
        정의입니다. 숏은 하락이 적중입니다. 과거 기록이며 미래를 보장하지 않습니다.
      </p>
      <ul className="mt-2 divide-y divide-border">
        <Row b={card.total} label="전체 진입 판단" min={card.min_samples} />
        {card.by_reason.map((b) => <Row key={`r-${b.key}`} b={b} label={REASON_LABEL[b.key] ?? b.key} min={card.min_samples} />)}
        {card.by_action.map((b) => <Row key={`a-${b.key}`} b={b} label={ACTION_LABEL[b.key] ?? b.key} min={card.min_samples} />)}
      </ul>
    </div>
  );
}
