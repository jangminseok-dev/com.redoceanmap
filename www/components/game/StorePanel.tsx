"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info } from "lucide-react";
import SettlementCard from "@/components/game/SettlementCard";
import StoreDetailCard from "@/components/game/StoreDetailCard";
import StoreFitnessCard from "@/components/game/StoreFitnessCard";
import {
  fetchAreaRanking,
  fetchGameAreaFitness,
  fetchGameStores,
  fetchGameWallet,
  openGameStore,
} from "@/lib/api";
import type { AreaRankingRow } from "@/lib/types";

// 지도는 카카오 SDK를 런타임에 주입한다 — SSR에서 window에 닿으면 터진다
const MapView = dynamic(() => import("@/components/seoul/MapView"), { ssr: false });

const won = (v: number) => `${v.toLocaleString()}원`;
const MAX_PINS = 120; // 1,650개를 다 찍으면 지도가 버틴다는 보장이 없다 — 구 선택으로 좁힌다

type Draft = {
  district: string;
  serviceCode: string;
  trdarCode: number | null;
  budgetKrw: number;
  facilityScore: number;
  staffCount: number;
  storeId: number | null; // 선택한 내 가게
  notice: string | null;
};

export default function StorePanel() {
  // 창업 폼은 값이 서로 물려 있어 한 객체로 든다(REACT_RULES 패턴 B)
  const [draft, setDraft] = useState<Draft>({
    district: "",
    serviceCode: "",
    trdarCode: null,
    budgetKrw: 500_000,
    facilityScore: 300,
    staffCount: 2,
    storeId: null,
    notice: null,
  });
  const patch = (next: Partial<Draft>) => setDraft((prev) => ({ ...prev, ...next }));
  const queryClient = useQueryClient();

  // 상권 1,650행 + 업종 목록을 한 번에 받는다(admin/areas 선례 — 왕복보다 클라이언트 필터가 빠르다)
  const rankingQ = useQuery({
    queryKey: ["game-area-ranking"],
    queryFn: () => fetchAreaRanking({}),
    staleTime: 30 * 60_000,
  });
  const walletQ = useQuery({ queryKey: ["game-wallet"], queryFn: fetchGameWallet });
  const storesQ = useQuery({ queryKey: ["game-stores"], queryFn: fetchGameStores });

  const fitnessQ = useQuery({
    queryKey: ["game-fitness", draft.trdarCode, draft.serviceCode],
    queryFn: () => fetchGameAreaFitness(draft.trdarCode!, draft.serviceCode),
    enabled: !!draft.trdarCode && !!draft.serviceCode,
  });

  const open = useMutation({
    mutationFn: () =>
      openGameStore({
        trdarCode: draft.trdarCode!,
        serviceCode: draft.serviceCode,
        budgetKrw: draft.budgetKrw,
        facilityScore: draft.facilityScore,
        staffCount: draft.staffCount,
        priceFactor: 1.0,
      }),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["game-stores"] });
      queryClient.invalidateQueries({ queryKey: ["game-wallet"] });
      patch({
        storeId: r.storeId,
        notice: `${r.trdarName}에 ${r.serviceName} 개업 — 규모 ${(r.storeScale * 100).toFixed(1)}% · 보증금 ${won(r.depositKrw)}`,
      });
    },
    onError: (e) =>
      patch({ notice: e instanceof Error ? e.message : "창업에 실패했습니다." }),
  });

  const rows = rankingQ.data?.rows ?? [];
  const services = rankingQ.data?.services ?? [];
  const districts = [...new Set(rows.map((r) => r.districtName))].sort();
  const filtered: AreaRankingRow[] = (
    draft.district ? rows.filter((r) => r.districtName === draft.district) : rows
  ).slice(0, MAX_PINS);
  const selected = rows.find((r) => r.trdarCode === draft.trdarCode);
  const stores = storesQ.data ?? [];
  const investable = walletQ.data?.investableKrw ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 border border-amber-200 px-3 py-1 text-xs font-medium text-amber-800">
          <Info size={13} strokeWidth={2} />
          매출은 서울시 상권 실데이터 기준 · 임대료·인건비는 가정치
        </span>
        <p className="text-sm text-foreground-muted">
          접속하지 않는 동안에도 가게는 장사합니다.
        </p>
      </div>

      {/* 내 가게 */}
      {stores.length > 0 && (
        <section>
          <h2 className="text-sm font-bold tracking-tight mb-2">내 가게</h2>
          <ul className="flex flex-wrap gap-2">
            {stores.map((s) => {
              const active = s.storeId === draft.storeId;
              return (
                <li key={s.storeId}>
                  <button
                    type="button"
                    onClick={() => patch({ storeId: active ? null : s.storeId })}
                    aria-pressed={active}
                    className={`px-3 py-2 rounded-xl border text-left transition-colors ${
                      active ? "border-brand bg-brand/8" : "border-border hover:bg-black/[0.03]"
                    }`}
                  >
                    <span className="block text-sm font-medium">{s.trdarName}</span>
                    <span className="block text-[11px] text-foreground-muted">
                      {s.serviceName} · {s.daysOpen}일 ·{" "}
                      <span
                        className={
                          s.cumulativeProfitKrw >= 0 ? "text-[#DC2626]" : "text-[#2563EB]"
                        }
                      >
                        {s.cumulativeProfitKrw >= 0 ? "+" : ""}
                        {s.cumulativeProfitKrw.toLocaleString()}원
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {draft.storeId && (
            <div className="mt-3">
              <StoreDetailCard storeId={draft.storeId} />
            </div>
          )}
          <div className="mt-4">
            <SettlementCard />
          </div>
        </section>
      )}

      {draft.notice && (
        <p className="rounded-xl bg-brand/8 border border-brand/20 px-4 py-2.5 text-sm">
          {draft.notice}
        </p>
      )}

      {/* 창업 */}
      <section>
        <h2 className="text-sm font-bold tracking-tight mb-2">새 가게 열기</h2>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs text-foreground-muted">
            자치구
            <select
              value={draft.district}
              onChange={(e) => patch({ district: e.target.value, trdarCode: null })}
              className="mt-1 w-full h-10 px-2 rounded-xl border border-border bg-background text-sm text-foreground"
            >
              <option value="">전체</option>
              {districts.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>

          <label className="text-xs text-foreground-muted">
            업종
            <select
              value={draft.serviceCode}
              onChange={(e) => patch({ serviceCode: e.target.value })}
              className="mt-1 w-full h-10 px-2 rounded-xl border border-border bg-background text-sm text-foreground"
            >
              <option value="">선택하세요</option>
              {services.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>

          <label className="text-xs text-foreground-muted">
            투입 자본 (가능 {won(investable)})
            <input
              type="number"
              min={10_000}
              step={100_000}
              value={draft.budgetKrw}
              onChange={(e) => patch({ budgetKrw: Math.max(10_000, Number(e.target.value)) })}
              className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
            />
          </label>

          <label className="text-xs text-foreground-muted">
            시설 점수 (좌석 {Math.floor(draft.facilityScore / 10)}석)
            <input
              type="number"
              min={10}
              max={2000}
              step={50}
              value={draft.facilityScore}
              onChange={(e) =>
                patch({
                  facilityScore: Math.min(2000, Math.max(10, Number(e.target.value))),
                })
              }
              className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
            />
          </label>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="rounded-2xl border border-border bg-surface overflow-hidden h-72 lg:h-[26rem]">
            <MapView
              areas={filtered.map((r) => ({
                id: String(r.trdarCode),
                lat: r.lat,
                lng: r.lng,
              }))}
              selectedId={draft.trdarCode ? String(draft.trdarCode) : null}
              onSelect={(id) => patch({ trdarCode: Number(id) })}
            />
          </div>

          <div className="space-y-3">
            {selected && (
              <p className="text-sm">
                <span className="font-medium">{selected.trdarName}</span>
                <span className="text-foreground-muted">
                  {" "}
                  · {selected.districtName} {selected.dongName}
                </span>
              </p>
            )}
            {!draft.trdarCode && (
              <p className="text-sm text-foreground-muted">
                지도에서 상권을 고르세요. 자치구를 선택하면 핀이 좁혀집니다
                {rows.length > MAX_PINS && ` (전체 ${rows.length.toLocaleString()}곳 중 ${MAX_PINS}곳 표시)`}.
              </p>
            )}
            {draft.trdarCode && !draft.serviceCode && (
              <p className="text-sm text-foreground-muted">업종을 고르면 적합도를 진단합니다.</p>
            )}
            {fitnessQ.isLoading && (
              <p className="text-sm text-foreground-muted">적합도를 계산하는 중…</p>
            )}
            {fitnessQ.isError && (
              <p className="text-sm text-foreground-muted">
                이 상권·업종 조합은 실데이터가 없어 창업할 수 없습니다.
              </p>
            )}
            {fitnessQ.data && <StoreFitnessCard fitness={fitnessQ.data} />}

            {fitnessQ.data && (
              <button
                type="button"
                onClick={() => open.mutate()}
                disabled={open.isPending || draft.budgetKrw > investable}
                className="w-full h-11 rounded-xl bg-brand text-white text-sm font-semibold hover:bg-brand-deep disabled:opacity-40 transition-colors"
              >
                {draft.budgetKrw > investable
                  ? "투자 가능 금액을 넘습니다"
                  : open.isPending
                    ? "개업 중…"
                    : `${won(draft.budgetKrw)}으로 창업하기`}
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
