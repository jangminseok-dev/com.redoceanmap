"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { useChatStore } from "@/lib/store";
import { useUIStore } from "@/lib/uiStore";
import ChatInput from "@/components/seoul/ChatInput";

/**
 * 홈 — 물어보는 자리 하나만 둔다(레퍼런스 Gemini·Grok).
 *
 * 예전에는 히어로 문구 + 데이터 설명 한 줄 + 퀵 칩 6개 + 워크스페이스 카드 2개 +
 * 자치구별 상권 8칸이 세로로 쌓여 있었다. 전부 지웠다:
 * - 워크스페이스 카드는 좌측 레일이 이미 하는 일이었다(같은 두 곳으로 가는 링크가 화면에 두 벌)
 * - 자치구별 상권 목록은 `/areas`가 정본이다(레일 → 더보기 → 상권 둘러보기)
 * - 데이터 범위 설명은 물어보기 전에 읽을 이유가 없는 문장이었다
 *
 * 남은 판단: 첫 방문자가 무엇을 물을 수 있는지 화면이 말해주지 않는다. 지금은 placeholder가
 * 그 역할을 한다 — 부족하면 칩을 돌리지 말고 placeholder를 손본다.
 */
export default function HomePage() {
  const router = useRouter();
  const messages = useChatStore((s) => s.messages);
  const isLoading = useChatStore((s) => s.isLoading);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const conversationId = useChatStore((s) => s.conversationId);
  const engine = useChatStore((s) => s.engine);
  const user = useUIStore((s) => s.user);

  // 답변이 도착하면 의도에 맞는 워크스페이스로 이동 — 마운트 시 이미 있던 메시지는 건너뛴다
  const handledRef = useRef<string | null>(messages[messages.length - 1]?.id ?? null);
  useEffect(() => {
    const last = messages[messages.length - 1];
    if (!last || last.role !== "assistant" || handledRef.current === last.id) return;
    handledRef.current = last.id;
    // ROM 2.0 답변은 /rom 챗봇 창이 렌더한다 — 전송 즉시 그리로 옮겨가므로 여기선 아무것도 안 한다
    if (last.engine === "rom2") return;
    const cParam = conversationId ? `&c=${conversationId}` : "";
    if (last.stock) {
      router.push(`/stock?symbol=${encodeURIComponent(last.stock.symbol)}${cParam}`);
    } else if (last.recommendations && last.recommendations.length > 0) {
      router.push(`/market?trdar=${last.recommendations[0].id}${cParam}`);
    } else {
      // 시장 뉴스 등 텍스트만 온 경우 — 주식 워크스페이스 채팅에서 이어간다
      router.push(`/stock?${cParam.replace("&", "")}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  const handleSend = (text: string) => {
    // ROM 2.0은 전용 챗봇 창이 있다 — 질문을 태운 뒤 바로 옮겨가 답변을 거기서 받는다
    if (engine === "rom2") router.push("/rom");
    void sendMessage(text);
  };

  return (
    // 배경 그라데이션은 이 화면에만 있다 — 비어 있는 면이 허전하지 않게 잡아주는 역할이고,
    // 데이터가 놓이는 화면에서는 값 읽기를 방해하므로 쓰지 않는다(DESIGN.md §1).
    <div className="flex-1 flex items-center justify-center px-6 py-12 home-glow">
      {/* z-10 — 배경 도트는 .home-glow::before가 z-0으로 깐다 */}
      <div className="relative z-10 w-full max-w-2xl">
        <h1 className="text-center text-3xl sm:text-4xl font-semibold tracking-tight leading-snug">
          {user ? `${user.name}님, ` : ""}무엇을 알아볼까요?
        </h1>

        <div className="mt-7">
          <ChatInput
            onSubmit={handleSend}
            disabled={isLoading}
            placeholder="상권이나 종목을 물어보세요"
          />
        </div>

        {isLoading && engine !== "rom2" && (
          <div
            className="mt-3 flex items-center gap-2 rounded-xl border border-border bg-surface px-3.5 py-2.5"
            role="status"
          >
            <Sparkles size={15} strokeWidth={2} className="shrink-0 text-brand animate-pulse" />
            <p className="text-sm">분석 중이에요 — 끝나면 결과 화면으로 옮겨갈게요</p>
          </div>
        )}
      </div>
    </div>
  );
}
