"use client";

import { AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * 어드민 확인 모달 — 무상태(REACT_RULES). 사유 입력은 uncontrolled(FormData 패턴 A).
 * danger면 확인 버튼이 붉은색(비가역 행위 — 탈퇴 등).
 *
 * 부모가 조건부로 마운트하므로 open은 항상 true다. Escape·오버레이 클릭·포커스 트랩은
 * Radix Dialog가 맡는다(직접 달았던 keydown 리스너와 오닫힘 방지 onMouseDown을 대체).
 */
export default function ConfirmDialog({
  title,
  message,
  confirmLabel,
  danger = false,
  withReason = false,
  onConfirm,
  onClose,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  danger?: boolean;
  withReason?: boolean;
  onConfirm: (reason: string) => void;
  onClose: () => void;
}) {
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    onConfirm(String(formData.get("reason") ?? "").trim());
  };

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent showCloseButton={false} className="sm:max-w-sm rounded-2xl bg-surface">
        <form onSubmit={handleSubmit}>
          <DialogHeader className="text-left">
            <div className="flex items-center gap-2.5">
              <span
                className={`grid place-items-center w-10 h-10 rounded-full shrink-0 ${
                  danger ? "bg-red-50 text-red-600" : "bg-brand/10 text-brand"
                }`}
              >
                <AlertTriangle size={18} strokeWidth={1.9} />
              </span>
              <DialogTitle className="text-base font-bold tracking-tight">{title}</DialogTitle>
            </div>
            <DialogDescription className="leading-relaxed whitespace-pre-line">
              {message}
            </DialogDescription>
          </DialogHeader>

          {withReason && (
            <Input
              name="reason"
              autoFocus
              maxLength={200}
              placeholder="사유 (선택, 200자 이내)"
              className="mt-4 bg-background"
            />
          )}

          <DialogFooter className="mt-6">
            <Button type="button" variant="outline" onClick={onClose}>
              취소
            </Button>
            <Button type="submit" variant={danger ? "destructive" : "default"}>
              {confirmLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
