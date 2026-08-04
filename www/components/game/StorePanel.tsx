"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Store } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

// 지도는 카카오 SDK를 런타임에 주입한다 — SSR에서 window에 닿으면 터진다
const MapView = dynamic(() => import("@/components/seoul/MapView"), { ssr: false });

const won = (v: number) => `${v.toLocaleString()}원`;
const signedWon = (v: number) => `${v >= 0 ? "+" : ""}${v.toLocaleString()}원`;
const toneOf = (v: number) => (v >= 0 ? "text-up" : "text-down");
// 만원 단위로 접는다 — 표에 원 단위를 그대로 쓰면 자릿수가 셀 수 없이 길어진다
const manwon = (v: number) =>
  v >= 1e8 ? `${(v / 1e8).toFixed(1)}억` : `${Math.round(v / 1e4).toLocaleString()}만`;

const MAX_PINS = 120; // 1,650개를 다 찍으면 지도가 버틴다는 보장이 없다 — 구 선택으로 좁힌다
const MAX_TABLE_ROWS = 200; // 표도 같은 이유로 자른다 — 아래 각주로 잘렸음을 알린다
// 백엔드 rule_coefficients.MAX_CONCURRENT_STORES와 같은 값 — 누르면 거절될 버튼을 열지 않는다
const MAX_STORES = 3;

// 폭 상한 — 대시보드 예외 폭(DESIGN.md §5), 투자 탭과 동일
const SHELL = "mx-auto w-full max-w-[1720px] px-4 sm:px-6";

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
  storeId: number | null; // 선택한 내 가게 — 있으면 우측 컬럼이 가게 상세로 바뀐다
  notice: string | null;
};

