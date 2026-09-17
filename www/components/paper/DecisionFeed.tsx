"use client";

import { ExternalLink } from "lucide-react";
import type { PaperDecision } from "@/lib/types";
import { ACTION_LABEL, ACTION_TONE, fmtPct, fmtPrice } from "./format";

const DIRECTION_LABEL: Record<string, string> = { UP: "상승", DOWN: "하락", NEUTRAL: "중립", NONE: "—" };
const REASON_LABEL: Record<string, string> = { news: "뉴스", indicator: "지표", mixed: "뉴스+지표", none: "근거 없음" };

/** 하루치 판단 — 시장 관점·주문(이유·인용)·거부·체결·채점·후보. 인용 기사는 제목 링크로 붙는다. */
export default function DecisionFeed({ decision }: { decision: PaperDecision | null }) {
  if (!decision) {
    return <p className="text-sm text-foreground-muted">이 날짜의 판단 기록이 없습니다.</p>;
  }
  const newsById = new Map(decision.candidates.flatMap((c) => c.news.map((n) => [n.news_id, n] as const)));
  const candidateOf = (ticker: string) => decision.candidates.find((c) => c.ticker === ticker);
  const scoreOf = (ticker: string) => decision.scores.find((s) => s.ticker === ticker);
  const fillOf = (ticker: string, action: string) => decision.fills.find((f) => f.ticker === ticker && f.action === action);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <p className="text-sm leading-relaxed">
          <span className="font-semibold">시장 관점 </span>
          {decision.market_view || "(없음)"}
        </p>
        {decision.replayed && (
          <span className="rounded-full bg-border/40 px-2 py-0.5 text-[11px] text-foreground-muted">리플레이</span>
        )}
        <span className="text-[11px] text-foreground-muted tabular-nums">응답 {(decision.latency_ms / 1000).toFixed(1)}초</span>
      </div>

      {decision.orders.length === 0 ? (
        <p className="text-sm text-foreground-muted">주문 없음 — 이날은 관망했습니다.</p>
      ) : (
        <ul className="space-y-2">
          {decision.orders.map((o) => {
            const cand = candidateOf(o.ticker);
            const fill = fillOf(o.ticker, o.action);
            const score = scoreOf(o.ticker);
            return (
              <li key={`${o.ticker}-${o.action}`} className="rounded-xl border border-border bg-surface p-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${ACTION_TONE[o.action]}`}>
                    {ACTION_LABEL[o.action]}
                  </span>
                  <span className="font-semibold">{o.ticker}</span>
                  {cand && <span className="text-xs text-foreground-muted">{cand.name}</span>}
                  {o.weight > 0 && <span className="text-xs text-foreground-muted tabular-nums">비중 {Math.round(o.weight * 100)}%</span>}
                  <span className="ml-auto rounded-full bg-border/40 px-2 py-0.5 text-[11px] text-foreground-muted">
                    근거 {REASON_LABEL[o.reason_kind] ?? o.reason_kind}
                  </span>
                </div>
                <p className="mt-1.5 text-sm leading-relaxed">{o.reason}</p>
                {/* 인용 — 프롬프트에 제시된 id만 통과한 것이라 여기 보이는 기사는 전부 실제 근거다 */}
                {(o.cites.news_ids.length > 0 || o.cites.signals.length > 0) && (
                  <ul className="mt-2 space-y-1 text-xs text-foreground-muted">
                    {o.cites.news_ids.map((id) => {
                      const n = newsById.get(id);
                      if (!n) return null;
                      return (
                        <li key={id} className="flex items-start gap-1.5">
                          <span className="shrink-0">📰</span>
                          <span>
                            {n.url ? (
                              <a href={n.url} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline text-foreground">
                                {n.title} <ExternalLink size={11} className="inline" />
                              </a>
                            ) : (
                              <span className="text-foreground">{n.title}</span>
                            )}
                            {n.sentiment != null && <span className="ml-1 tabular-nums">감성 {n.sentiment >= 0 ? "+" : ""}{n.sentiment.toFixed(2)}</span>}
                            {n.event_type && <span className="ml-1">· {n.event_type}</span>}
                          </span>
                        </li>
                      );
                    })}
                    {o.cites.signals.length > 0 && cand && (
                      <li className="flex items-start gap-1.5">
                        <span className="shrink-0">📊</span>
                        <span>
                          스냅샷 {DIRECTION_LABEL[cand.direction]}
                          {cand.score != null && ` (score ${cand.score >= 0 ? "+" : ""}${cand.score.toFixed(2)})`}
                          {cand.up_rate != null && ` · 과거 같은 신호 적중 ${Math.round(cand.up_rate * 100)}%`}
                          {cand.baseline_up_rate != null && ` / 평소 ${Math.round(cand.baseline_up_rate * 100)}%`}
                          {!cand.ready && " · 통계적 유의성 미달"}
                        </span>
                      </li>
                    )}
                  </ul>
                )}
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-foreground-muted tabular-nums">
                  {fill ? (
                    <span>체결 {fmtPrice(fill.price, fill.ticker)} × {fill.quantity}주</span>
                  ) : (
                    <span>체결 대기(다음 세션 시가) 또는 미체결</span>
                  )}
                  {score && (
                    <span className={score.hit ? "text-up" : "text-down"}>
                      5거래일 뒤 {fmtPct(score.realized_return_pct)} · {score.hit ? "적중" : "빗나감"}
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {decision.rejected.length > 0 && (
        <details className="text-xs text-foreground-muted">
          <summary className="cursor-pointer select-none">거부된 주문 {decision.rejected.length}건 — 후보 밖 종목·환각 인용·한도 위반</summary>
          <ul className="mt-1.5 space-y-0.5 pl-3">
            {decision.rejected.map((r, i) => (
              <li key={i}>{r.ticker} {r.action}: {r.reason}</li>
            ))}
          </ul>
        </details>
      )}

      <details className="text-xs">
        <summary className="cursor-pointer select-none text-foreground-muted">
          이날 AI가 본 후보 {decision.candidates.length}종목
        </summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-foreground-muted border-b border-border">
                <th className="py-1.5 pr-2 font-medium">종목</th>
                <th className="py-1.5 pr-2 font-medium">신호</th>
                <th className="py-1.5 pr-2 font-medium text-right">5일</th>
                <th className="py-1.5 pr-2 font-medium text-right">3일 감성</th>
                <th className="py-1.5 font-medium text-right">뉴스</th>
              </tr>
            </thead>
            <tbody>
              {decision.candidates.map((c) => (
                <tr key={c.ticker} className="border-b border-border last:border-0">
                  <td className="py-1.5 pr-2 font-medium">{c.ticker} <span className="text-foreground-muted">{c.name}</span></td>
                  <td className="py-1.5 pr-2">{DIRECTION_LABEL[c.direction]}{c.earnings_veto ? " · 실적 임박" : ""}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{fmtPct(c.return_5d_pct)}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{c.sentiment_3d == null ? "—" : c.sentiment_3d.toFixed(2)}</td>
                  <td className="py-1.5 text-right tabular-nums">{c.news.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
