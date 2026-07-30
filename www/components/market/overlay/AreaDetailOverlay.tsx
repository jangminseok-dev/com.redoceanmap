"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, CalendarClock, DoorOpen, Store, UsersRound, Wallet, X } from "lucide-react";
import { fetchAreaDetail } from "@/lib/api";
import InsightList from "@/components/common/InsightList";
import CustomerProfileSection from "./CustomerProfileSection";
import DemandSection from "./DemandSection";
import SalesRhythmSection from "./SalesRhythmSection";
import PermitChurnSection from "./PermitChurnSection";
import ServiceRankingSection from "./ServiceRankingSection";
import SpendingSection from "./SpendingSection";

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
    <section>
      <h3 className="flex items-center gap-1.5 text-xs font-semibold text-foreground-muted uppercase tracking-wide mb-2">
        <Icon size={13} strokeWidth={2} />
        {title}
      </h3>
      {children}
    </section>
  );
}

// 지도 위 반투명 분석 오버레이 — 열림/닫힘은 URL(?trdar / &ov=0)이 단일 진실
export default function AreaDetailOverlay({
  trdarCode,
  serviceCode,
  onClose,
}: {
  trdarCode: string;
  serviceCode?: string;
  onClose: () => void;
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["area-detail", trdarCode, serviceCode],
    queryFn: () => fetchAreaDetail(trdarCode, serviceCode),
    enabled: !!trdarCode,
    retry: false, // 404(미존재 상권)를 재시도 없이 바로 에러 문구로
  });

  return (
    <div className="absolute inset-3 lg:inset-auto lg:right-3 lg:top-3 lg:bottom-3 lg:w-[400px] lg:max-w-[calc(100%-1.5rem)] rounded-2xl border border-border bg-background/90 backdrop-blur-md shadow-xl overflow-y-auto z-10">
      <div className="sticky top-0 flex items-start justify-between gap-2 px-4 pt-3.5 pb-2.5 bg-background/90 backdrop-blur-md border-b border-border">
        <div className="min-w-0">
          <p className="text-[10px] text-foreground-muted">{data?.districtName ?? "상권 상세 분석"}</p>
          <h2 className="text-sm font-semibold truncate">{data?.trdarName ?? "…"}</h2>
          {data?.serviceName && data.salesMix && (
            <p className="text-[10px] text-foreground-muted mt-0.5">
              기준 업종 {data.serviceName} · {String(data.salesMix.yearQuarter).slice(0, 4)}년{" "}
              {String(data.salesMix.yearQuarter).slice(4)}분기
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="분석 오버레이 닫기"
          className="shrink-0 rounded-md p-1 text-foreground-muted hover:bg-border/50"
        >
          <X size={16} />
        </button>
      </div>

      <div className="p-4 flex flex-col gap-5">
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
              <div className="rounded-xl border border-border bg-background px-3 py-2.5">
                <InsightList insights={data.insights} />
              </div>
            )}
            {/* 인허가는 분기 팩트보다 시의성이 높다(어제 연 가게가 보인다) — 업종 랭킹 앞에 둔다 */}
            {data.permitChurn && (
              <Section icon={DoorOpen} title="요즘 뭐가 열고 닫나">
                <PermitChurnSection churn={data.permitChurn} />
              </Section>
            )}
            {/* 업종 랭킹은 매출 분해와 별개다 — 기준 업종이 안 잡혀도 목록은 뜬다 */}
            {data.serviceRanking.length > 0 && (
              <Section icon={Store} title="이 자리에서 뭐가 되나 (업종별)">
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