/**
 * 상권 창업 — 투자 탭과 같은 토스 골격이다.
 *
 *   [내 가게 슬림 바]
 *   [상권 표 (주인공, 내부 스크롤) | 지도·적합도·창업 폼 컬럼]
 *
 * 이전에는 안내문·가게 카드·결산 카드·폼·지도가 세로로 흘러 "긴 설정 페이지"처럼 보였다.
 * 상권 고르기가 이 화면의 본업이므로 상권 표를 주인공으로 세운다 — 토스 "주식 골라보기"의
 * 상권판이다(점포당 월매출·점포 수·폐업률이 스크리너 컬럼).
 */
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
  // 업종을 고르면 그 업종 기준으로 한 번 더 받는다 — 매출 실적이 있는 상권만 남기려면
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
  const districts = useMemo(
    () => [...new Set(rows.map((r) => r.districtName))].sort(),
    [rows],
  );
  // 업종을 골랐으면 **그 업종의 매출 실적이 있는 상권만** 남긴다. 실적이 없는 자리는
  // 창업 기준(점포당 월매출)을 세울 수 없어 백엔드가 거절한다 — 애초에 고를 수 없게 한다.
  const openableRows = draft.serviceCode
    ? (serviceRankingQ.data?.rows ?? []).filter(
        (r) => r.monthlySales !== null && r.monthlySales > 0,
      )
    : rows;
  // 표 순서는 점포당 월매출 내림차순 — "어디가 장사가 되는 자리인가"가 이 표의 질문이다
  const filtered: AreaRankingRow[] = useMemo(() => {
    const base = draft.district
      ? openableRows.filter((r) => r.districtName === draft.district)
      : openableRows;
    return [...base].sort((a, b) => (b.salesPerStore ?? -1) - (a.salesPerStore ?? -1));
  }, [openableRows, draft.district]);

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

  const serviceName = services.find((s) => s.code === draft.serviceCode)?.name;

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* 내 가게 슬림 바 — 투자 탭의 지갑 한 줄과 같은 층. 카드로 쌓지 않는다 */}
      <div
        className={`${SHELL} shrink-0 flex items-center gap-2 border-b border-border pb-2 overflow-x-auto whitespace-nowrap [scrollbar-width:none] [&::-webkit-scrollbar]:hidden`}
      >
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold shrink-0">
          <Store size={15} strokeWidth={2} className="text-brand" />
          내 가게
        </span>
        {stores.length === 0 && (
          <span className="text-xs text-foreground-muted">
            아직 없습니다 — 표에서 상권을 골라 첫 가게를 열어보세요
          </span>
        )}
        {stores.map((s) => {
          const active = s.storeId === draft.storeId;
          return (
            <button
              key={s.storeId}
              type="button"
              onClick={() => patch({ storeId: active ? null : s.storeId })}
              aria-pressed={active}
              className={`shrink-0 inline-flex items-baseline gap-1.5 h-8 px-3 rounded-full border text-xs font-medium transition-colors duration-150 ${
                active ? "border-brand bg-brand/8 text-foreground" : "border-border hover:bg-accent"
              }`}
            >
              {s.trdarName}
              <span className="text-foreground-muted">{s.serviceName}</span>
              <span className={`tabular-nums font-semibold ${toneOf(s.cumulativeProfitKrw)}`}>
                {signedWon(s.cumulativeProfitKrw)}
              </span>
            </button>
          );
        })}
        <span className="ml-auto shrink-0 text-xs text-foreground-muted">
          매출은 서울시 실데이터 · 임대료·인건비는 가정치 · 접속하지 않아도 장사합니다
        </span>
      </div>

      {draft.notice && (
        <div className={`${SHELL} shrink-0`}>
          <p className="mt-2 rounded-lg bg-brand/8 border border-brand/20 px-3 py-1.5 text-xs">
            {draft.notice}
          </p>
        </div>
      )}

      <div
        className={`${SHELL} flex-1 min-h-0 mt-3 overflow-y-auto lg:overflow-hidden lg:grid lg:grid-cols-[minmax(0,1fr)_420px] lg:gap-4`}
      >
        {/* 주인공 — 상권 스크리너 표(토스 "주식 골라보기"의 상권판) */}
        <section className="lg:h-full lg:min-h-0 flex flex-col rounded-2xl border border-border bg-surface overflow-hidden">
          <div className="shrink-0 flex items-center gap-2 px-3 pt-3 pb-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {/* 업종·자치구는 20개가 넘어 칩으로 못 편다 — 셀렉트를 칩 모양으로 입힌다 */}
            <select
              value={draft.serviceCode}
              // 업종이 바뀌면 목록 자체가 바뀐다 — 이전 선택을 들고 있으면
              // 새 업종으로는 열 수 없는 자리가 선택된 채로 남는다
              onChange={(e) => patch({ serviceCode: e.target.value, trdarCode: null })}
              className={`${SELECT_CHIP} ${draft.serviceCode ? SELECT_ACTIVE : ""}`}
            >
              <option value="">업종 전체</option>
              {services.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.name}
                </option>
              ))}
            </select>
            <select
              value={draft.district}
              onChange={(e) => patch({ district: e.target.value, trdarCode: null })}
              className={`${SELECT_CHIP} ${draft.district ? SELECT_ACTIVE : ""}`}
            >
              <option value="">자치구 전체</option>
              {districts.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <span className="shrink-0 text-xs text-foreground-muted">
              {serviceRankingQ.isLoading
                ? "찾는 중…"
                : `검색된 상권 ${filtered.length.toLocaleString()}곳`}
              {draft.serviceCode && serviceName && ` · ${serviceName} 실적 보유`}
            </span>
          </div>

          <div className="shrink-0 flex items-center gap-2.5 px-3 pb-1.5 text-xs text-foreground-muted border-b border-border">
            <span className="w-6 shrink-0">#</span>
            <span className="flex-1">상권</span>
            <span className="w-24 shrink-0 text-right">점포당 월매출</span>
            <span className="hidden md:block w-16 shrink-0 text-right">점포 수</span>
            <span className="hidden xl:block w-16 shrink-0 text-right">폐업률</span>
          </div>

          <ul className="flex-1 min-h-0 overflow-y-auto">
            {filtered.slice(0, MAX_TABLE_ROWS).map((r, i) => {
              const active = r.trdarCode === draft.trdarCode;
              return (
                <li key={r.trdarCode}>
                  <button
                    type="button"
                    // 상권을 고르면 우측이 창업 흐름으로 바뀐다 — 보고 있던 가게 상세는 닫는다
                    onClick={() => patch({ trdarCode: r.trdarCode, storeId: null })}
                    aria-current={active}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 text-left border-b border-border transition-colors ${
                      active ? "bg-accent" : "hover:bg-accent"
                    }`}
                  >
                    <span className="w-6 shrink-0 text-xs tabular-nums text-foreground-muted">
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium truncate">{r.trdarName}</span>
                      <span className="block text-xs text-foreground-muted truncate">
                        {r.districtName} {r.dongName} · {r.divisionName}
                      </span>
                    </span>
                    <span className="w-24 shrink-0 text-right text-sm font-medium tabular-nums">
                      {r.salesPerStore !== null ? manwon(r.salesPerStore) : "—"}
                    </span>
                    <span className="hidden md:block w-16 shrink-0 text-right text-sm tabular-nums text-foreground-muted">
                      {r.storeCount !== null ? r.storeCount.toLocaleString() : "—"}
                    </span>
                    <span
                      className={`hidden xl:block w-16 shrink-0 text-right text-sm tabular-nums ${
                        r.closureRate !== null && r.closureRate >= 0.05
                          ? "text-down"
                          : "text-foreground-muted"
                      }`}
                    >
                      {r.closureRate !== null ? `${(r.closureRate * 100).toFixed(1)}%` : "—"}
                    </span>
                  </button>
                </li>
              );
            })}
            {filtered.length === 0 && !rankingQ.isLoading && (
              <li className="px-3 py-8 text-center text-sm text-foreground-muted">
                조건에 맞는 상권이 없습니다.
              </li>
            )}
          </ul>

          {filtered.length > MAX_TABLE_ROWS && (
            <p className="shrink-0 px-3 py-1.5 text-xs text-foreground-muted border-t border-border">
              점포당 월매출 상위 {MAX_TABLE_ROWS}곳만 표시 — 업종·자치구로 좁히면 전부 보입니다.
            </p>
          )}
        </section>

        {/* 조연 — 가게를 골랐으면 가게 상세, 아니면 지도 + 적합도 + 창업 폼 */}
        <aside className="mt-4 lg:mt-0 lg:h-full lg:min-h-0 lg:overflow-y-auto flex flex-col gap-4 pb-4">
          {draft.storeId ? (
            <>
              <StoreDetailCard storeId={draft.storeId} />
              <SettlementCard />
            </>
          ) : (
            <>
              {/* 지도 — 표와 같은 목록을 본다. 표에서 고른 자리가 핀으로 강조된다 */}
              <div className="shrink-0 rounded-2xl border border-border bg-surface overflow-hidden h-56">
                <MapView
                  areas={filtered.slice(0, MAX_PINS).map((r) => ({
                    id: String(r.trdarCode),
                    lat: r.lat,
                    lng: r.lng,
                  }))}
                  selectedId={draft.trdarCode ? String(draft.trdarCode) : null}
                  onSelect={(id) => patch({ trdarCode: Number(id), storeId: null })}
                />
              </div>

              {!draft.trdarCode && (
                <p className="text-xs text-foreground-muted leading-relaxed">
                  {!draft.serviceCode
                    ? "업종을 고르면 그 업종으로 창업할 수 있는 상권만 남습니다. 표나 지도에서 자리를 골라보세요."
                    : `${serviceName ?? "이 업종"} 매출 기록이 있는 ${openableRows.length.toLocaleString()}곳이 남았습니다. 표나 지도에서 자리를 골라보세요.`}
                  {filtered.length > MAX_PINS &&
                    ` (지도에는 ${MAX_PINS}곳만 표시)`}
                </p>
              )}
              {draft.trdarCode && !draft.serviceCode && (
                <p className="text-xs text-foreground-muted">
                  <b className="text-foreground">{selected?.trdarName}</b> — 업종을 고르면 이 자리의
                  적합도를 진단합니다.
                </p>
              )}
              {fitnessQ.isLoading && (
                <p className="text-xs text-foreground-muted">적합도를 계산하는 중…</p>
              )}
              {fitnessQ.isError && (
                <p className="text-xs text-foreground-muted">
                  이 상권·업종 조합은 실데이터가 없어 창업할 수 없습니다.
                </p>
              )}

              {fitness && <StoreFitnessCard fitness={fitness} />}

              {fitness && (
                <div className="rounded-2xl border border-border bg-surface p-5">
                  <h3 className="text-sm font-bold tracking-tight">창업하기</h3>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <label className="text-xs text-foreground-muted">
                      투입 자본 (가능 {won(investable)})
                      <Input
                        type="number"
                        min={10_000}
                        step={100_000}
                        value={budget}
                        onChange={(e) =>
                          patch({ budgetKrw: Math.max(10_000, Number(e.target.value)) })
                        }
                        className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
                      />
                    </label>
                    <label className="text-xs text-foreground-muted">
                      직원 수
                      <Input
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

                  {/* 입력한 자본이 이 자리의 최소치에 못 미치면 실제로 나갈 금액을 먼저 알린다 */}
                  {!blockedReason && payment > budget && (
                    <p className="mt-2 text-xs text-foreground-muted">
                      이 자리는 최소 {won(payment)}이 필요합니다 — 입력한 {won(budget)} 대신 이
                      금액으로 창업합니다.
                    </p>
                  )}
                  {/* 자본에 비례해 규모가 정해진다 — 너무 작으면 열려도 손님이 오지 않는다.
                      막지는 않는다. 작게 들어가는 것도 선택이므로 결과만 먼저 알린다 */}
                  {!blockedReason && payment < fitness.assumedViableCapitalKrw && (
                    <p className="mt-2 text-xs text-up">
                      이 자본으로는 가게 규모가 너무 작아 하루 손님이 1명에 못 미칩니다 — 이
                      자리에서 장사가 되려면 {won(fitness.assumedViableCapitalKrw)}부터입니다.
                    </p>
                  )}
                  <Button
                    type="button"
                    onClick={() => open.mutate()}
                    disabled={open.isPending || blockedReason !== null}
                    size="lg"
                    className="mt-3 w-full"
                  >
                    {blockedReason ?? (open.isPending ? "개업 중…" : `${won(payment)}으로 창업하기`)}
                  </Button>
                </div>
              )}
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

// 셀렉트를 칩 모양으로 — 옵션이 20개가 넘어 칩 나열이 불가능한 축은 셀렉트가 맞다.
// 값이 걸리면 브랜드 톤(토스 스크리너의 파란 활성 칩 자리)으로 표시한다.
const SELECT_CHIP =
  "shrink-0 h-8 rounded-full border border-border bg-surface px-3 pr-7 text-xs font-medium text-foreground appearance-none bg-no-repeat bg-[right_0.6rem_center] bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2210%22%20height%3D%226%22%3E%3Cpath%20d%3D%22M1%201l4%204%204-4%22%20stroke%3D%22%236B7280%22%20stroke-width%3D%221.5%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%3C%2Fsvg%3E')]";
const SELECT_ACTIVE = "border-brand/40 bg-brand/8 text-brand";
