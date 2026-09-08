import type { PaperRules } from "@/lib/types";

/** 고정 고지 — 화면당 한 번. 실제 매매가 아니고 권유가 아니라는 것, 체결 축이 다르다는 것을 먼저 말한다. */
export default function RulesNotice({ rules, replayUntil }: { rules: PaperRules; replayUntil: string | null }) {
  return (
    <details className="rounded-2xl border border-border bg-surface px-4 py-3 text-xs leading-relaxed text-foreground-muted">
      <summary className="cursor-pointer select-none text-sm text-foreground">
        <span className="font-semibold">실제 돈이 아닙니다</span> — AI 판단의 기록이고 매매 권유가 아닙니다. <span className="text-foreground-muted">규칙 보기</span>
      </summary>
      <p className="mt-2">
        EXAONE 계정은 매일 14:00 동결된 예측 스냅샷과 뉴스 라벨을 읽고 종목·방향·비중을 판단하며, 그 판단은
        다음 세션 시가에 사후 체결됩니다. 지표 규칙 계정은 검증된 지표 조합을 그대로 따르는 대조군입니다.  여기 있는
        어떤 문장도 매수·매도 권유가 아니며, &ldquo;어느 계정이 무엇을 샀다&rdquo;는 사실만 적습니다.
      </p>
      <p className="mt-1.5">
        &ldquo;검증된 지표 규칙&rdquo;의 검증이란: 20종목 5년 백테스트에서 그 신호가 났을 때 실제로 그 방향으로 간 비율의 95%
        신뢰구간 하한이 평소 비율보다 높았다는 뜻입니다(인샘플·홀드아웃 두 구간 모두). 우위는 몇 %p 수준이고, 매주
        재적합으로 조합이 바뀔 수 있습니다. &ldquo;맞힌다&rdquo;가 아니라 &ldquo;동전 던지기보다 조금 낫다는 것이 확인됐다&rdquo;에 가깝습니다.
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
