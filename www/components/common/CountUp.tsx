"use client";

import { useCountUp } from "@/lib/useCountUp";

/**
 * 값이 바뀔 때만 굴러가는 숫자. 잔액·시세처럼 **갱신되는 자리**에만 쓴다.
 * 한 번 찍고 마는 값(집계 결과·통계 표)에는 쓰지 않는다 — 읽는 데 방해가 된다.
 */
export default function CountUp({
  value,
  format,
}: {
  value: number;
  format: (v: number) => string;
}) {
  return <>{format(useCountUp(value))}</>;
}
