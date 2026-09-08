"use client";

import { Suspense, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchAreaInfo } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import { useRecentStore } from "@/lib/uiStore";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";
import ChatPanel from "@/components/chat/ChatPanel";
import MapView, { type MapPin } from "@/components/seoul/MapView";
import AreaStatsPanel from "@/components/market/AreaStatsPanel";
import AreaBrowsePanel from "@/components/market/AreaBrowsePanel";
import AreaDetailOverlay from "@/components/market/overlay/AreaDetailOverlay";

const EMPTY_PROMPTS = [
  "성수동 카페 상권 어때요?",
  "3000만원으로 시작할 수 있는 곳 알려주세요",
  "지금 가장 핫한 동네 추천해주세요",
];

function MarketWorkspace() {
  const params = useSearchParams();
  const trdar = params?.get("trdar") ?? "";
  const c = params?.get("c") ?? null;
  const overlayOpen = !!trdar && params?.get("ov") !== "0";

  const recommendations = useChatStore((s) => s.recommendations);
  // 채팅이 고른 업종 — 넘기지 않으면 백엔드가 "매출 최대 업종"으로 폴백해, 답변과 지도 패널이
  // 서로 다른 업종을 말한다(실사례: 채팅 커피-음료 vs 패널 의약품). 추천 목록의 업종을 따른다.
  // 상권 둘러보기에서 업종 필터로 들어오면(?service=) 그 업종이 우선 — 랭킹의 업종을 상세가 잃지 않게(2026-09-08 QA P02)
  const serviceCode = params?.get("service")
    ?? recommendations.find((r) => r.id === trdar)?.serviceCode
    ?? recommendations[0]?.serviceCode;
  const conversationId = useChatStore((s) => s.conversationId);
  const messages = useChatStore((s) => s.messages);
  const loadConversation = useChatStore((s) => s.loadConversation);

  // 같은 라우트에서 쿼리만 바꾸는 이동 — 초기 URL에 쿼리가 있으면 router.replace/push가
  // 프로덕션 빌드에서 무시된다(Next 16.2.6). 공식 shallow 라우팅인 history.replaceState는
  // useSearchParams와 동기화되므로 이쪽을 쓴다.
  // 새 상권 선택은 ov 파라미터를 버려 오버레이를 자동 재오픈한다
  const setTrdar = (next: string) => {
    const cid = conversationId ?? c;
    window.history.replaceState(null, "", `/market?trdar=${next}${cid ? `&c=${cid}` : ""}`);
  };

  const closeOverlay = () => {
    const cid = conversationId ?? c;
    window.history.replaceState(null, "", `/market?trdar=${trdar}&ov=0${cid ? `&c=${cid}` : ""}`);
  };

  // 채팅 응답에 추천 상권이 오면 첫 곳을 URL(?trdar)에 반영 — 마운트 시 기존 메시지는 건너뛴다
  const handledRef = useRef<string | null>(messages[messages.length - 1]?.id ?? null);

  // 새로고침 복원 — URL의 c를 실제 대화로 되살린다. 복원하지 않으면 채팅이 빈 채로 남아
  // 다음 질문이 새 대화가 되고 멀티턴 맥락이 끊긴다. 복원된 메시지는 이미 URL에 반영된
  // 상태이므로 handledRef를 최신 메시지로 맞춰 위 이펙트가 재이동하지 않게 한다.
  const restoredRef = useRef(false);
  useEffect(() => {
    if (restoredRef.current || !c || conversationId !== null) return;
    restoredRef.current = true;
    void loadConversation(Number(c))
      .then(() => {
        const restored = useChatStore.getState().messages;
        handledRef.current = restored[restored.length - 1]?.id ?? null;
      })
      .catch(() => {}); // 남의 대화·미로그인은 404/401 — 빈 채팅으로 열화
  }, [c, conversationId, loadConversation]);

  useEffect(() => {
    const last = messages[messages.length - 1];
    if (!last || last.role !== "assistant" || handledRef.current === last.id) return;
    handledRef.current = last.id;
    if (last.recommendations && last.recommendations.length > 0) {
      // 같은 상권 재추천이면 URL 불변 — 사용자가 닫은 오버레이를 다시 열지 않는다
      const next = last.recommendations[0].id;
      if (next !== trdar) setTrdar(next);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  // 새로고침 등으로 추천 목록에 없는 상권이 URL에 있으면 위치를 조회해 핀을 복원한다
  const inRecommendations = recommendations.some((r) => r.id === trdar);
  const areaInfoQ = useQuery({
    queryKey: ["area-info", trdar],
    queryFn: () => fetchAreaInfo(trdar),
    enabled: !!trdar && !inRecommendations,
  });

  // 레일 "최근" 스택 기록 — 이름을 아는 시점(추천 목록 또는 상권 조회 도착)에 남긴다
  const pushRecent = useRecentStore((s) => s.push);
  const recentLabel =
    recommendations.find((r) => r.id === trdar)?.name ?? areaInfoQ.data?.trdar_name;
  useEffect(() => {
    if (trdar && recentLabel) pushRecent({ type: "market", id: trdar, label: recentLabel });
  }, [trdar, recentLabel, pushRecent]);

  // 추천 순서를 핀 번호로 — 채팅 카드·지도 칩과 같은 번호라 셋이 하나의 흐름으로 읽힌다
  const pins: MapPin[] = [
    ...recommendations.map((r, i) => ({ id: r.id, lat: r.lat, lng: r.lng, n: i + 1 })),
    ...(areaInfoQ.data && !inRecommendations
      ? [{ id: String(areaInfoQ.data.trdar_code), lat: areaInfoQ.data.lat, lng: areaInfoQ.data.lng }]
      : []),
  ];

  return (
    <WorkspaceShell
      stage={
        // 지도를 전면으로 깐다(레퍼런스 네이버지도) — 여백과 radius를 두면 "카드 안의 지도"가 되어
        // 지도가 배경이 아니라 부품처럼 보인다. 조작(줌)은 MapView가 지도 위에 올린다.
        <div className="relative h-full min-h-[420px]">
          <MapView areas={pins} selectedId={trdar || null} onSelect={setTrdar} />

          {/* 지도 위 떠 있는 상권 칩 — 네이버지도의 카테고리 칩 자리다.
              추천받은 상권을 지도 밖으로 나가지 않고 그 위에서 바로 오갈 수 있게 한다.
              오버레이가 열려 있으면 그 폭만큼 비켜 준다(lg 이상에서만 나란히 놓인다). */}
          {recommendations.length > 0 && (
            <div
              className={`absolute inset-x-0 top-0 z-10 flex gap-1.5 overflow-x-auto px-3 py-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden ${
                overlayOpen ? "lg:pr-[420px]" : ""
              }`}
            >
              {recommendations.map((r, i) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setTrdar(r.id)}
                  aria-pressed={r.id === trdar}
                  // 유리 한 겹(핸드오프 §6 상한) — 지도 위에 뜨는 유일한 반투명 요소다.
                  // 다크 활성은 브랜드 면 대신 전경 반전 — 다크에서 적색 면은 상승색과 헷갈린다.
                  className={`shrink-0 inline-flex items-center gap-1.5 h-8 pl-1.5 pr-3 rounded-full text-xs font-medium shadow-sm transition-colors duration-150 ${
                    r.id === trdar
                      ? "bg-brand text-white dark:bg-foreground dark:text-background"
                      : "bg-surface/80 supports-[backdrop-filter]:backdrop-blur-md border border-border hover:bg-accent"
                  }`}
                >
                  <span
                    aria-hidden
                    className={`grid place-items-center w-5 h-5 rounded-full text-xs font-bold tabular-nums ${
                      r.id === trdar
                        ? "bg-white/20 dark:bg-background/20"
                        : "bg-accent text-brand"
                    }`}
                  >
                    {i + 1}
                  </span>
                  {r.name}
                </button>
              ))}
            </div>
          )}

          {/* 데이터 출처 — 지도 좌하단 상주 칩. 기준 분기는 상세 시트 헤더가 상권별로 말한다. */}
          <span className="absolute left-3 bottom-3 z-10 inline-flex items-center h-6 px-2.5 rounded-full bg-surface/80 supports-[backdrop-filter]:backdrop-blur-md border border-border text-xs text-foreground-muted pointer-events-none">
            서울시 상권분석서비스 데이터
          </span>

          {overlayOpen && (
            <AreaDetailOverlay trdarCode={trdar} serviceCode={serviceCode} onClose={closeOverlay} />
          )}
        </div>
      }
      // 상권을 고르기 전에는 둘러보기 목록으로 채운다 — 예전에는 안내 한 줄만 있었다
      panel={
        trdar ? (
          <AreaStatsPanel trdarCode={trdar} serviceCode={serviceCode} />
        ) : (
          <AreaBrowsePanel onSelect={setTrdar} />
        )
      }
      chat={
        <ChatPanel
          workspace="market"
          placeholder="동네·업종·예산으로 물어보세요"
          emptyPrompts={EMPTY_PROMPTS}
          onSelectArea={(area) => setTrdar(area.id)}
        />
      }
    />
  );
}

export default function MarketPage() {
  return (
    <Suspense>
      <MarketWorkspace />
    </Suspense>
  );
}
