"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { MessageSquare, ChevronRight } from "lucide-react";
import { fetchConversations } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import { useUIStore } from "@/lib/uiStore";
import { Button } from "@/components/ui/button";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ko-KR", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function HistoryPage() {
  const router = useRouter();
  const user = useUIStore((s) => s.user);
  const openAuth = useUIStore((s) => s.openAuth);
  const loadConversation = useChatStore((s) => s.loadConversation);
  const [openingId, setOpeningId] = useState<number | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => fetchConversations(),
    enabled: !!user,
  });

  const open = async (id: number) => {
    if (openingId !== null) return;
    setOpeningId(id);
    try {
      const raw = await loadConversation(id);
      // 마지막 구조화 카드 기준으로 이동할 워크스페이스 결정
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

  if (!user) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-6">
        <MessageSquare size={36} className="text-foreground-muted" strokeWidth={1.5} />
        <p className="text-sm text-foreground-muted">
          지난 대화를 보려면 로그인이 필요해요.
        </p>
        <Button
          type="button"
          onClick={() => openAuth("login")}
          
        >
          로그인
        </Button>
      </div>
    );
  }

  return (
    <div className="flex-1 px-6 py-8">
      <div className="w-full max-w-2xl mx-auto">
        <h1 className="text-lg font-semibold flex items-center gap-2 mb-5">
          <MessageSquare size={18} className="text-brand" strokeWidth={2} />
          지난 대화
        </h1>

        {isLoading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="skeleton h-16 rounded-xl" />
            ))}
          </div>
        )}
        {isError && (
          <p className="text-sm text-foreground-muted">대화 목록을 불러오지 못했습니다.</p>
        )}
        {data && data.length === 0 && (
          <p className="text-sm text-foreground-muted">
            아직 대화가 없어요. 홈에서 질문을 시작해보세요.
          </p>
        )}

        <ul className="flex flex-col gap-2">
          {data?.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => void open(c.id)}
                disabled={openingId !== null}
                className="w-full flex items-center gap-3 text-left bg-surface border border-border rounded-xl px-4 py-3.5 hover:border-brand/40 transition-colors disabled:opacity-60"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{c.title}</p>
                  <p className="text-xs text-foreground-muted mt-0.5">{formatDate(c.createdAt)}</p>
                </div>
                {openingId === c.id ? (
                  <span className="text-xs text-foreground-muted animate-pulse shrink-0">여는 중…</span>
                ) : (
                  <ChevronRight size={16} className="text-foreground-muted shrink-0" />
                )}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
