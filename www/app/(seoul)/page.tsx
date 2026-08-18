"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useChatStore } from "@/lib/store";
import { useUIStore } from "@/lib/uiStore";
import BrandObject from "@/components/seoul/BrandObject";
import ChatInput from "@/components/seoul/ChatInput";
import HomeHistorySidebar from "@/components/seoul/HomeHistorySidebar";
import ProgressCard from "@/components/seoul/ProgressCard";

// placeholder 순환 — 첫 방문자에게 "무엇을 물을 수 있는지"를 칩·카드 없이 알린다(핸드오프 §홈 (a)).
// 칩을 늘리지 않는 것이 이 화면의 결정이다 — 부족하면 이 목록을 손본다.
const PLACEHOLDERS = [
  "성수동 카페 상권 어때요?",
  "삼성전자 지금 어때요?",
  "3000만원으로 시작할 수 있는 동네 알려주세요",
];
const PLACEHOLDER_INTERVAL_MS = 4000;

/**
 * 홈 — 물어보는 자리 하나만 둔다(레퍼런스 Gemini·Grok).
 *
 * 2026-08-16 리뉴얼: ① placeholder 3개 순환 ② 전송 시 입력창이 그 자리에서 진행 스텝
 * 카드로 전환(최대 1.5분 대기를 견디게) ③ 좌측 대화 히스토리 사이드바(접힘 기본)
 * ④ 인사말 위 3D 브랜드 오브젝트(이 화면이 유일한 3D 자리 — 핸드오프 §6).
 * 설명 문구·퀵 칩·카드 목록을 두지 않는 결정은 유지한다.
 */
export default function HomePage() {
  const router = useRouter();
  const messages = useChatStore((s) => s.messages);
  const isLoading = useChatStore((s) => s.isLoading);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const conversationId = useChatStore((s) => s.conversationId);
  const engine = useChatStore((s) => s.engine);
  const draftPrompt = useChatStore((s) => s.draftPrompt);
  const user = useUIStore((s) => s.user);

  // 단일 객체 패턴(REACT_RULES) — placeholder 인덱스와 사이드바 개폐를 한 상태로 둔다
  const [ui, setUi] = useState({ phIndex: 0, sidebarOpen: false });

  useEffect(() => {
    const id = setInterval(
      () => setUi((prev) => ({ ...prev, phIndex: (prev.phIndex + 1) % PLACEHOLDERS.length })),
      PLACEHOLDER_INTERVAL_MS,
    );
    return () => clearInterval(id);
  }, []);

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

  const showProgress = isLoading && engine !== "rom2";

  return (
    <div className="flex-1 min-h-0 flex">
      <HomeHistorySidebar
        open={ui.sidebarOpen}
        onToggle={() => setUi((prev) => ({ ...prev, sidebarOpen: !prev.sidebarOpen }))}
      />

      {/* 배경 그라데이션은 이 화면에만 있다 — 비어 있는 면이 허전하지 않게 잡아주는 역할이고,
          데이터가 놓이는 화면에서는 값 읽기를 방해하므로 쓰지 않는다(DESIGN.md §1). */}
      <div className="flex-1 min-w-0 flex items-center justify-center px-6 py-12 home-glow">
        {/* z-10 — 배경 도트는 .home-glow::before가 z-0으로 깐다 */}
        <div className="relative z-10 w-full max-w-2xl">
          {/* 3D 오브젝트 — 사이드바가 열리면 숨긴다(주의가 둘로 갈리지 않게, 핸드오프 §홈 (e)) */}
          {!ui.sidebarOpen && (
            <div className="hidden sm:block mb-2">
              <BrandObject />
            </div>
          )}

          <h1 className="text-center text-3xl sm:text-4xl font-semibold tracking-tight leading-snug">
            {user ? `${user.name}님, ` : ""}무엇을 알아볼까요?
          </h1>

          <div className="mt-7">
            {showProgress ? (
              <ProgressCard />
            ) : (
              <>
                {/* key — "질문 고치기"로 돌아온 문장을 초기값으로 다시 마운트한다 */}
                <ChatInput
                  key={draftPrompt ?? "fresh"}
                  onSubmit={handleSend}
                  disabled={isLoading}
                  placeholder={PLACEHOLDERS[ui.phIndex]}
                  initialText={draftPrompt ?? ""}
                />
                <p className="mt-2.5 text-center text-xs text-foreground-muted">
                  서울 상권 통계와 주가·뉴스·펀더멘털을 근거로 답해요
                </p>
              </>
            )}
          </div>

          {showProgress && (
            <p className="mt-3 text-center text-xs text-foreground-muted">
              끝나면 결과 화면으로 옮겨갈게요 — 이 화면을 떠나 있어도 돼요
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
