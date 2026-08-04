import type { StockAnalyzeResult } from "@/lib/types";

// 상승 기여 빨강 / 하락 기여 파랑 — 차트·방향 배지와 동일 관례
const UP = "#DC2626";
const DOWN = "#2563EB";

// 좁은 바 라벨이라 쉬운 말 짧은 형태만(괄호 병기는 넓은 지표 타일 쪽에서)
const SIGNAL_LABELS: Record<string, string> = {
  sentiment: "뉴스 감성",
  rsi: "RSI",
  trend: "단기 추세",
  bollinger: "밴드 위치",
  obv: "자금 흐름",
  momentum: "1년 추세",
};

// 신호별 기여도 분해 — "왜 이 방향인지"를 중앙 0 기준 diverging 바로 보여준다
export default function SignalBreakdown({ analyze }: { analyze: StockAnalyzeResult }) {
  const signals = analyze.signals ?? [];
  if (signals.length === 0 || analyze.score === undefined) return null;
  const upThr = analyze.up_threshold ?? 0.3;
  const downThr = analyze.down_threshold ?? -upThr;
  const maxAbs = Math.max(0.1, ...signals.map((s) => Math.abs(s.contribution)));

  return (
    <div className="bg-surface border border-border rounded-lg px-3 py-2.5">
      <p className="text-xs text-foreground-muted mb-2">신호별 기여도 (왜 이 방향인가)</p>
      <div className="flex flex-col gap-1.5">
        {signals.map((s) => {
          const inactive = s.weight === 0;
          const widthPct = Math.min(50, (Math.abs(s.contribution) / maxAbs) * 50);
          return (
            <div key={s.key} className="flex items-center gap-2 text-xs">
              <span className={`w-16 shrink-0 ${inactive ? "text-foreground-muted/60" : "text-foreground-muted"}`}>
                {SIGNAL_LABELS[s.key] ?? s.key}
              </span>
              <div className="relative flex-1 h-3">
                <div className="absolute inset-y-0 left-1/2 w-px bg-border" />
                {!inactive && s.contribution !== 0 && (
                  <div
                    className="absolute inset-y-0.5 rounded-sm"
                    style={{
                      backgroundColor: s.contribution > 0 ? UP : DOWN,
                      opacity: 0.75,
                      left: s.contribution > 0 ? "50%" : `${50 - widthPct}%`,
                      width: `${widthPct}%`,
                    }}
                  />
                )}
              </div>
              <span className={`w-12 shrink-0 text-right tabular-nums ${inactive ? "text-foreground-muted/60" : "font-medium"}`}>
                {inactive ? `(${s.signal >= 0 ? "+" : ""}${s.signal.toFixed(1)})` : `${s.contribution >= 0 ? "+" : ""}${s.contribution.toFixed(2)}`}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-2.5 pt-2 border-t border-border">
        <div className="flex justify-between text-xs text-foreground-muted mb-1">
          <span>하락 기준 {downThr.toFixed(2)}</span>
          <span className="font-medium text-foreground">종합 {analyze.score >= 0 ? "+" : ""}{analyze.score.toFixed(2)}</span>
          <span>상승 기준 +{upThr.toFixed(2)}</span>
        </div>
        <div className="relative h-2 rounded-full bg-border/60">
          {/* 임계 눈금 (임계값을 ±1 스케일 위에) */}
          <div className="absolute inset-y-0 w-px bg-foreground-muted/50" style={{ left: `${50 + downThr * 50}%` }} />
          <div className="absolute inset-y-0 w-px bg-foreground-muted/50" style={{ left: `${50 + upThr * 50}%` }} />
          <div
            className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border-2 border-background shadow"
            style={{
              backgroundColor: analyze.score > 0 ? UP : analyze.score < 0 ? DOWN : "#9CA3AF",
              left: `calc(${50 + Math.max(-1, Math.min(1, analyze.score)) * 50}% - 5px)`,
            }}
          />
        </div>
      </div>
      <p className="mt-2 text-xs text-foreground-muted">
        회색 괄호 값은 판정에 반영되지 않는 지표(가중치 0)의 신호 상태입니다.
      </p>
    </div>
  );
}
