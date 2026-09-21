"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  CalendarClock,
  ChevronUp,
  DoorOpen,
  Store,
  UsersRound,
  Wallet,
  X,
} from "lucide-react";
import { fetchAreaDetail } from "@/lib/api";
import BookmarkButton from "@/components/common/BookmarkButton";
import InsightList from "@/components/common/InsightList";
import CustomerProfileSection from "./CustomerProfileSection";
import DemandSection from "./DemandSection";
import SalesRhythmSection from "./SalesRhythmSection";
import PermitChurnSection from "./PermitChurnSection";
import ServiceRankingSection from "./ServiceRankingSection";
import SpendingSection from "./SpendingSection";

// 시트 안은 카드 금지 — border-t 선으로만 구획한다(핸드오프 §상권).
// 유리 시트 위에 카드를 겹치면 반투명이 두 겹이 되어 뒤 지도가 죽는다.
function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Wallet;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="pt-4 mt-4 border-t border-border first:pt-0 first:mt-0 first:border-t-0">
      <h3 className="flex items-center gap-1.5 text-xs font-semibold text-foreground-muted uppercase tracking-wide mb-2">
        <Icon size={13} strokeWidth={2} />
        {title}
      </h3>
      {children}
    </section>
  );
}

// 지도 위 반투명 분석 시트 — 열림/닫힘은 URL(?trdar / &ov=0)이 단일 진실.
// 모바일은 **반개방 바텀시트가 기본**이다: 지도(어디인가)와 결론(어떤가)을 동시에 보여주고,
// 손잡이로 펼친다. 예전 전체 덮기는 상권을 고르는 순간 지도가 사라졌다.
export default function AreaDetailOverlay({
  trdarCode,
  serviceCode,
  onClose,
}: {
  trdarCode: string;
  serviceCode?: string;
  onClose: () => void;
}) {
  const [expanded, setExpanded] = useState(false); // 모바일 시트 확장 — 상태는 이 하나뿐이다
  const { data, isLoading, isError } = useQuery({
    queryKey: ["area-detail", trdarCode, serviceCode],
    queryFn: () => fetchAreaDetail(trdarCode, serviceCode),
    enabled: !!trdarCode,
    retry: false, // 404(미존재 상권)를 재시도 없이 바로 에러 문구로
  });

  return (
    <div
      className={[
        "absolute z-10 border border-border bg-background/90 supports-[backdrop-filter]:backdrop-blur-md shadow-xl overflow-y-auto overscroll-contain",
        // 모바일 — 하단 시트. 반개방(46dvh) ↔ 확장(85dvh)을 손잡이로 오간다.
        "inset-x-0 bottom-0 rounded-t-2xl transition-[height] duration-[280ms] ease-[cubic-bezier(0.22,1,0.36,1)]",
        expanded ? "h-[85%]" : "h-[46%]",
        // 데스크탑 — 우측 416px 컬럼 시트(핸드오프 §상권). 시트 속성을 되돌린다.
        "lg:inset-auto lg:right-3 lg:top-3 lg:bottom-3 lg:h-auto lg:w-[416px] lg:max-w-[calc(100%-1.5rem)] lg:rounded-2xl",
      ].join(" ")}
    >
      <div className="sticky top-0 z-10 flex items-start justify-between gap-2 px-4 pt-3.5 pb-2.5 bg-background/90 supports-[backdrop-filter]:backdrop-blur-md border-b border-border">
        {/* 모바일 손잡이 — 시트 확장/축소. 데스크탑에는 없다. */}
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          aria-expanded={expanded}
          aria-label={expanded ? "시트 줄이기" : "시트 펼치기"}
          className="lg:hidden shrink-0 grid place-items-center w-8 h-8 -ml-1 rounded-full text-foreground-muted hover:bg-border/50"
        >
          <ChevronUp
            size={16}
            className={`transition-transform duration-150 ${expanded ? "rotate-180" : ""}`}
          />
        </button>
        <div className="min-w-0 flex-1">
          <p className="text-xs text-foreground-muted">{data?.districtName ?? "상권 상세 분석"}</p>
          <h2 className="text-sm font-semibold truncate">{data?.trdarName ?? "…"}</h2>
          {data?.serviceName && data.salesMix && (
            <p className="text-xs text-foreground-muted mt-0.5">
              기준 업종 {data.serviceName} · {String(data.salesMix.yearQuarter).slice(0, 4)}년{" "}
              {String(data.salesMix.yearQuarter).slice(4)}분기
            </p>
          )}
        </div>
        {data && (
          <BookmarkButton
            targetType="area"
            targetKey={trdarCode}
            label={data.trdarName}
            className="mt-0.5"
          />
        )}
        <button
          type="button"
          onClick={onClose}
          aria-label="분석 시트 닫기"
          className="shrink-0 rounded-md p-1 text-foreground-muted hover:bg-border/50"
        >
          <X size={16} />
        </button>
      </div>

      <div className="p-4">
        {isLoading && (
          <div className="flex flex-col gap-3">
            <div className="skeleton h-16 rounded-xl" />
            <div className="skeleton h-32 rounded-xl" />
            <div className="skeleton h-32 rounded-xl" />
          </div>
        )}
        {isError && (
          <p className="text-sm text-foreground-muted">상권 상세를 불러오지 못했습니다.</p>
        )}
        {data && (
          <>
            {data.insights.length > 0 && (
              <div className="pb-1">
                <InsightList insights={data.insights} limit={4} />
              </div>
            )}
            {/* 인허가는 분기 팩트보다 시의성이 높다(어제 연 가게가 보인다) — 업종 랭킹 앞에 둔다 */}
            {data.permitChurn && (
              <Section icon={DoorOpen} title="인허가 업소 교체">
                <PermitChurnSection churn={data.permitChurn} />
              </Section>
            )}
            {/* 업종 랭킹은 매출 분해와 별개다 — 기준 업종이 안 잡혀도 목록은 뜬다 */}
            {data.serviceRanking.length > 0 && (
              <Section icon={Store} title="업종 랭킹">
                <ServiceRankingSection
                  ranking={data.serviceRanking}
                  currentCode={data.serviceCode}
                />
              </Section>
            )}
            {data.salesMix && (
              <Section icon={CalendarClock} title="매출 리듬">
                <SalesRhythmSection salesMix={data.salesMix} floating={data.floating} />
              </Section>
            )}
            {data.salesMix && (
              <Section icon={UsersRound} title="고객 프로필 (매출 기준)">
                <CustomerProfileSection salesMix={data.salesMix} />
              </Section>
            )}
            {data.demand && (
              <Section icon={Building2} title="배후 수요">
                <DemandSection demand={data.demand} facility={data.facility} />
              </Section>
            )}
            {data.spending && (
              <Section icon={Wallet} title="소비·구매력">
                <SpendingSection spending={data.spending} />
              </Section>
            )}
            {!data.salesMix && !data.demand && !data.spending && (
              <p className="text-sm text-foreground-muted">이 상권의 상세 데이터가 없습니다.</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
