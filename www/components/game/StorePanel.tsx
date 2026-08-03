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
  fetchGameSettlements,
  fetchGameStores,
  fetchGameWallet,
  openGameStore,
} from "@/lib/api";
import type { AreaRankingRow } from "@/lib/types";

// 지도는 카카오 SDK를 런타임에 주입한다 — SSR에서 window에 닿으면 터진다
const MapView = dynamic(() => import("@/components/seoul/MapView"), { ssr: false });

const won = (v: number) => `${v.toLocaleString()}원`;
const MAX_PINS = 120; // 1,650개를 다 찍으면 지도가 버틴다는 보장이 없다 — 구 선택으로 좁힌다
// 백엔드 rule_coefficients.MAX_CONCURRENT_STORES와 같은 값 — 누르면 거절될 버튼을 열지 않는다
const MAX_STORES = 3;

/**
 * 지금 창업을 누르면 거절될 이유. `null`이면 버튼은 **반드시 성공한다**.
 *
 * 백엔드 `store_open_interactor`의 거절 조건을 화면 쪽에서 미리 답하는 것이다 —
 * 순서도 그쪽과 같게 둔다(시즌 → 자료 → 가게 수 → 흑자 조건 → 자본).
 */
function blockedBecause(s: {
  seasonOver: boolean;
  openable: boolean;
  openStoreCount: number;
  profitableQuarters: number;
  payment: number;
  investable: number;
}): string | null {
  if (s.seasonOver) return "시즌이 종료되어 새로 창업할 수 없습니다";
  if (!s.openable) return "이 상권엔 이 업종의 매출 기록이 없어 창업할 수 없습니다";
  if (s.openStoreCount >= MAX_STORES)
    return `가게는 동시에 ${MAX_STORES}곳까지만 운영할 수 있습니다`;
  if (s.openStoreCount > s.profitableQuarters)
    return `${s.openStoreCount + 1}호점은 흑자 분기 결산 ${s.openStoreCount}회가 필요합니다 (현재 ${s.profitableQuarters}회)`;
  if (s.payment > s.investable)
    return `이 자리는 최소 ${won(s.payment)}이 필요합니다 (가능 ${won(s.investable)})`;
  return null;
}

