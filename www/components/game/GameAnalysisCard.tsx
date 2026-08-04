"use client";

import { TriangleAlert } from "lucide-react";
import type { GameSymbolAnalysis } from "@/lib/types";

// 부호 규약: 양수 = 뜨겁다. 한국 관례대로 뜨거운 쪽이 빨강이다.
const HOT = "#DC2626";
const COLD = "#2563EB";

const LABEL_TONE: Record<string, string> = {
  과열: "text-up",
  달아오름: "text-up",
  잠잠: "text-foreground-muted",
  "식는 중": "text-down",
  침체: "text-down",
};

const fmt = (v: number | null, digits = 2, suffix = "") =>
  v === null ? "—" : `${v.toFixed(digits)}${suffix}`;

/**
 * 종목 상태 요약 카드.
 *
 * ⚠️ **예측이 아니다.** 이 게임의 주가는 브라운 운동 + 뉴스 충격으로 만든 값이라 과거
 * 형태에 미래 정보가 없다. 그래서 "오른다/내린다"가 아니라 "지금 뜨겁다/차갑다"만 말하고,
 * 그 고지를 카드 안에 함께 둔다(차트 패턴의 note와 같은 규칙).
 */
export default function GameAnalysisCard({
  analysis,
  className = "",
}: {
  analysis: GameSymbolAnalysis;
  className?: string;
}) {
  const tone = LABEL_TONE[analysis.label] ?? "text-foreground";

  return (
    <section className={`rounded-2xl border border-border bg-surface p-5 ${className}`}>
      <div className="flex items-baseline gap-2">
        <h3 className="text-sm font-bold tracking-tight">지금 상태</h3>
        <span className={`ml-auto text-lg font-bold ${tone}`}>{analysis.label}</span>
        <span className="text-xs text-foreground-muted tabular-nums">
          {analysis.score >= 0 ? "+" : ""}
          {analysis.score.toFixed(2)}
        </span>
      </div>

      {/* 축 분해 — 점수만 보여주면 근거가 사라진다. 0을 가운데 둔 양방향 막대다 */}
      <ul className="mt-4 space-y-2.5">
        {analysis.axes.map((a) => {
          const pct = Math.abs(a.value) * 50; // 반쪽 폭 기준
          const color = a.value >= 0 ? HOT : COLD;
          return (
            <li key={a.key} className="text-xs">
              <div className="flex items-center gap-2">
                <span className="w-16 shrink-0 text-foreground-muted">
                  {a.label}
                  <span className="ml-1 opacity-60 tabular-nums">×{a.weight.toFixed(2)}</span>
                </span>
                <span className="relative flex-1 h-1.5 rounded-full bg-black/[0.06]">
                  {/* 가운데 기준선 */}
                  <span className="absolute left-1/2 top-[-2px] h-[10px] w-px bg-black/20" />
                  <span
                    className="absolute top-0 h-full rounded-full"
                    style={{
                      background: color,
                      width: `${pct}%`,
                      left: a.value >= 0 ? "50%" : `${50 - pct}%`,
                    }}
                  />
                </span>
                <span className="w-10 text-right tabular-nums" style={{ color }}>
                  {a.value >= 0 ? "+" : ""}
                  {a.value.toFixed(2)}
                </span>
              </div>
              <p className="mt-1 pl-[4.5rem] text-foreground-muted leading-relaxed">{a.note}</p>
            </li>
          );
        })}
      </ul>

      {/* 지표 원값 — 요약이 어떤 숫자에서 나왔는지 그대로 보여준다 */}
      <dl className="mt-4 pt-3 border-t border-border grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-2 text-xs">
        <div>
          <dt className="text-foreground-muted">RSI (14)</dt>
          <dd className="tabular-nums font-medium">{fmt(analysis.rsi, 1)}</dd>
        </div>
        <div>
          <dt className="text-foreground-muted">볼린저 위치</dt>
          <dd className="tabular-nums font-medium">{fmt(analysis.percentB)}</dd>
        </div>
        <div>
          <dt className="text-foreground-muted">변동성 (ATR)</dt>
          <dd className="tabular-nums font-medium">{fmt(analysis.atrPct, 2, "%")}</dd>
        </div>
        <div>
          <dt className="text-foreground-muted">거래량비</dt>
          <dd className="tabular-nums font-medium">{fmt(analysis.volumeRatio)}배</dd>
        </div>
        <div>
          <dt className="text-foreground-muted">OBV 기울기</dt>
          <dd className="tabular-nums font-medium">{fmt(analysis.obvSlope, 3)}</dd>
        </div>
        <div>
          <dt className="text-foreground-muted">뉴스 {analysis.headlineCount}건</dt>
          <dd
            className="tabular-nums font-medium"
            style={{ color: analysis.newsImpactPct >= 0 ? HOT : COLD }}
          >
            {analysis.newsImpactPct >= 0 ? "+" : ""}
            {analysis.newsImpactPct.toFixed(2)}%
          </dd>
        </div>
      </dl>

      {/* 일봉에서 관측된 형태 */}
      {analysis.dailyPatterns.length > 0 && (
        <div className="mt-4 pt-3 border-t border-border">
          <p className="text-xs font-semibold">일봉에서 보이는 형태</p>
          <ul className="mt-2 space-y-1.5">
            {analysis.dailyPatterns.map((p) => (
              <li key={p.name} className="text-xs leading-relaxed">
                <span className="font-medium">{p.label}</span>
                <span className="ml-1.5 text-foreground-muted tabular-nums">
                  근접도 {(p.confidence * 100).toFixed(0)}%
                </span>
                <span className="block text-foreground-muted">{p.note}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-4 flex items-start gap-1.5 text-xs text-foreground-muted leading-relaxed">
        <TriangleAlert size={13} strokeWidth={2} className="mt-0.5 shrink-0 text-amber-600" />
        <span>
          <b>예측이 아닙니다.</b> 이 게임의 주가는 난수(브라운 운동)에 뉴스 충격을 더해
          만들어지므로 과거 형태에 미래 정보가 담겨 있지 않습니다. 위 요약은 &ldquo;지금 얼마나
          뜨거운가&rdquo;를 말할 뿐이며, 점수가 높다고 오를 확률이 높다는 뜻이 아닙니다.
        </span>
      </p>
    </section>
  );
}
