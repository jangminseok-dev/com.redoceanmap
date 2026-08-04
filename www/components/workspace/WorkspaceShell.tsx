"use client";

import { useState } from "react";
import { ChevronUp, MessageSquare } from "lucide-react";

type WorkspaceShellProps = {
  /** 좌측 목록 — 2xl(1536px+)에서만 상시 노출. 좁은 화면에서는 스테이지가 그 역할을 한다. */
  list?: React.ReactNode;
  stage: React.ReactNode; // 중앙 스테이지 (차트/지도) — 높이는 스테이지가 스스로 정한다
  panel: React.ReactNode; // 자료 패널 — 스테이지 아래로 이어진다
  chat: React.ReactNode; // AI 인사이트 + 대화
};

/**
 * 워크스페이스 골격 — 2열.
 *
 *   lg+   [스테이지 + 자료(한 스크롤) | 채팅 380px]
 *   <lg   [스테이지 + 자료(한 스크롤)] + 채팅 바텀시트
 *
 * 이전 구조는 3열(자료 340 | 스테이지 | 채팅 360)에 모바일 3탭[채팅][스테이지][자료]이었다.
 * 탭을 없앤 이유는 왕복 비용이다 — 차트를 보면서 물어보는 것이 이 제품의 기본 동작인데,
 * 탭으로 갈라 두면 질문할 때마다 차트가 사라졌다. 지금은 시트를 올려도 차트가 남는다.
 *
 * **채팅은 한 번만 마운트된다.** 데스크탑 컬럼과 모바일 시트가 같은 DOM 노드이고
 * position만 바뀐다(모바일 fixed → lg static). 지도·차트 이중 인스턴스를 막던
 * 기존 구조의 의도를 그대로 지킨다.
 */
export default function WorkspaceShell({ list, stage, panel, chat }: WorkspaceShellProps) {
  const [sheetOpen, setSheetOpen] = useState(false);

  return (
    // h-full — 부모(main)가 스크롤 컨테이너다. flex-1로 두면 콘텐츠만큼 늘어나
    // 내부 스크롤 대신 페이지 전체가 스크롤된다(채팅 컬럼이 무한히 길어진다).
    <div className="h-full min-h-0 flex flex-col lg:flex-row">
      {/* 목록 — 종목을 골라도 남는다. 예전에는 스테이지가 목록↔상세로 교체돼,
          종목을 고르는 순간 화면에서 목록이 사라지고 그만큼 헐거워 보였다(레퍼런스 토스증권은
          왼쪽 표가 그대로 남는다). 2xl 미만에서는 폭이 모자라 숨긴다 —
          그 구간에서는 종목 미선택 상태의 스테이지가 목록 역할을 한다. */}
      {list && (
        <aside
          aria-label="종목 목록"
          className="hidden 2xl:flex 2xl:flex-col w-[320px] shrink-0 min-h-0 overflow-y-auto overscroll-contain border-r border-border"
        >
          {list}
        </aside>
      )}

      {/* 스테이지 + 자료 — 하나의 스크롤 흐름. 차트 높이는 스테이지가 래퍼로 정한다. */}
      <div className="flex-1 min-w-0 min-h-0 overflow-y-auto overscroll-contain">
        {stage}
        {panel}
      </div>

      {/* 시트가 열렸을 때만 뒤를 덮는다. 데스크탑에는 없다. */}
      {sheetOpen && (
        <button
          type="button"
          aria-label="채팅 닫기"
          onClick={() => setSheetOpen(false)}
          className="lg:hidden fixed inset-0 z-30 bg-black/20"
        />
      )}

      <aside
        aria-label="AI 채팅"
        // 모바일: 하단 탭바(4rem + safe-area) 위에 뜨는 시트. 접히면 손잡이 3.5rem만 남는다.
        // 데스크탑: 우측 고정 컬럼 — position과 transform이 함께 풀린다.
        style={{ ["--sheet-y" as string]: sheetOpen ? "0px" : "calc(100% - 3.5rem)" }}
        className={[
          "flex flex-col bg-surface",
          // 모바일 시트
          "fixed inset-x-0 z-40 bottom-[calc(4rem+env(safe-area-inset-bottom))] h-[72dvh]",
          "translate-y-(--sheet-y) transition-transform duration-[280ms] ease-[cubic-bezier(0.22,1,0.36,1)]",
          "rounded-t-2xl border-t border-border shadow-lg",
          // 데스크탑 컬럼 — 시트 속성을 전부 되돌린다
          "lg:static lg:z-auto lg:h-auto lg:w-[380px] lg:shrink-0",
          "lg:translate-y-0 lg:transition-none",
          "lg:rounded-none lg:border-t-0 lg:border-l lg:border-border lg:shadow-none",
        ].join(" ")}
      >
        {/* 손잡이 — 접힌 상태에서 화면에 남는 유일한 부분이다. 탭 대신 이것이 채팅 입구다. */}
        <button
          type="button"
          onClick={() => setSheetOpen((prev) => !prev)}
          aria-expanded={sheetOpen}
          className="lg:hidden shrink-0 h-14 flex items-center gap-2 px-4 text-sm font-medium"
        >
          <MessageSquare size={17} strokeWidth={1.9} className="text-brand" />
          물어보기
          <ChevronUp
            size={16}
            className={`ml-auto text-foreground-muted transition-transform duration-150 ${
              sheetOpen ? "rotate-180" : ""
            }`}
          />
        </button>

        <div className="flex-1 min-h-0 flex flex-col">{chat}</div>
      </aside>
    </div>
  );
}
