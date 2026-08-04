"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowUp, Plus, RotateCcw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useChatStore, type Message } from "@/lib/store";
import RobotAvatar from "@/components/rom/RobotAvatar";
import { Textarea } from "@/components/ui/textarea";

const SUGGESTIONS = [
  "성수동 상권 요즘 어때?",
  "카페 창업하기 좋은 동네 알려줘",
  "요즘 뜨는 업종이 뭐야?",
];

const clock = (ms?: number) =>
  ms === undefined
    ? ""
    : new Date(ms).toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });

export default function RomChatPage() {
  const messages = useChatStore((s) => s.messages);
  const isLoading = useChatStore((s) => s.isLoading);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const setEngine = useChatStore((s) => s.setEngine);
  const reset = useChatStore((s) => s.reset);
  const [text, setText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  // 이 페이지는 ROM 2.0 전용 창구다 — 다른 화면에서 1.0을 골라두고 들어와도 여기선 2.0으로 말한다
  useEffect(() => setEngine("rom2"), [setEngine]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const send = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    void sendMessage(trimmed);
    setText("");
  };

  return (
    <div className="flex-1 min-h-0 flex flex-col bg-background">
      <header className="shrink-0 flex items-center gap-3 px-4 h-14 border-b border-border bg-surface/60">
        <Link
          href="/"
          aria-label="홈으로"
          className="w-10 h-10 grid place-items-center rounded-full text-foreground-muted hover:bg-accent transition-colors"
        >
          <ArrowLeft size={18} />
        </Link>
        <div className="flex-1 min-w-0 text-center">
          <div className="text-[15px] font-semibold tracking-tight">ROM 2.0</div>
          <div className="text-[11px] text-foreground-muted">상권·주식 대화형 어시스턴트</div>
        </div>
        <button
          type="button"
          onClick={reset}
          aria-label="새 대화"
          className="w-10 h-10 grid place-items-center rounded-full text-foreground-muted hover:bg-accent transition-colors"
        >
          <RotateCcw size={17} />
        </button>
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto" aria-live="polite">
        <div className="mx-auto w-full max-w-2xl px-4 py-6 flex flex-col gap-4">
          {/* 아바타는 대화 맨 위에 남아 스크롤과 함께 밀려 올라간다 */}
          <div className="flex flex-col items-center gap-3 pb-2">
            <RobotAvatar size={messages.length === 0 ? 176 : 96} ring thinking={isLoading} />
            {messages.length === 0 && (
              <>
                <p className="text-sm text-foreground-muted text-center leading-relaxed">
                  무엇이든 물어보세요.
                  <br />
                  상권 질문은 뉴스 근거를 찾아서 답해드려요.
                </p>
                <div className="mt-2 w-full flex flex-col gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => send(s)}
                      className="w-full text-left text-sm px-4 py-3 rounded-2xl bg-surface border border-border hover:border-brand/40 hover:shadow-sm transition-all"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          {messages.map((m) => (
            <Bubble key={m.id} message={m} />
          ))}

          {isLoading && (
            <div className="flex items-end gap-2 animate-fade-in-up">
              <RobotAvatar size={28} />
              <div className="bg-surface border border-border rounded-2xl rounded-bl-md px-4 py-3 flex gap-1.5">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-foreground-muted animate-pulse"
                    style={{ animationDelay: `${i * 0.18}s` }}
                  />
                ))}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      <footer className="shrink-0 border-t border-border bg-surface/60 px-4 py-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(text);
          }}
          className="mx-auto w-full max-w-2xl flex items-end gap-2"
        >
          <button
            type="button"
            aria-label="첨부"
            className="shrink-0 w-10 h-10 grid place-items-center rounded-full bg-surface border border-border text-foreground-muted hover:bg-accent transition-colors"
          >
            <Plus size={19} />
          </button>
          <Textarea
            aria-label="메시지 입력"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(text);
              }
            }}
            rows={1}
            placeholder="ROM에게 메시지 보내기…"
            className="flex-1 resize-none bg-surface border border-border rounded-2xl px-5 py-3 text-[15px] outline-none placeholder:text-foreground-muted focus:border-brand/40 transition-colors max-h-32"
          />
          <button
            type="submit"
            aria-label="보내기"
            disabled={!text.trim() || isLoading}
            className="shrink-0 w-10 h-10 grid place-items-center rounded-full bg-brand text-white hover:bg-brand-deep transition-colors disabled:bg-border disabled:text-foreground-muted"
          >
            <ArrowUp size={19} strokeWidth={2.5} />
          </button>
        </form>
      </footer>
    </div>
  );
}

function Bubble({ message }: { message: Message }) {
  const time = clock(message.createdAt);

  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-fade-in-up">
        <div className="max-w-[80%] bg-brand text-white rounded-2xl rounded-br-md px-4 py-2.5">
          <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{message.content}</p>
          {time && <p className="mt-1 text-[11px] text-white/70 text-right">{time}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-end gap-2 animate-fade-in-up">
      <RobotAvatar size={28} />
      <div className="max-w-[80%] bg-surface border border-border rounded-2xl rounded-bl-md px-4 py-3">
        <MarkdownBody text={message.content} />
        {time && <p className="mt-1.5 text-[11px] text-foreground-muted">{time}</p>}
      </div>
    </div>
  );
}

// LLM 답변은 마크다운으로 온다(**굵게** · 번호 목록). 평문으로 두면 기호가 그대로 보인다.
function MarkdownBody({ text }: { text: string }) {
  return (
    <div className="text-[15px] leading-relaxed text-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => (
            <p className="whitespace-pre-wrap [&:not(:first-child)]:mt-2.5">{children}</p>
          ),
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          ol: ({ children }) => (
            <ol className="mt-2.5 list-decimal pl-5 flex flex-col gap-1.5">{children}</ol>
          ),
          ul: ({ children }) => (
            <ul className="mt-2.5 list-disc pl-5 flex flex-col gap-1.5">{children}</ul>
          ),
          h1: ({ children }) => <p className="mt-3 font-semibold">{children}</p>,
          h2: ({ children }) => <p className="mt-3 font-semibold">{children}</p>,
          h3: ({ children }) => <p className="mt-3 font-semibold">{children}</p>,
          code: ({ children }) => (
            <code className="px-1.5 py-0.5 rounded-md bg-black/5 text-[13px]">{children}</code>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand underline"
            >
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
