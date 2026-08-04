"use client";

import { useEffect, useState } from "react";

/**
 * 관심 종목 — 브라우저에만 둔다.
 *
 * 서버에 저장하지 않는 이유: 게임 지갑처럼 시즌 자산에 영향을 주는 값이 아니라 화면 취향이고,
 * 저장하려면 테이블·엔드포인트·인증 경계가 붙는다. 기기가 바뀌면 사라지는 것을 감수한다.
 *
 * 초기값을 빈 배열로 두고 마운트 후 읽는 이유: localStorage는 서버에 없다.
 * 렌더 중에 읽으면 SSR 결과와 달라져 하이드레이션이 어긋난다.
 */
export function useFavorites(storageKey: string) {
  const [favorites, setFavorites] = useState<string[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) setFavorites(JSON.parse(raw) as string[]);
    } catch {
      // 손상된 값·프라이빗 모드 — 관심 목록이 비는 것으로 열화한다(기능은 계속 동작)
    }
  }, [storageKey]);

  const toggle = (symbol: string) =>
    setFavorites((prev) => {
      const next = prev.includes(symbol)
        ? prev.filter((s) => s !== symbol)
        : [...prev, symbol];
      try {
        localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        // 저장 실패해도 이번 세션 동안은 화면에 반영된다
      }
      return next;
    });

  return { favorites, toggle };
}
