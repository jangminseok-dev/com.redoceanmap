"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiTabs } from "./authApi";
import { useUIStore } from "./uiStore";

export type TabKey = "history" | "market" | "stock" | "vision" | "automation";

/**
 * 등급 게이팅 단일 소스 — 셸 내비(AppShell)와 라우트 가드(TabGuard)가 함께 쓴다.
 * user.id를 쿼리 키에 넣어 로그인/로그아웃 시 자동 리페치.
 * 반환: null = 로딩 중(게이팅 탭 미표시), 에러 시 빈 Set(안전측).
 */
export function useVisibleTabs(): Set<TabKey> | null {
  const user = useUIStore((s) => s.user);
  const { data, isError } = useQuery({
    queryKey: ["visible-tabs", user?.id ?? "anon"],
    queryFn: () => apiTabs(),
    // 로그인/로그아웃으로 키가 바뀌는 동안 이전 값을 유지한다 — data가 잠깐 undefined가 되면
    // TabGuard가 null을 반환해 워크스페이스 전체가 언마운트→리마운트된다(차트 재생성·상태 초기화).
    placeholderData: keepPreviousData,
  });
  if (isError) return new Set<TabKey>();
  if (!data) return null;
  return new Set(data.tabs as TabKey[]);
}
