import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// shadcn 표준 유틸 — 조건부 클래스를 합치고 뒤에 온 Tailwind 클래스가 이기게 한다.
// (컴포넌트 기본 스타일을 호출부 className으로 덮어쓰기 위해 필요하다)
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
