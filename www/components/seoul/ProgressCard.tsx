"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { useChatStore } from "@/lib/store";

// 백엔드 chat_interactor의 stage 키 → 4스텝 인덱스.
// 흐름별로 중간 키가 다르다(상권: select→data→narrate · 주식: analyze→narrate · 뉴스: search→narrate).
// 매핑에 없는 키는 마지막으로 본 스텝을 유지한다 — 새 스텝이 생겨도 카드가 깨지지 않는다.
const STEP_OF_STAGE: Record<string, number> = {
  intent: 0,
  select: 1,
  search: 1,
  analyze: 1,
  data: 2,
  answer: 3,
  narrate: 3,
};

const STEPS = ["의도 분류", "데이터 조회", "근거 생성", "서술"] as const;

// 평균 응답 시간 안내 — 백엔드 phase 왕복 p95 ~1.5분에서 온 값
const TYPICAL_LABEL = "보통 1분 30초 안에 끝나요";

// 백엔드 chat_router의 대기열 stage 키 — 앞선 질문이 끝나길 기다리는 중이라 아직 어느 스텝도 시작하지 않았다
const QUEUED_STAGE = "queued";

/**
 * 홈 진행 카드 — 전송 시 입력창이 그 자리에서 이 카드로 바뀐다(핸드오프 §홈 (b)).
 * AI가 최대 1.5분까지 걸리는 동안 화면이 죽지 않게, 서버 SSE 단계를 4스텝으로 보여준다.
 */
export default function ProgressCard() {
  const messages = useChatStore((s) => s.messages);
  const loadingStage = useChatStore((s) => s.loadingStage);
  const loadingStageKey = useChatStore((s) => s.loadingStageKey);
  const askStartedAt = useChatStore((s) => s.askStartedAt);
  const abortAsk = useChatStore((s) => s.abortAsk);

  // 경과 표시 — 1초 tick. 이 카드가 떠 있는 동안만 돈다.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const prompt = [...messages].reverse().find((m) => m.role === "user")?.content ?? "";
  const queued = loadingStageKey === QUEUED_STAGE;
  const current = queued ? -1 : loadingStageKey != null ? (STEP_OF_STAGE[loadingStageKey] ?? 0) : 0;
  const elapsed = askStartedAt ? Math.max(0, Math.floor((now - askStartedAt) / 1000)) : 0;
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="animate-fade-in-up rounded-3xl border border-border bg-surface px-5 py-4 shadow-[0_1px_2px_rgba(26,26,26,0.04),0_10px_30px_-12px_rgba(26,26,26,0.12)]">
      <p className="text-[15px] font-semibold leading-snug">{prompt}</p>

      <ol className="mt-4 flex flex-col gap-2.5" aria-label="분석 진행 단계">
        {STEPS.map((label, i) => {
          const state = i < current ? "done" : i === current ? "active" : "waiting";
          return (
            <li key={label} className="flex items-center gap-2.5">
              <span
                aria-hidden
                className={`grid place-items-center w-[22px] h-[22px] rounded-full transition-colors duration-150 ${
                  state === "done"
                    ? "bg-accent text-brand"
                    : state === "active"
                      ? "bg-surface border-[1.5px] border-brand"
                      : "border border-border"
                }`}
              >
                {state === "done" && <Check size={12} strokeWidth={2.5} />}
                {state === "active" && (
                  <span className="w-1.5 h-1.5 rounded-full bg-brand animate-pulse" />
                )}
              </span>
              <span
                className={`text-sm transition-colors duration-150 ${
                  state === "active"
                    ? "font-medium text-foreground"
                    : state === "done"
                      ? "text-foreground-muted"
                      : "text-foreground-muted/60"
                }`}
              >
                {label}
                {state === "active" && loadingStage && (
                  <span className="ml-1.5 text-xs text-foreground-muted">— {loadingStage}</span>
                )}
              </span>
            </li>
          );
        })}
      </ol>

      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs">
        <span className="text-foreground-muted tabular-nums">
          {mm}:{ss} {queued && loadingStage ? `· ${loadingStage}` : `경과 · ${TYPICAL_LABEL}`}
        </span>
        <button
          type="button"
          onClick={abortAsk}
          className="text-brand font-medium hover:underline underline-offset-2"
        >
          질문 고치기
        </button>
      </div>
    </div>
  );
}
