"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, MapPin, MessageSquare, Plus } from "lucide-react";
import Link from "next/link";
import { fetchConversations } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import { useUIStore } from "@/lib/uiStore";
import type { ConversationSummary } from "@/lib/types";

const DAY_MS = 86_400_000;

// 시간 그룹 — "언제 했더라"로 찾는 목록이라 날짜보다 그룹이 먼저다(레퍼런스 Gemini 사이드바)
function groupOf(iso: string): "오늘" | "이번 주" | "이전" {
  const t = Date.parse(iso);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (t >= startOfToday) return "오늘";
  if (t >= startOfToday - 6 * DAY_MS) return "이번 주";
  return "이전";
}

/**
 * 홈 히스토리 사이드바 — 접힘(44px 스트립)이 기본, 펼치면 260px(핸드오프 §홈 (d)).
 * 데스크탑 전용이다 — 모바일에서는 더보기 → 지난 대화가 같은 역할을 한다.
 */
export default function HomeHistorySidebar({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  const router = useRouter();
  const user = useUIStore((s) => s.user);
  const loadConversation = useChatStore((s) => s.loadConversation);
  const reset = useChatStore((s) => s.reset);
  const [openingId, setOpeningId] = useState<number | null>(null);

  const { data } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => fetchConversations(),
    enabled: !!user && open,
  });

  // 히스토리 페이지와 같은 재개 규칙 — 마지막 카드 기준으로 워크스페이스를 고른다
  const openConversation = async (id: number) => {
    if (openingId !== null) return;
    setOpeningId(id);
    try {
      const raw = await loadConversation(id);
      const lastPayload = [...raw].reverse().find((m) => m.payload)?.payload;
      if (lastPayload?.stock) {
        router.push(`/stock?symbol=${encodeURIComponent(lastPayload.stock.symbol)}&c=${id}`);
      } else if (lastPayload?.recommendations?.length) {
        router.push(`/market?trdar=${lastPayload.recommendations[0].id}&c=${id}`);
      } else {
        router.push(`/stock?c=${id}`);
      }
    } catch {
      setOpeningId(null);
    }
  };

  const groups = (data ?? []).reduce<Record<string, ConversationSummary[]>>((acc, c) => {
    const g = groupOf(c.createdAt);
    (acc[g] ??= []).push(c);
    return acc;
  }, {});

  return (
    <aside
      aria-label="지난 대화"
      className={`hidden lg:flex flex-col shrink-0 border-r border-border bg-surface overflow-hidden transition-[width] duration-[280ms] ease-[cubic-bezier(0.22,1,0.36,1)] ${
        open ? "w-[260px]" : "w-11"
      }`}
    >
      {!open ? (
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={false}
          title="지난 대화 열기"
          className="flex-1 flex flex-col items-center gap-2 pt-4 text-foreground-muted hover:bg-accent hover:text-foreground transition-colors"
        >
          <MessageSquare size={17} strokeWidth={1.75} />
          <ChevronRight size={15} strokeWidth={1.75} />
        </button>
      ) : (
        <>
          <div className="shrink-0 flex items-center justify-between gap-2 px-3 h-12 border-b border-border">
            <span className="text-sm font-semibold">대화</span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={reset}
                className="inline-flex items-center gap-1 h-8 px-2.5 rounded-xl bg-accent text-brand text-xs font-medium hover:bg-border/60 transition-colors"
              >
                <Plus size={13} strokeWidth={2.25} />새 질문
              </button>
              <button
                type="button"
                onClick={onToggle}
                aria-expanded
                aria-label="사이드바 접기"
                className="grid place-items-center w-8 h-8 rounded-full text-foreground-muted hover:bg-accent"
              >
                <ChevronLeft size={15} />
              </button>
            </div>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto px-2 py-2">
            {!user && (
              <p className="px-2 py-4 text-xs text-foreground-muted leading-relaxed">
                로그인하면 지난 대화가 여기에 쌓여요.
              </p>
            )}
            {user && data && data.length === 0 && (
              <p className="px-2 py-4 text-xs text-foreground-muted leading-relaxed">
                아직 대화가 없어요. 오른쪽 입력창에서 시작해보세요.
              </p>
            )}
            {(["오늘", "이번 주", "이전"] as const).map(
              (g) =>
                groups[g]?.length > 0 && (
                  <div key={g} className="mb-2">
                    <p className="px-2 py-1.5 text-xs text-foreground-muted">{g}</p>
                    {groups[g].map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => void openConversation(c.id)}
                        disabled={openingId !== null}
                        className="w-full flex items-center gap-2 px-2 py-2 rounded-xl text-left hover:bg-accent transition-colors disabled:opacity-60"
                      >
                        {/* 도메인 마크 — 상권은 핀, 주식은 심볼 초성, 카드 없는 대화는 제목 초성 */}
                        <span
                          aria-hidden
                          className="grid place-items-center w-[18px] h-[18px] shrink-0 rounded-full bg-accent text-brand text-[10px] font-bold"
                        >
                          {c.domain === "market" ? (
                            <MapPin size={10} strokeWidth={2.5} />
                          ) : (
                            (c.label ?? c.title).trim().charAt(0) || "?"
                          )}
                        </span>
                        <span className="flex-1 min-w-0 text-[13px] truncate">{c.title}</span>
                        {openingId === c.id && (
                          <span className="shrink-0 text-xs text-foreground-muted animate-pulse">
                            여는 중…
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                ),
            )}
          </div>

          <div className="shrink-0 border-t border-border px-3 py-2.5">
            <Link
              href="/history"
              className="text-xs font-medium text-brand hover:underline underline-offset-2"
            >
              전체 보기 →
            </Link>
          </div>
        </>
      )}
    </aside>
  );
}
