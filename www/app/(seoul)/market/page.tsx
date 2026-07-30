"use client";

import { Suspense, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchAreaInfo } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";
import ChatPanel from "@/components/chat/ChatPanel";
import MapView, { type MapPin } from "@/components/seoul/MapView";
import AreaStatsPanel from "@/components/market/AreaStatsPanel";
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
  const serviceCode = recommendations.find((r) => r.id === trdar)?.serviceCode
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

  const pins: MapPin[] = [
    ...recommendations.map((r) => ({ id: r.id, lat: r.lat, lng: r.lng })),
    ...(areaInfoQ.data && !inRecommendations
      ? [{ id: String(areaInfoQ.data.trdar_code), lat: areaInfoQ.data.lat, lng: areaInfoQ.data.lng }]
      : []),
  ];

  return (
    <WorkspaceShell
      stageLabel="지도"
      stage={
        <div className="relative flex-1 min-h-0 p-3">
          <MapView areas={pins} selectedId={trdar || null} onSelect={setTrdar} />
          {overlayOpen && (
            <AreaDetailOverlay trdarCode={trdar} serviceCode={serviceCode} onClose={closeOverlay} />
          )}
        </div>
      }
      panel={<AreaStatsPanel trdarCode={trdar} serviceCode={serviceCode} />}
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
