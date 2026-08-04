import { type ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/utils";

// Magic UI marquee — 의존성 0(순수 CSS)이라 모션 라이브러리 없이 쓴다.
// 원본의 `interface`·세로 모드는 걷어냈다: 우리는 가로 티커 하나만 쓴다(www CLAUDE.md — 단일 용도 추상화 금지).
// 키프레임과 --animate-marquee는 app/globals.css에 있다.
//
// `prefers-reduced-motion: reduce`에서는 globals.css가 iteration-count를 1로 강제해 멈춘다.
// 내용은 repeat벌이 이미 렌더돼 있어 그대로 읽힌다 — 정보가 사라지지 않는다.
type MarqueeProps = ComponentPropsWithoutRef<"div"> & {
  /** 흐르는 속도. 길수록 느리다. */
  duration?: string;
  /** hover 시 멈춤 — 값을 읽으려고 마우스를 올렸을 때 도망가지 않게 한다. */
  pauseOnHover?: boolean;
  /** 내용 반복 횟수. 폭이 좁은 내용일수록 늘려야 빈틈이 생기지 않는다. */
  repeat?: number;
  children: React.ReactNode;
};

export function Marquee({
  className,
  duration = "40s",
  pauseOnHover = true,
  repeat = 4,
  children,
  ...props
}: MarqueeProps) {
  return (
    <div
      {...props}
      className={cn("group flex flex-row gap-(--gap) overflow-hidden [--gap:1.5rem]", className)}
      style={{ ["--duration" as string]: duration, ...props.style }}
    >
      {Array.from({ length: repeat }, (_, i) => (
        <div
          key={i}
          aria-hidden={i > 0} // 스크린리더에는 한 벌만 읽힌다 — 나머지는 빈틈을 메우는 시각적 복제다
          className={cn(
            "flex shrink-0 flex-row items-center justify-around gap-(--gap) animate-marquee",
            pauseOnHover && "group-hover:[animation-play-state:paused]",
          )}
        >
          {children}
        </div>
      ))}
    </div>
  );
}
