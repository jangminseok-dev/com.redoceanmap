import type { PaperRules } from "@/lib/types";

/** 고정 고지 — 화면당 한 번. 실제 매매가 아니고 권유가 아니라는 것, 체결 축이 다르다는 것을 먼저 말한다. */
export default function RulesNotice({ rules, replayUntil }: { rules: PaperRules; replayUntil: string | null }) {
  return (
    <details className="rounded-2xl border border-border bg-surface px-4 py-3 text-xs leading-relaxed text-foreground-muted">
      <summary className="cursor-pointer select-none text-sm text-foreground">
        <span className="font-semibold">실제 돈이 아닙니다</span> — AI 판단의 기록이고 매매 권유가 아닙니다. <span className="text-foreground-muted">규칙 보기</span>
      </summary>
      <p className="mt-2">
        AI 계정은 매일 14:00 동결된 예측 스냅샷과 뉴스 라벨을 읽고 종목·방향·비중을 판단하며, 그 판단은
        다음 세션 시가에 사후 체결됩니다(판단 모델: 2026-09-11까지 EXAONE 3.5 7.8B, 9/15부터 Gemma 4 e4b).
        지표 규칙 계정은 그날 활성화된 지표 조합의 신호를 그대로 따르는 대조군입니다. 여기 있는
        어떤 문장도 매수·매도 권유가 아니며, &ldquo;어느 계정이 무엇을 샀다&rdquo;는 사실만 적습니다.
      </p>
      <p className="mt-1.5">
        지표 조합은 통계적으로 검증된 신호가 아닙니다. 2026-09-17 워치리스트 81종목 10년치를 앞·뒤 5년으로 나누고 겹치는 기간을
        보정해 다시 채점하니, 반등(상승) 신호는 앞 5년엔 평소보다 조금 더 맞혔지만 최근 5년엔 평소와 구분되지 않았고 하락 신호는
        평소보다 못해 내지 않습니다. 9/1~9/16에는 자동 재적합이 바꾼 조합이 쓰였고 성적이 나빠 되돌렸습니다. 이 계정은
        &ldquo;지표만 따르면 어떻게 되나&rdquo;를 보여주는 대조군입니다.
      </p>
      <p className="mt-1.5 tabular-nums">
        가정치: 초기 자본 {(rules.assumed_initial_cash_krw / 1e8).toFixed(0)}억원 · 수수료{" "}
        {(rules.assumed_fee_rate * 100).toFixed(1)}%/체결 · 환율 고정 {rules.assumed_usdkrw.toLocaleString("ko-KR")}원/$ ·
        종목당 ≤{Math.round(rules.assumed_max_position_weight * 100)}% · 동시 ≤{rules.assumed_max_positions}종목 · 숏
        가능(레버리지 없음){replayUntil ? ` · ${replayUntil}까지는 저장된 과거 스냅샷으로 재생한 구간` : ""}
      </p>
    </details>
  );
}
