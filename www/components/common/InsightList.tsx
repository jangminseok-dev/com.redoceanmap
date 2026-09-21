"use client";

import { useState } from "react";
import { AlertTriangle, Lightbulb, ThumbsUp } from "lucide-react";
import type { Insight } from "@/lib/types";
import { Button } from "@/components/ui/button";

const TONE = {
  positive: { icon: ThumbsUp, className: "text-emerald-600" },
  neutral: { icon: Lightbulb, className: "text-foreground-muted" },
  warning: { icon: AlertTriangle, className: "text-amber-600" },
} as const;

// limit을 줬을 때의 노출 순서 — 주의·강점이 전구(중립) 문장에 묻히지 않게 앞으로 올린다
const TONE_RANK: Record<string, number> = { warning: 0, positive: 1, neutral: 2 };

/** 규칙 기반 해석 문장 리스트 — market·stock 공용.
 *  limit을 주면 그만큼만 보이고 나머지는 "더 보기"로 접는다(2026-09-21: 상권 상세에 같은 크기 문장 17개가
 *  한꺼번에 떠서 뭐가 중요한지 화면이 말해 주지 않았다). limit이 없으면 전부 그대로 보인다. */
export default function InsightList({ insights, limit }: { insights: Insight[]; limit?: number }) {
  const [expanded, setExpanded] = useState(false);
  if (insights.length === 0) return null;
  const ordered =
    limit === undefined
      ? insights
      : [...insights].sort((a, b) => (TONE_RANK[a.tone] ?? 2) - (TONE_RANK[b.tone] ?? 2));
  const folded = limit !== undefined && ordered.length > limit;
  const shown = folded && !expanded ? ordered.slice(0, limit) : ordered;
  return (
    <div>
      <ul className="flex flex-col gap-1.5">
        {shown.map((i) => {
          const tone = TONE[i.tone] ?? TONE.neutral;
          const Icon = tone.icon;
          return (
            <li key={i.key} className="flex items-start gap-2 text-sm leading-snug">
              <Icon size={14} strokeWidth={2} className={`mt-0.5 shrink-0 ${tone.className}`} />
              <span>{i.text}</span>
            </li>
          );
        })}
      </ul>
      {folded && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-1 -ml-3 text-foreground-muted"
        >
          {expanded ? "접기" : `더 보기 (${ordered.length - limit}개)`}
        </Button>
      )}
    </div>
  );
}
