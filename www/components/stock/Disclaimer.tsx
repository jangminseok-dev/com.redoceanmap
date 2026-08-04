// 화면당 한 번만 노출하는 단일 면책 — 예전엔 같은 취지 문구가 지표 타일·밴드·근거 블록 등
// 여러 곳에 흩어져 헤지 밀도만 높였다. 결론 바로 아래에서 한 번 말한다.
export default function Disclaimer({ className = "" }: { className?: string }) {
  return (
    <p className={`text-xs text-foreground-muted leading-relaxed ${className}`}>
      지연 시세 기반 참고 정보입니다. 확률·예상 범위는 과거 통계이며 미래를 보장하지 않습니다.
      매매 지시가 아니며 투자 판단과 책임은 본인에게 있습니다.
    </p>
  );
}
