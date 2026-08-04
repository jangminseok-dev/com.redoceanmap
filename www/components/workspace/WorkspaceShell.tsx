"use client";

import { useState } from "react";

type Tab = "chat" | "stage" | "panel";

type WorkspaceShellProps = {
  stageLabel: string; // 모바일 탭 라벨: "차트" | "지도"
  stage: React.ReactNode; // 중앙 스테이지 (차트/지도)
  panel: React.ReactNode; // 자료 패널 (데스크탑 좌측)
  chat: React.ReactNode; // 채팅 패널 (데스크탑 우측)
};

// 3패널 반응형 골격.
// xl(1280+): [자료 340px | 스테이지 | 채팅 360px]
// lg(1024~1279): [스테이지 위 + 자료 아래 | 채팅 360px]
// 모바일(<1024): 세그먼트 탭 [채팅][스테이지][자료]
// 패널들은 한 번만 마운트하고(지도·차트 이중 인스턴스 방지) 표시 전환은 CSS로 한다.
export default function WorkspaceShell({ stageLabel, stage, panel, chat }: WorkspaceShellProps) {
  const [tab, setTab] = useState<Tab>("stage");

  const tabs: { key: Tab; label: string }[] = [
    { key: "chat", label: "채팅" },
    { key: "stage", label: stageLabel },
    { key: "panel", label: "자료" },
  ];

  return (
    <div className="flex flex-col h-[calc(100dvh-3.5rem)]">
      {/* 모바일 세그먼트 탭 */}
      <nav className="lg:hidden shrink-0 flex px-4 pt-2 gap-1" aria-label="워크스페이스 패널 전환">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            aria-pressed={tab === t.key}
            className={`flex-1 h-10 rounded-lg text-sm font-medium transition-colors ${
              tab === t.key
                ? "bg-brand text-white"
                : "bg-surface border border-border text-foreground-muted"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="flex-1 min-h-0 flex flex-col lg:grid lg:grid-cols-[minmax(0,1fr)_360px] lg:grid-rows-[minmax(0,1fr)] xl:grid-cols-[340px_minmax(0,1fr)_360px]">
        {/* 스테이지 + 자료 래퍼 — xl에서는 contents로 녹아 그리드 아이템이 된다 */}
        <div
          className={`min-h-0 flex-col lg:flex lg:flex-1 xl:contents ${
            tab === "chat" ? "hidden lg:flex" : "flex flex-1"
          }`}
        >
          <section
            className={`flex-1 min-h-0 flex-col ${
              tab === "stage" ? "flex" : "hidden"
            } lg:flex xl:col-start-2 xl:row-start-1 xl:min-h-0`}
          >
            {stage}
          </section>
          <aside
            className={`min-h-0 overflow-y-auto ${
              tab === "panel" ? "block flex-1" : "hidden"
            } lg:block lg:flex-none lg:max-h-[45%] lg:border-t lg:border-border xl:col-start-1 xl:row-start-1 xl:h-full xl:max-h-none xl:border-t-0 xl:border-r xl:border-border`}
            aria-label="분석 자료"
          >
            {panel}
          </aside>
        </div>

        <aside
          className={`min-h-0 flex-col ${
            tab === "chat" ? "flex flex-1" : "hidden"
          } lg:flex lg:border-l lg:border-border xl:col-start-3 xl:row-start-1`}
          aria-label="AI 채팅"
        >
          {chat}
        </aside>
      </div>
    </div>
  );
}
