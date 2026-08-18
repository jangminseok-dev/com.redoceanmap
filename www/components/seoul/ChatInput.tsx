"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Plus, ChevronDown, ArrowRight, Check } from "lucide-react";
import { useChatStore, type ChatEngine } from "@/lib/store";
import { Textarea } from "@/components/ui/textarea";

type Props = {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
  /** 초기 입력값 — "질문 고치기"로 중단한 문장을 복원할 때 쓴다(호출부가 key로 리마운트) */
  initialText?: string;
};

const ENGINES: { id: ChatEngine; label: string; desc: string }[] = [
  { id: "rom1", label: "ROM 1.0", desc: "단발 질의 · 상권/종목 카드" },
  { id: "rom2", label: "ROM 2.0", desc: "랭체인 · 이어지는 대화" },
];

export default function ChatInput({
  onSubmit,
  disabled,
  placeholder = "예산이랑 하고 싶은 업종을 알려주세요",
  initialText = "",
}: Props) {
  // 엔진은 스토어 소유 — 답변 후 워크스페이스로 이동해도 고른 버전이 유지된다
  const engine = useChatStore((s) => s.engine);
  const setEngine = useChatStore((s) => s.setEngine);
  const [ui, setUi] = useState({ text: initialText, menuOpen: false });

  const submit = () => {
    const trimmed = ui.text.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setUi((prev) => ({ ...prev, text: "" }));
  };

  const handleFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const canSend = ui.text.trim().length > 0 && !disabled;
  const current = ENGINES.find((e) => e.id === engine) ?? ENGINES[0];

  return (
    // 상자는 **하나**다. Textarea가 자체 border·ring을 갖고 있어(shadcn 기본) 그대로 두면
    // 둥근 form 안에 각진 상자가 하나 더 그려진다 — 아래에서 전부 무력화하고,
    // focus 표시는 form이 focus-within으로 한 번만 낸다.
    <form
      onSubmit={handleFormSubmit}
      className={[
        "bg-surface border border-border rounded-3xl",
        "shadow-[0_1px_2px_rgba(26,26,26,0.04),0_10px_30px_-12px_rgba(26,26,26,0.12)]",
        "transition-[border-color,box-shadow] duration-150 ease-[cubic-bezier(0.22,1,0.36,1)]",
        "hover:border-foreground-muted/25",
        "focus-within:border-brand/45 focus-within:ring-4 focus-within:ring-brand/10",
      ].join(" ")}
    >
      <Textarea
        aria-label="질문 입력"
        value={ui.text}
        onChange={(e) => setUi((prev) => ({ ...prev, text: e.target.value }))}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={2}
        className="w-full resize-none border-0 rounded-none bg-transparent px-5 pt-5 pb-2 text-base shadow-none placeholder:text-foreground-muted focus-visible:border-0 focus-visible:ring-0"
      />
      <div className="flex items-center justify-between px-3 pb-3">
        <button
          type="button"
          aria-label="첨부"
          className="w-10 h-10 grid place-items-center rounded-full text-foreground-muted hover:bg-accent"
        >
          <Plus size={18} strokeWidth={1.75} />
        </button>
        <div className="flex items-center gap-1 text-sm text-foreground-muted">
          <div className="relative">
            <button
              type="button"
              aria-haspopup="listbox"
              aria-expanded={ui.menuOpen}
              onClick={() => setUi((prev) => ({ ...prev, menuOpen: !prev.menuOpen }))}
              className="flex items-center gap-1 px-2 py-1 rounded-md hover:bg-accent"
            >
              {current.label} <ChevronDown size={14} />
            </button>
            {ui.menuOpen && (
              <>
                {/* 바깥 클릭으로 닫기 — 전역 리스너 없이 배경 한 겹으로 처리 */}
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setUi((prev) => ({ ...prev, menuOpen: false }))}
                />
                <ul
                  role="listbox"
                  className="absolute bottom-full right-0 mb-2 z-20 w-60 bg-surface border border-border rounded-xl shadow-lg p-1"
                >
                  {ENGINES.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={item.id === engine}
                        onClick={() => {
                          setEngine(item.id);
                          setUi((prev) => ({ ...prev, menuOpen: false }));
                        }}
                        className="w-full flex items-start gap-2 px-3 py-2 rounded-lg text-left hover:bg-accent"
                      >
                        <Check
                          size={14}
                          className={`mt-1 shrink-0 text-brand ${
                            item.id === engine ? "" : "invisible"
                          }`}
                        />
                        <span className="min-w-0">
                          <span className="block text-sm font-medium text-foreground">
                            {item.label}
                          </span>
                          <span className="block text-xs text-foreground-muted">
                            {item.desc}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
          <button
            type="submit"
            aria-label="보내기"
            disabled={!canSend}
            className="ml-1 w-10 h-10 grid place-items-center rounded-full bg-brand text-white transition-[background-color,transform] duration-150 ease-[cubic-bezier(0.22,1,0.36,1)] hover:bg-brand-deep active:scale-95 disabled:bg-accent disabled:text-foreground-muted/50 disabled:cursor-not-allowed disabled:active:scale-100"
          >
            <ArrowRight size={16} strokeWidth={2.25} />
          </button>
        </div>
      </div>
    </form>
  );
}
