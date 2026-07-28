"use client";

import { useEffect, useState } from "react";
import { X, Send, CheckCircle2 } from "lucide-react";

// 브라우저 직접 호출 — same-origin /api/backend(rewrites) 경유 (authApi와 동일 이유)
const API_BASE = "/api/backend";

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function EmailModal({ open, onClose }: Props) {
  const [ui, setUI] = useState<{
    status: "idle" | "sending" | "sent" | "error";
    error: string;
  }>({ status: "idle", error: "" });

  useEffect(() => {
    if (open) setUI({ status: "idle", error: "" });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const content = String(formData.get("content") ?? "").trim();
    if (!content) {
      setUI({ status: "error", error: "보낼 내용을 입력해주세요." });
      return;
    }
    setUI({ status: "sending", error: "" });
    try {
      // 수신자는 보내지 않는다 — 서버가 로그인 계정 이메일로 고정한다(오픈 릴레이 차단).
      const res = await fetch(`${API_BASE}/email/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (!res.ok) throw new Error("발송 요청 실패");
      setUI({ status: "sent", error: "" });
    } catch {
      setUI({ status: "error", error: "발송에 실패했어요. 잠시 후 다시 시도해주세요." });
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm grid place-items-center px-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md bg-surface rounded-2xl shadow-xl p-8"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="이메일 보내기"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="닫기"
          className="absolute top-4 right-4 w-8 h-8 grid place-items-center rounded-full text-foreground-muted hover:bg-black/5"
        >
          <X size={18} />
        </button>

        <div className="flex items-center gap-2 mb-1">
          <Send size={18} strokeWidth={1.75} className="text-brand" />
          <h2 className="text-lg font-semibold tracking-tight">이메일 보내기</h2>
        </div>
        <p className="text-sm text-foreground-muted mb-6">
          내용을 적으면 AI가 정중한 이메일로 작성해 회원님 가입 메일로 보내드려요.
        </p>

        {ui.status === "sent" ? (
          <div className="flex flex-col items-center py-8 gap-3">
            <CheckCircle2 size={40} strokeWidth={1.5} className="text-brand" />
            <p className="font-medium">발송 완료!</p>
            <p className="text-sm text-foreground-muted">
              AI가 작성한 이메일을 회원님 가입 메일로 보냈어요.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="mt-2 px-6 py-2 rounded-full bg-brand text-white text-sm font-medium hover:bg-brand-deep transition-colors"
            >
              닫기
            </button>
          </div>
        ) : (
          <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
            <label htmlFor="email-content" className="sr-only">
              보낼 내용
            </label>
            <textarea
              id="email-content"
              name="content"
              rows={5}
              placeholder="전하고 싶은 내용을 편하게 적어주세요 (예: 성수동 상권 리포트가 준비됐다고 안내해줘)"
              className="w-full bg-transparent border border-border rounded-xl px-4 py-3 text-sm outline-none focus:border-brand placeholder:text-foreground-muted resize-none"
            />

            {ui.error && (
              <p className="text-sm text-red-500 text-center">{ui.error}</p>
            )}
            <button
              type="submit"
              disabled={ui.status === "sending"}
              className="mt-2 w-full bg-brand text-white py-3 rounded-xl font-medium hover:bg-brand-deep transition-colors disabled:opacity-60"
            >
              {ui.status === "sending" ? "AI가 작성해서 보내는 중..." : "보내기"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
