"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark as BookmarkIcon } from "lucide-react";
import { addBookmark, fetchBookmarks, removeBookmark } from "@/lib/api";
import type { Bookmark } from "@/lib/types";
import { useUIStore } from "@/lib/uiStore";

// 북마크 토글 — 상태는 서버(["bookmarks"] 쿼리)가 단일 진실이라 로컬 useState가 없다.
// 비로그인 클릭은 로그인 모달을 연다(조용한 실패보다 다음 행동을 알려주는 쪽).
export default function BookmarkButton({
  targetType,
  targetKey,
  label,
  className = "",
}: {
  targetType: Bookmark["target_type"];
  targetKey: string;
  label: string;
  className?: string;
}) {
  const user = useUIStore((s) => s.user);
  const openAuth = useUIStore((s) => s.openAuth);
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["bookmarks"],
    queryFn: fetchBookmarks,
    enabled: !!user,
  });
  // 서버 정규화(종목 키 대문자)와 같은 규칙으로 비교해야 등록 직후 활성 표시가 맞는다
  const key = targetType === "stock" ? targetKey.trim().toUpperCase() : targetKey.trim();
  const active = (data?.items ?? []).some(
    (b) => b.target_type === targetType && b.target_key === key,
  );
  const toggle = useMutation({
    mutationFn: async (): Promise<void> => {
      if (active) await removeBookmark(targetType, key);
      else await addBookmark({ target_type: targetType, target_key: targetKey, label });
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["bookmarks"] }),
  });

  if (!targetKey.trim()) return null;
  return (
    <button
      type="button"
      aria-pressed={active}
      aria-label={active ? "북마크 해제" : "북마크에 추가"}
      title={active ? "북마크 해제" : "북마크에 추가"}
      disabled={toggle.isPending}
      onClick={() => {
        if (!user) {
          openAuth("login");
          return;
        }
        toggle.mutate();
      }}
      className={`shrink-0 rounded-md p-1 transition-colors ${
        active ? "text-brand" : "text-foreground-muted hover:bg-border/50"
      } ${className}`}
    >
      <BookmarkIcon size={16} className={active ? "fill-current" : ""} />
    </button>
  );
}
