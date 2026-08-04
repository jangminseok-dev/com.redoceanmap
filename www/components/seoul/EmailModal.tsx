"use client";

import { useEffect, useState } from "react";
import { Send, CheckCircle2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

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

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      {/* 닫기 X·Escape·오버레이 클릭은 DialogContent가 기본 제공한다 */}
      <DialogContent className="sm:max-w-md rounded-2xl bg-surface p-8">
        <DialogHeader className="text-left gap-1">
          <DialogTitle className="flex items-center gap-2 tracking-tight">
            <Send size={18} strokeWidth={1.75} className="text-brand" />
            이메일 보내기
          </DialogTitle>
          <DialogDescription>
            내용을 적으면 AI가 정중한 이메일로 작성해 회원님 가입 메일로 보내드려요.
          </DialogDescription>
        </DialogHeader>

        {ui.status === "sent" ? (
          <div className="flex flex-col items-center py-8 gap-3">
            <CheckCircle2 size={40} strokeWidth={1.5} className="text-brand" />
            <p className="font-medium">발송 완료!</p>
            <p className="text-sm text-foreground-muted">
              AI가 작성한 이메일을 회원님 가입 메일로 보냈어요.
            </p>
            <Button type="button" onClick={onClose} className="mt-2">
              닫기
            </Button>
          </div>
        ) : (
          <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
            <label htmlFor="email-content" className="sr-only">
              보낼 내용
            </label>
            <Textarea
              id="email-content"
              name="content"
              rows={5}
              placeholder="전하고 싶은 내용을 편하게 적어주세요 (예: 성수동 상권 리포트가 준비됐다고 안내해줘)"
              className="resize-none"
            />

            {ui.error && <p className="text-sm text-destructive text-center">{ui.error}</p>}
            {/* 폭이 w-full로 고정이라 라벨이 길어져도 버튼이 흔들리지 않는다 —
                진행 문구를 그대로 보여주는 편이 스피너보다 정보가 많다 */}
            <Button type="submit" size="xl" disabled={ui.status === "sending"} className="mt-2 w-full">
              {ui.status === "sending" ? "AI가 작성해서 보내는 중..." : "보내기"}
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
