"use client";

import { useEffect, useRef, useState } from "react";

// DESIGN.md §15의 3단 중 "요소 진입·퇴장"과 같은 길이. 여기만 다른 값을 쓰지 않는다.
const DURATION_MS = 200;

/**
 * 값이 바뀔 때 이전 값에서 새 값으로 굴러가는 숫자.
 *
 * 첫 렌더에는 애니메이션이 없다 — 화면에 처음 뜨는 값이 0에서 올라오면
 * 그 사이 잘못된 금액이 읽힌다. **바뀔 때만** 움직인다.
 */
export function useCountUp(target: number) {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const from = fromRef.current;
    if (from === target) return;

    // 동작 줄이기를 켰으면 즉시 반영한다 (DESIGN.md §15 — 선택이 아니다)
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      fromRef.current = target;
      setValue(target);
      return;
    }

    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION_MS);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out — 감속만 있고 되튀지 않는다
      setValue(Math.round(from + (target - from) * eased));
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = target;
      }
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      // 중간에 끊기면 다음 애니메이션이 화면에 보이는 값에서 이어지게 한다
      fromRef.current = target;
    };
  }, [target]);

  return value;
}