type Draft = {
  district: string;
  serviceCode: string;
  trdarCode: number | null;
  budgetKrw: number;
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
  // 업종을 고르면 그 업종 기준으로 한 번 더 받는다 — 매출 실적이 있는 상권만 핀으로 남기려면
  // 업종별 집계가 필요하다. 자치구·업종 목록은 위 쿼리가 계속 들고 있어 화면이 깜빡이지 않는다.
  const serviceRankingQ = useQuery({
    queryKey: ["game-area-ranking", draft.serviceCode],
    queryFn: () => fetchAreaRanking({ serviceCode: draft.serviceCode }),
    enabled: !!draft.serviceCode,
    staleTime: 30 * 60_000,
  });
  const walletQ = useQuery({ queryKey: ["game-wallet"], queryFn: fetchGameWallet });
  const storesQ = useQuery({ queryKey: ["game-stores"], queryFn: fetchGameStores });

  const fitnessQ = useQuery({
    queryKey: ["game-fitness", draft.trdarCode, draft.serviceCode],
    queryFn: () => fetchGameAreaFitness(draft.trdarCode!, draft.serviceCode),
    enabled: !!draft.trdarCode && !!draft.serviceCode,
  });

  const rows = rankingQ.data?.rows ?? [];
  const services = rankingQ.data?.services ?? [];
  const districts = [...new Set(rows.map((r) => r.districtName))].sort();
  // 업종을 골랐으면 **그 업종의 매출 실적이 있는 상권만** 남긴다. 실적이 없는 자리는
  // 창업 기준(점포당 월매출)을 세울 수 없어 백엔드가 거절한다 — 애초에 고를 수 없게 한다.
  const openableRows = draft.serviceCode
    ? (serviceRankingQ.data?.rows ?? []).filter(
        (r) => r.monthlySales !== null && r.monthlySales > 0,
      )
    : rows;
  const filtered: AreaRankingRow[] = (
    draft.district
      ? openableRows.filter((r) => r.districtName === draft.district)
      : openableRows
  ).slice(0, MAX_PINS);
  const selected = rows.find((r) => r.trdarCode === draft.trdarCode);
  const stores = storesQ.data ?? [];
  const openStoreCount = stores.filter((s) => s.status === "open").length;
  const investable = walletQ.data?.investableKrw ?? 0;
  // 기본값이 잔액을 넘으면 폼이 열리자마자 비활성 상태가 된다 — 가능액으로 눌러 둔다
  const budget = Math.min(draft.budgetKrw, Math.max(10_000, investable));

  // n+1호점은 흑자 분기 결산 n회가 필요하다(백엔드 store_open_interactor와 같은 규칙).
  // 1호점은 조건이 없으므로 가게가 있을 때만 결산을 본다. 키는 SettlementCard와 공유한다.
  const settlementsQ = useQuery({
    queryKey: ["game-settlements"],
    queryFn: fetchGameSettlements,
    enabled: openStoreCount > 0,
  });
  const profitableQuarters = (settlementsQ.data?.settlements ?? []).filter(
    (s) => s.profitKrw > 0,
  ).length;

  const fitness = fitnessQ.data;
  // 화면이 제시하는 금액은 **반드시 통과하는 금액**이어야 한다 — 자리마다 최소 자본이
  // 다르므로(점포당 매출 × 임대료 입지계수) 모자라면 그 경계값으로 올려 보낸다.
  const payment = Math.max(budget, fitness?.assumedMinimumCapitalKrw ?? 0);
  const blockedReason = !fitness
    ? null
    : blockedBecause({
        seasonOver: walletQ.data?.seasonOver ?? false,
        openable: fitness.openable,
        openStoreCount,
        profitableQuarters,
        payment,
        investable,
      });

  const open = useMutation({
    mutationFn: () =>
      openGameStore({
        trdarCode: draft.trdarCode!,
        serviceCode: draft.serviceCode,
        budgetKrw: payment,
        staffCount: draft.staffCount,
        priceFactor: 1.0,
      }),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["game-stores"] });
      queryClient.invalidateQueries({ queryKey: ["game-wallet"] });
      patch({
        storeId: r.storeId,
        notice:
          `${r.trdarName}에 ${r.serviceName} 개업 — 규모 ${(r.storeScale * 100).toFixed(1)}% · ` +
          `좌석 ${r.seatCount}석 · 하루 ${r.dailyCapacityCustomers}명 수용` +
          `(포장 ${Math.round(r.takeoutRatio * 100)}%) · 보증금 ${won(r.depositKrw)}`,
      });
    },
    onError: (e) =>
      patch({ notice: e instanceof Error ? e.message : "창업에 실패했습니다." }),
  });

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
              // 업종이 바뀌면 핀 목록 자체가 바뀐다 — 이전 선택을 들고 있으면
              // 새 업종으로는 열 수 없는 자리가 선택된 채로 남는다
              onChange={(e) => patch({ serviceCode: e.target.value, trdarCode: null })}
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
              value={budget}
              onChange={(e) => patch({ budgetKrw: Math.max(10_000, Number(e.target.value)) })}
              className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
            />
          </label>

          <label className="text-xs text-foreground-muted">
            직원 수
            <input
              type="number"
              min={0}
              max={20}
              step={1}
              value={draft.staffCount}
              onChange={(e) =>
                patch({ staffCount: Math.min(20, Math.max(0, Number(e.target.value))) })
              }
              className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
            />
          </label>
        </div>

        <p className="mt-2 text-xs text-foreground-muted">
          시설 점수(좌석·회전율)는 투입 자본과 이 상권의 예상 수요에서 자동으로 정해집니다.
        </p>

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
                {!draft.serviceCode
                  ? "업종을 고르면 그 업종으로 창업할 수 있는 상권만 핀으로 남습니다."
                  : serviceRankingQ.isLoading
                    ? "이 업종으로 창업할 수 있는 상권을 찾는 중…"
                    : `지도에 남은 핀은 ${services.find((s) => s.code === draft.serviceCode)?.name ?? "이 업종"} 매출 기록이 있는 ${openableRows.length.toLocaleString()}곳입니다.`}{" "}
                자치구를 선택하면 더 좁혀집니다
                {openableRows.length > MAX_PINS &&
                  ` (${openableRows.length.toLocaleString()}곳 중 ${MAX_PINS}곳 표시)`}
                .
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
            {fitness && <StoreFitnessCard fitness={fitness} />}

            {fitness && (
              <>
                {/* 입력한 자본이 이 자리의 최소치에 못 미치면 실제로 나갈 금액을 먼저 알린다 */}
                {!blockedReason && payment > budget && (
                  <p className="text-xs text-foreground-muted">
                    이 자리는 최소 {won(payment)}이 필요합니다 — 입력한 {won(budget)} 대신 이
                    금액으로 창업합니다.
                  </p>
                )}
                {/* 자본에 비례해 규모가 정해진다 — 너무 작으면 열려도 손님이 오지 않는다.
                    막지는 않는다. 작게 들어가는 것도 선택이므로 결과만 먼저 알린다 */}
                {!blockedReason && payment < fitness.assumedViableCapitalKrw && (
                  <p className="text-xs text-[#DC2626]">
                    이 자본으로는 가게 규모가 너무 작아 하루 손님이 1명에 못 미칩니다 —
                    이 자리에서 장사가 되려면 {won(fitness.assumedViableCapitalKrw)}부터입니다.
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => open.mutate()}
                  disabled={open.isPending || blockedReason !== null}
                  className="w-full h-11 rounded-xl bg-brand text-white text-sm font-semibold hover:bg-brand-deep disabled:opacity-40 transition-colors"
                >
                  {blockedReason ??
                    (open.isPending ? "개업 중…" : `${won(payment)}으로 창업하기`)}
                </button>
              </>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
