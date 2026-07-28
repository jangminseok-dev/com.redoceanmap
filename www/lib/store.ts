import { create } from "zustand";
import type { Area, ConversationMessage, NewsCardItem, StockAnalysis } from "./types";
import { fetchConversationMessages } from "./api";
import { tryRefreshSession } from "./authApi";
import { useUIStore } from "./uiStore";

export type { StockAnalysis } from "./types"; // 기존 임포트 호환 재수출

/** ROM 1.0 = 기존 chat 파이프라인, ROM 2.0 = 허브 랭체인 게이트웨이(시멘틱 분류 → LCEL 체인). */
export type ChatEngine = "rom1" | "rom2";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  recommendations?: Area[];
  stock?: StockAnalysis;
  news?: NewsCardItem[];
};

type ChatState = {
  messages: Message[];
  recommendations: Area[];
  conversationId: number | null;
  engine: ChatEngine;
  langchainSessionId: number | null;
  isLoading: boolean;
  setEngine: (engine: ChatEngine) => void;
  sendMessage: (prompt: string) => Promise<void>;
  loadConversation: (id: number) => Promise<ConversationMessage[]>;
  reset: () => void;
};

/** 액세스 토큰 만료(60분) → 리프레시 회전 후 1회 재시도. 두 엔진이 같은 규칙을 쓴다. */
async function postWithAuth(url: string, body: unknown): Promise<Response> {
  const request = () =>
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  const res = await request();
  if (res.status === 401 && (await tryRefreshSession())) return request();
  return res;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  recommendations: [],
  conversationId: null,
  engine: "rom1",
  langchainSessionId: null,
  isLoading: false,
  setEngine: (engine) => set({ engine }),
  sendMessage: async (prompt) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: prompt,
    };
    set((s) => ({ messages: [...s.messages, userMsg], isLoading: true }));

    try {
      const engine = get().engine;
      // ROM 2.0은 허브 랭체인 게이트웨이 직결(rewrites 프록시). 세션 id로 대화가 이어진다.
      const res =
        engine === "rom2"
          ? await postWithAuth("/api/backend/langchain-semantic/ask", {
              prompt,
              sessionId: get().langchainSessionId,
            })
          : await postWithAuth("/api/chat", {
              prompt,
              conversationId: get().conversationId,
            });
      if (res.status === 401) {
        useUIStore.getState().openAuth("login");
        const loginMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "로그인 후 이용할 수 있어요. 로그인 창을 열어드렸으니 로그인하고 다시 물어봐 주세요.",
        };
        set((s) => ({ messages: [...s.messages, loginMsg], isLoading: false }));
        return;
      }
      if (!res.ok) throw new Error("AI 응답 오류");

      if (engine === "rom2") {
        // 랭체인 응답은 텍스트 한 덩어리다 — 카드(추천/종목)는 ROM 1.0만 만든다
        const data: { sessionId: number; answer: string } = await res.json();
        const aiMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.answer,
        };
        set((s) => ({
          messages: [...s.messages, aiMsg],
          langchainSessionId: data.sessionId,
          isLoading: false,
        }));
        return;
      }

      const data: {
        text: string;
        recommendations: Area[];
        conversationId: number;
        stock?: StockAnalysis | null;
        news?: NewsCardItem[];
      } = await res.json();

      const aiMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.text,
        recommendations: data.recommendations,
        stock: data.stock ?? undefined,
        news: data.news?.length ? data.news : undefined,
      };
      set((s) => ({
        messages: [...s.messages, aiMsg],
        recommendations: data.recommendations,
        conversationId: data.conversationId,
        isLoading: false,
      }));
    } catch {
      const errMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "죄송해요, 일시적인 오류가 발생했어요. 잠시 후 다시 시도해주세요.",
      };
      set((s) => ({ messages: [...s.messages, errMsg], isLoading: false }));
    }
  },
  // 지난 대화 복원 — payload(추천/종목 카드)까지 되살린다. 원본 목록을 반환해
  // 호출부(히스토리 페이지)가 이동할 워크스페이스를 결정하게 한다.
  loadConversation: async (id) => {
    set({ isLoading: true });
    try {
      const raw = await fetchConversationMessages(id);
      const messages: Message[] = raw.map((m) => ({
        id: crypto.randomUUID(),
        role: m.role,
        content: m.content,
        recommendations: m.payload?.recommendations,
        stock: m.payload?.stock,
        news: m.payload?.news,
      }));
      const lastRecommendations =
        [...raw].reverse().find((m) => m.payload?.recommendations?.length)?.payload
          ?.recommendations ?? [];
      set({
        messages,
        recommendations: lastRecommendations,
        conversationId: id,
        isLoading: false,
      });
      return raw;
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },
  reset: () =>
    set({
      messages: [],
      recommendations: [],
      conversationId: null,
      langchainSessionId: null,
      isLoading: false,
    }),
}));
