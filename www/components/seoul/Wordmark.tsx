"use client";

import Link from "next/link";
import { useChatStore } from "@/lib/store";

// iconOnly는 72px 레일용이다 — 그 폭에 "redoceanmap" 11글자가 들어가지 않는다.
export default function Wordmark({ iconOnly = false }: { iconOnly?: boolean }) {
  const reset = useChatStore((s) => s.reset);

  return (
    <Link
      href="/"
      onClick={reset}
      aria-label={iconOnly ? "redoceanmap 홈" : undefined}
      className="flex items-center gap-2 text-foreground"
    >
      <svg
        width="16"
        height="20"
        viewBox="0 0 16 20"
        fill="none"
        aria-hidden
      >
        <path
          d="M8 0C3.6 0 0 3.6 0 8c0 6 8 12 8 12s8-6 8-12c0-4.4-3.6-8-8-8z"
          fill="var(--brand)"
        />
        <circle cx="8" cy="8" r="2.5" fill="var(--background)" />
      </svg>
      {!iconOnly && (
        <span className="font-semibold tracking-tight text-[15px]">
          redoceanmap
        </span>
      )}
    </Link>
  );
}
