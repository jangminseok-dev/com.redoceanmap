"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Plus, ChevronDown, ArrowRight, Check } from "lucide-react";
import { useChatStore, type ChatEngine } from "@/lib/store";

type Props = {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
};

const ENGINES: { id: ChatEngine; label: string; desc: string }[] = [
  { id: "rom1", label: "ROM 1.0", desc: "단발 질의 · 상권/종목 카드" },
  { id: "rom2", label: "ROM 2.0", desc: "랭체인 · 이어지는 대화" },
];

export default function ChatInput({
  onSubmit,
  disabled,
  placeholder = "예산이랑 하고 싶은 업종을 알려주세요",
}: Props) {
  // 엔진은 스토어 소유 — 답변 후 워크스페이스로 이동해도 고른 버전이 유지된다
  const engine = useChatStore((s) => s.engine);
  const setEngine = useChatStore((s) => s.setEngine);
  const [ui, setUi] = useState({ text: "", menuOpen: false });

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
    <form
      onSubmit={handleFormSubmit}
      className="bg-surface border border-border rounded-2xl shadow-sm"
    >
      <textarea
        aria-label="질문 입력"
        value={ui.text}
        onChange={(e) => setUi((prev) => ({ ...prev, text: e.target.value }))}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={2}
        className="w-full resize-none bg-transparent px-5 pt-5 pb-2 outline-none text-base placeholder:text-foreground-muted"
      />
      <div className="flex items-center justify-between px-3 pb-3">
        <button
          type="button"
          aria-label="첨부"
          className="w-9 h-9 grid place-items-center rounded-full text-foreground-muted hover:bg-black/5"
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
              className="flex items-center gap-1 px-2 py-1 rounded-md hover:bg-black/5"
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
                        className="w-full flex items-start gap-2 px-3 py-2 rounded-lg text-left hover:bg-black/5"
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
            className="ml-1 w-9 h-9 grid place-items-center rounded-full bg-brand text-white hover:bg-brand-deep transition-colors disabled:bg-border disabled:text-foreground-muted disabled:cursor-not-allowed"
          >
            <ArrowRight size={16} strokeWidth={2.25} />
          </button>
        </div>
      </div>
    </form>
  );
}
