"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MessagesSquare } from "lucide-react";
import { fetchAdminQuestions } from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import Empty from "@/components/admin/Empty";
import Kpi from "@/components/admin/Kpi";

const KIND_LABEL: Record<string, string> = {
  market: "상권",
  stock: "종목",
  market_news: "시황",
  nonseoul: "서울외 차단",
  text: "일반/기타",
};

const KIND_BADGE: Record<string, string> = {
  market: "bg-emerald-500/10 text-emerald-600",
  stock: "bg-blue-500/10 text-blue-600",
  market_news: "bg-violet-500/10 text-violet-600",
  nonseoul: "bg-amber-500/10 text-amber-600",
  text: "bg-foreground/5 text-foreground-muted",
};

const DAY_OPTIONS = [7, 30, 90] as const;

export default function QuestionsPage() {
  const [days, setDays] = useState<number>(30);
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-questions", days],
    queryFn: () => fetchAdminQuestions(days, 50),
  });

  const nonseoulTotal = data?.nonseoul_regions.reduce((s, r) => s + r.count, 0) ?? 0;
  const topKind = data?.kinds[0];

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">질문 로그</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            사용자가 무엇을 묻는가 — 수요 신호 (최근 {days}일)
          </p>
        </div>
        <div className="flex gap-1.5">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 h-8 rounded-full text-xs font-medium border ${
                days === d
                  ? "bg-foreground text-background border-foreground"
                  : "bg-surface border-border text-foreground-muted hover:text-foreground"
              }`}
            >
              {d}일
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 sm:gap-4 max-w-xl">
        <Kpi label="질문 수" value={data ? data.total_questions.toLocaleString() : "—"} />
        <Kpi
          label="최다 분기"
          value={topKind ? `${KIND_LABEL[topKind.kind] ?? topKind.kind} ${topKind.share_pct}%` : "—"}
        />
        <Kpi label="서울외 수요" value={data ? `${nonseoulTotal}건` : "—"} />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <section className="rounded-2xl bg-surface border border-border p-5 space-y-3">
          <h2 className="text-sm font-semibold">답변 종류 분포</h2>
          {isPending && <BlockSkeleton rows={4} />}
          {!isPending && data && data.kinds.length === 0 && <Empty msg="기간 내 답변이 없습니다." />}
          {data?.kinds.map((k) => (
            <div key={k.kind} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="font-medium">{KIND_LABEL[k.kind] ?? k.kind}</span>
                <span className="text-foreground-muted">
                  {k.count.toLocaleString()}건 · {k.share_pct}%
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-background overflow-hidden">
                <div
                  className="h-full rounded-full bg-brand"
                  style={{ width: `${Math.min(100, k.share_pct)}%` }}
                />
              </div>
            </div>
          ))}

          <h2 className="text-sm font-semibold pt-3">서울 외 지역 수요</h2>
          <p className="text-xs text-foreground-muted -mt-2">
            가드가 차단한 질문 — 전국 확장 우선순위 근거
          </p>
          {!isPending && data && data.nonseoul_regions.length === 0 && (
            <Empty msg="기간 내 서울 외 질문이 없습니다." />
          )}
          {data?.nonseoul_regions.map((r) => (
            <div key={r.region} className="flex justify-between text-xs">
              <span className="font-medium">{r.region}</span>
              <span className="text-foreground-muted">{r.count}건</span>
            </div>
          ))}
        </section>

        <section className="lg:col-span-2 rounded-2xl bg-surface border border-border overflow-hidden">
          {isPending && <BlockSkeleton rows={6} />}
          {isError && <Empty msg="질문 로그를 불러오지 못했습니다." />}
          {!isPending && !isError && (data?.recent.length ?? 0) === 0 && (
            <Empty msg="아직 질문이 없습니다." />
          )}
          {(data?.recent.length ?? 0) > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-foreground-muted border-b border-border bg-background/60">
                  <th className="font-medium px-5 py-2.5">질문</th>
                  <th className="font-medium px-5 py-2.5">답변</th>
                  <th className="font-medium px-5 py-2.5 text-right">시각</th>
                </tr>
              </thead>
              <tbody>
                {data?.recent.map((q) => (
                  <tr
                    key={`${q.conversation_id}-${q.asked_at}`}
                    className="border-b border-border last:border-0 hover:bg-background/40"
                  >
                    <td className="px-5 py-3">
                      <span className="inline-flex items-start gap-1.5">
                        <MessagesSquare size={13} className="mt-0.5 shrink-0 text-foreground-muted" />
                        <span className="line-clamp-2">{q.question}</span>
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                          KIND_BADGE[q.answer_kind] ?? KIND_BADGE.text
                        }`}
                      >
                        {KIND_LABEL[q.answer_kind] ?? q.answer_kind}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right text-xs text-foreground-muted whitespace-nowrap">
                      {new Date(q.asked_at).toLocaleString("ko-KR", {
                        month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit",
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}
