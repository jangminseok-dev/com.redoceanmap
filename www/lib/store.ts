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
  /** 이 답변을 만든 엔진. 화면 이동 여부를 답변 시점 기준으로 판정한다(그 뒤 셀렉터를 바꿔도 안전). */
  engine?: ChatEngine;
  /** 말풍선에 찍는 시각(epoch ms). 지난 대화 복원분은 없다. */
  createdAt?: number;
};

type ChatState = {
  messages: Message[];
  recommendations: Area[];
  conversationId: number | null;
  engine: ChatEngine;
  langchainSessionId: number | null;
  isLoading: boolean;
  /** 진행 단계 라벨(SSE) — phase 왕복(p95 ~1.5분) 동안 "분석 중…" 대신 지금 뭘 하는지 보여준다 */
  loadingStage: string | null;
  /** 진행 단계 키(intent·select·data·narrate…) — 홈 진행 카드가 4스텝 인덱스로 매핑한다 */
  loadingStageKey: string | null;
  /** 질문 전송 시각(epoch ms) — 진행 카드의 경과 표시용 */
  askStartedAt: number | null;
  /** "질문 고치기"로 중단한 질문 — 입력창이 이 텍스트로 복원한다 */
  draftPrompt: string | null;
  setEngine: (engine: ChatEngine) => void;
  sendMessage: (prompt: string) => Promise<void>;
  /** 진행 중인 질문 중단 — 보낸 말풍선을 걷어 draftPrompt로 되돌린다(홈 "질문 고치기") */
  abortAsk: () => void;
  loadConversation: (id: number) => Promise<ConversationMessage[]>;
  reset: () => void;
};

/** 액세스 토큰 만료(60분) → 리프레시 회전 후 1회 재시도. 두 엔진이 같은 규칙을 쓴다. */
async function postWithAuth(url: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  const request = () =>
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  const res = await request();
  if (res.status === 401 && (await tryRefreshSession())) return request();
  return res;
}

// 진행 중인 ask의 중단 핸들 — 상태가 아니라 부수 장치라 스토어 밖에 둔다(직렬화 불필요)
let askController: AbortController | null = null;

type AskData = {
  text: string;
  recommendations: Area[];
  conversationId: number;
  stock?: StockAnalysis | null;
  news?: NewsCardItem[];
};

type AskOutcome =
  | { ok: true; data: AskData }
  | { ok: false; status: number; message: string };

/** /chat/ask/progress SSE 소비 — stage 이벤트는 콜백으로, 종결(result|error)은 반환값으로.
 *  오류도 본문 이벤트로 온다(SSE는 이미 200) — HTTP 상태만 보면 실패를 놓친다. */
async function consumeAskProgress(
  res: Response,
  onStage: (stage: string, label: string) => void,
): Promise<AskOutcome> {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let final: AskOutcome | null = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const event = JSON.parse(line.slice(6)) as
        | { type: "stage"; stage: string; label: string }
        | { type: "result"; data: AskData }
        | { type: "error"; status: number; message: string };
      if (event.type === "stage") onStage(event.stage, event.label);
      else if (event.type === "result") final = { ok: true, data: event.data };
      else final = { ok: false, status: event.status, message: event.message };
    }
  }
  return final ?? { ok: false, status: 500, message: "응답이 중간에 끊겼어요." };
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  recommendations: [],
  conversationId: null,
  engine: "rom1",
  langchainSessionId: null,
  isLoading: false,
  loadingStage: null,
  loadingStageKey: null,
  askStartedAt: null,
  draftPrompt: null,
  setEngine: (engine) => set({ engine }),
  sendMessage: async (prompt) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: prompt,
      createdAt: Date.now(),
    };
    askController = new AbortController();
    set((s) => ({
      messages: [...s.messages, userMsg],
      isLoading: true,
      askStartedAt: Date.now(),
      draftPrompt: null,
    }));

    try {
      const engine = get().engine;
      // ROM 2.0은 허브 랭체인 게이트웨이 직결(rewrites 프록시). 세션 id로 대화가 이어진다.
      // ROM 1.0은 진행 단계 SSE(/chat/ask/progress) — phase 왕복 동안 화면이 침묵하지 않게.
      const res =
        engine === "rom2"
          ? await postWithAuth(
              "/api/backend/langchain-semantic/ask",
              { prompt, sessionId: get().langchainSessionId },
              askController.signal,
            )
          : await postWithAuth(
              "/api/backend/chat/ask/progress",
              { prompt, conversationId: get().conversationId },
              askController.signal,
            );
      if (res.status === 401) {
        useUIStore.getState().openAuth("login");
        const loginMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "로그인 후 이용할 수 있어요. 로그인 창을 열어드렸으니 로그인하고 다시 물어봐 주세요.",
        };
        set((s) => ({ messages: [...s.messages, loginMsg], isLoading: false, loadingStage: null }));
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
          engine: "rom2",
          createdAt: Date.now(),
        };
        set((s) => ({
          messages: [...s.messages, aiMsg],
          langchainSessionId: data.sessionId,
          isLoading: false,
          loadingStage: null,
        }));
        return;
      }

      if (!res.body) throw new Error("AI 응답 오류");
      const outcome = await consumeAskProgress(res, (stage, label) =>
        set({ loadingStage: label, loadingStageKey: stage }),
      );
      if (!outcome.ok) {
        // 백엔드가 사람이 읽는 사유를 준다(서울 외 준비중·상권 미발견 등) — 그대로 보여준다
        const errMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: outcome.message,
        };
        set((s) => ({ messages: [...s.messages, errMsg], isLoading: false, loadingStage: null }));
        return;
      }
      const data = outcome.data;

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
        loadingStage: null,
      }));
    } catch (error) {
      // "질문 고치기"로 중단한 경우 — abortAsk가 이미 상태를 되돌렸으므로 오류 말풍선을 만들지 않는다
      if (error instanceof DOMException && error.name === "AbortError") return;
      const errMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "죄송해요, 일시적인 오류가 발생했어요. 잠시 후 다시 시도해주세요.",
      };
      set((s) => ({ messages: [...s.messages, errMsg], isLoading: false, loadingStage: null }));
    } finally {
      askController = null;
      set({ loadingStageKey: null, askStartedAt: null });
    }
  },
  abortAsk: () => {
    if (!get().isLoading) return;
    askController?.abort();
    // 방금 보낸 말풍선을 걷어 입력창으로 되돌린다 — 사용자가 문장을 고쳐 다시 보낸다
    set((s) => {
      const last = s.messages[s.messages.length - 1];
      const isPendingUser = last?.role === "user";
      return {
        messages: isPendingUser ? s.messages.slice(0, -1) : s.messages,
        draftPrompt: isPendingUser ? last.content : null,
        isLoading: false,
        loadingStage: null,
        loadingStageKey: null,
        askStartedAt: null,
      };
    });
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
      set({ isLoading: false, loadingStage: null });
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
      loadingStage: null,
      loadingStageKey: null,
      askStartedAt: null,
      draftPrompt: null,
    }),
}));
