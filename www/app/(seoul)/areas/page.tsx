"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, MapPin, Search } from "lucide-react";
import { ApiError, fetchAreaRanking } from "@/lib/api";
import { useUIStore } from "@/lib/uiStore";
import type { AreaRankingRow } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

type SortKey =
  | "salesPerStore"
  | "monthlySales"
  | "storeCount"
  | "salesQoq"
  | "storeDensity"
  | "salesDensity";

type Grouping = "area" | "gu" | "division";

const SORT_COLUMNS: { key: SortKey; label: string; hint: string }[] = [
  { key: "salesPerStore", label: "점포당 매출", hint: "규모가 아니라 '돈이 되는가'" },
  { key: "monthlySales", label: "월 매출", hint: "상권 전체 규모" },
  { key: "storeCount", label: "점포수", hint: "경쟁 밀도" },
  { key: "salesQoq", label: "전분기 대비", hint: "성장 흐름" },
  { key: "storeDensity", label: "점포 밀도", hint: "면적당 경쟁 강도 — 규모 착시 제거" },
  { key: "salesDensity", label: "매출 밀도", hint: "면적당 수익력" },
];

// 면적 격차가 1,300배라 절대량만 보면 넓은 상권이 늘 이긴다. ha(10,000㎡)당으로 정규화한다.
const density = (value: number | null, areaSize: number | null) =>
  value != null && areaSize ? value / (areaSize / 10_000) : null;

const metric = (r: AreaRankingRow, key: SortKey): number | null => {
  if (key === "storeDensity") return density(r.storeCount, r.areaSize);
  if (key === "salesDensity") return density(r.monthlySales, r.areaSize);
  return r[key];
};

const quarterLabel = (yq: number | null) =>
  yq ? `${String(yq).slice(0, 4)}년 ${String(yq).slice(4)}분기` : "—";

const won = (v: number | null) => {
  if (v == null) return "—";
  if (v >= 100_000_000) return `${(v / 100_000_000).toFixed(1)}억`;
  return `${Math.round(v / 10_000).toLocaleString()}만`;
};

export default function AreasDirectoryPage() {
  // REACT_RULES 패턴 B: 필터·정렬 상태는 useState 여러 개가 아니라 단일 객체
  const [q, setQ] = useState<{
    text: string;
    gu: string;
    division: string;
    serviceCode: string;
    grouping: Grouping;
    compare: number[];
    sort: { key: SortKey; dir: "asc" | "desc" };
  }>({
    text: "",
    gu: "전체",
    division: "전체",
    serviceCode: "",
    grouping: "area",
    compare: [],
    sort: { key: "salesPerStore", dir: "desc" },
  });

  // 서버 필터는 걸지 않는다 — 1,650행을 한 번 받고 클라이언트에서 좁힌다(왕복 제거).
  const { data, isPending, isError, error } = useQuery({
    // 업종만 서버 왕복이다 — 집계 자체가 달라진다. 자치구·상권구분은 행 부분집합일
    // 뿐이라 클라이언트에서 좁힌다(이 구분을 지우면 조용히 틀린 숫자가 나온다).
    queryKey: ["area-ranking", q.serviceCode],
    queryFn: () => fetchAreaRanking({ serviceCode: q.serviceCode || undefined }),
  });

  const openAuth = useUIStore((s) => s.openAuth);
  const needsLogin = error instanceof ApiError && error.status === 401;

  const all = useMemo(() => data?.rows ?? [], [data]);
  const guList = useMemo(
    () => ["전체", ...Array.from(new Set(all.map((r) => r.districtName).filter(Boolean))).sort()],
    [all],
  );
  const divisionList = useMemo(
    () => ["전체", ...Array.from(new Set(all.map((r) => r.divisionName).filter(Boolean))).sort()],
    [all],
  );

  const rows = useMemo(() => {
    const filtered = all.filter(
      (r) =>
        (q.gu === "전체" || r.districtName === q.gu) &&
        (q.division === "전체" || r.divisionName === q.division) &&
        (!q.text || r.trdarName.includes(q.text) || r.dongName.includes(q.text)),
    );
    const { key, dir } = q.sort;
    return [...filtered].sort((a, b) => {
      const av = metric(a, key);
      const bv = metric(b, key);
      if (av == null && bv == null) return 0;
      if (av == null) return 1; // 팩트 없는 상권은 항상 뒤로
      if (bv == null) return -1;
      return dir === "asc" ? av - bv : bv - av;
    });
  }, [all, q]);

  // 자치구·상권구분 롤업 — 서버 GROUP BY를 만들지 않는다. 원자재가 이미 페이로드에 있다.
  // **주의**: 그룹의 점포당 매출은 avg(각 상권의 salesPerStore)가 아니라
  // sum(매출)/sum(점포)다. 비율의 평균 ≠ 합의 비율.
  const groups = useMemo(() => {
    if (q.grouping === "area") return null;
    const key = q.grouping === "gu" ? "districtName" : "divisionName";
    const acc = new Map<string, { name: string; n: number; sales: number; stores: number; area: number }>();
    for (const r of rows) {
      const k = r[key] || "미분류";
      const g = acc.get(k) ?? { name: k, n: 0, sales: 0, stores: 0, area: 0 };
      g.n += 1;
      g.sales += r.monthlySales ?? 0;
      g.stores += r.storeCount ?? 0;
      g.area += r.areaSize ?? 0;
      acc.set(k, g);
    }
    return [...acc.values()]
      .map((g) => ({
        ...g,
        salesPerStore: g.stores ? Math.round(g.sales / g.stores) : null,
        storeDensity: g.area ? g.stores / (g.area / 10_000) : null,
      }))
      .sort((a, b) => (b.salesPerStore ?? -1) - (a.salesPerStore ?? -1));
  }, [rows, q.grouping]);

  // "상위 몇 %" — 62개 업종·1,650상권 중 이 상권의 상대 위치. 절대값만으론 알 수 없다.
  const percentile = useMemo(() => {
    const vals = all
      .map((r) => metric(r, q.sort.key))
      .filter((v): v is number => v != null)
      .sort((a, b) => b - a);
    return (v: number | null) => {
      if (v == null || !vals.length) return null;
      const rank = vals.findIndex((x) => x <= v);
      return Math.max(1, Math.round(((rank < 0 ? vals.length : rank) / vals.length) * 100));
    };
  }, [all, q.sort.key]);

  // 비교는 최대 3곳 — 넘으면 가장 오래된 것을 밀어낸다(전용 라우트를 만들지 않는다,
  // 필요한 데이터가 이미 이 응답 안에 다 있다)
  const toggleCompare = (code: number) =>
    setQ((p) => ({
      ...p,
      compare: p.compare.includes(code)
        ? p.compare.filter((c) => c !== code)
        : [...p.compare, code].slice(-3),
    }));

  const compareRows = useMemo(
    () => q.compare.map((c) => all.find((r) => r.trdarCode === c)).filter(Boolean) as AreaRankingRow[],
    [q.compare, all],
  );

  const toggleSort = (key: SortKey) =>
    setQ((prev) => ({
      ...prev,
      sort: { key, dir: prev.sort.key === key && prev.sort.dir === "desc" ? "asc" : "desc" },
    }));

  // 비로그인도 이 화면까지는 들어온다 — 탭 게이팅의 basic 등급이 market을 포함하고,
  // 막히는 건 데이터 조회뿐이다. 필터와 "서울 0개 상권"을 남겨두면 막다른 길이 되므로
  // 화면 전체를 로그인 안내로 바꾼다.
  if (needsLogin) {
    return (
      <div className="min-h-[60vh] grid place-items-center p-6">
        <div className="max-w-sm w-full rounded-2xl bg-surface border border-border p-8 text-center">
          <span className="mx-auto grid place-items-center w-12 h-12 rounded-full bg-brand/10 text-brand">
            <MapPin size={22} strokeWidth={1.9} />
          </span>
          <h1 className="mt-4 text-lg font-bold tracking-tight">
            로그인하면 서울 상권을 전부 둘러볼 수 있어요
          </h1>
          <p className="mt-2 text-sm text-foreground-muted leading-relaxed">
            자치구·업종으로 좁혀 보고, 최대 3곳까지 나란히 비교할 수 있어요.
          </p>
          <Button
            onClick={() => openAuth("login")}
            className="mt-6"
          >
            로그인하기
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight">상권 둘러보기</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          서울 {all.length.toLocaleString()}개 상권 · {quarterLabel(data?.yearQuarter ?? null)} 기준.
          궁금한 상권을 고르면 지도와 상세 분석으로 이어집니다.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <label className="relative flex-1 min-w-[200px]">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground-muted"
          />
          <Input
            value={q.text}
            onChange={(e) => setQ((p) => ({ ...p, text: e.target.value }))}
            placeholder="상권명·동 이름으로 찾기"
            className="w-full pl-9 pr-3 py-2 rounded-xl bg-surface border border-border text-sm"
          />
        </label>
        <select
          value={q.gu}
          onChange={(e) => setQ((p) => ({ ...p, gu: e.target.value }))}
          className="px-3 py-2 rounded-xl bg-surface border border-border text-sm"
        >
          {guList.map((gu) => (
            <option key={gu}>{gu}</option>
          ))}
        </select>
        <select
          value={q.serviceCode}
          onChange={(e) => setQ((p) => ({ ...p, serviceCode: e.target.value }))}
          className="px-3 py-2 rounded-xl bg-surface border border-border text-sm"
        >
          <option value="">전 업종</option>
          {(data?.services ?? []).map((s) => (
            <option key={s.code} value={s.code}>
              {s.name}
            </option>
          ))}
        </select>
        <select
          value={q.division}
          onChange={(e) => setQ((p) => ({ ...p, division: e.target.value }))}
          className="px-3 py-2 rounded-xl bg-surface border border-border text-sm"
        >
          {divisionList.map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-1">
        <span className="text-xs text-foreground-muted mr-1">집계 단위</span>
        {(
          [
            ["area", "상권"],
            ["gu", "자치구"],
            ["division", "상권 유형"],
          ] as [Grouping, string][]
        ).map(([g, label]) => (
          <button
            key={g}
            onClick={() => setQ((p) => ({ ...p, grouping: g }))}
            className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
              q.grouping === g ? "bg-brand/10 text-brand" : "text-foreground-muted hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {SORT_COLUMNS.map(({ key, label, hint }) => (
          <button
            key={key}
            onClick={() => toggleSort(key)}
            title={hint}
            className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              q.sort.key === key
                ? "bg-brand/10 text-brand border-brand/30"
                : "bg-surface text-foreground-muted border-border hover:text-foreground"
            }`}
          >
            {label}
            {q.sort.key === key &&
              (q.sort.dir === "desc" ? <ArrowDown size={12} /> : <ArrowUp size={12} />)}
          </button>
        ))}
      </div>

      {isPending && <p className="text-sm text-foreground-muted">상권을 불러오는 중이에요…</p>}
      {isError && <p className="text-sm text-foreground-muted">상권 목록을 불러오지 못했습니다.</p>}
      {!isPending && !isError && rows.length === 0 && (
        <p className="text-sm text-foreground-muted">조건에 맞는 상권이 없어요.</p>
      )}

      {groups ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {groups.map((g) => (
            <div key={g.name} className="rounded-2xl bg-surface border border-border p-4">
              <p className="font-semibold">{g.name}</p>
              <p className="text-xs text-foreground-muted">{g.n.toLocaleString()}개 상권</p>
              <dl className="mt-3 space-y-1.5 text-sm">
                <div className="flex items-center justify-between">
                  <dt className="text-foreground-muted">점포당 매출</dt>
                  <dd className="font-medium tabular-nums">{won(g.salesPerStore)}원</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-foreground-muted">월 매출 합</dt>
                  <dd className="font-medium tabular-nums">{won(g.sales)}원</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-foreground-muted">점포 밀도</dt>
                  <dd className="font-medium tabular-nums">
                    {g.storeDensity ? `${g.storeDensity.toFixed(1)}개/ha` : "—"}
                  </dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {rows.slice(0, 120).map((r) => (
            <AreaCard
              key={r.trdarCode}
              row={r}
              pct={percentile(metric(r, q.sort.key))}
              selected={q.compare.includes(r.trdarCode)}
              onCompare={() => toggleCompare(r.trdarCode)}
            />
          ))}
        </div>
      )}
      {compareRows.length > 0 && <CompareBar rows={compareRows} onClear={() => setQ((p) => ({ ...p, compare: [] }))} />}

      {rows.length > 120 && (
        <p className="text-xs text-foreground-muted text-center">
          상위 120곳만 보여주고 있어요. 자치구·업종으로 좁혀보세요. (전체 {rows.length.toLocaleString()}곳)
        </p>
      )}
    </div>
  );
}

function AreaCard({
  row,
  pct,
  selected,
  onCompare,
}: {
  row: AreaRankingRow;
  pct: number | null;
  selected: boolean;
  onCompare: () => void;
}) {
  const up = row.salesQoq != null && row.salesQoq > 0;
  return (
    <div className="relative">
      <button
        onClick={onCompare}
        title="비교에 담기 (최대 3곳)"
        className={`absolute right-3 top-3 z-10 w-5 h-5 rounded-md border text-xs font-bold transition-colors ${
          selected ? "bg-brand text-white border-brand" : "bg-surface border-border text-transparent"
        }`}
      >
        ✓
      </button>
    <Link
      href={`/market?trdar=${row.trdarCode}`}
      className="block rounded-2xl bg-surface border border-border p-4 hover:border-brand/40 transition-colors"
    >
      <div className="flex items-start gap-2">
        <span className="grid place-items-center w-10 h-10 rounded-xl bg-brand/10 text-brand shrink-0">
          <MapPin size={16} strokeWidth={1.9} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold truncate">
            {row.trdarName}
            {pct !== null && (
              <span className="ml-1.5 text-xs font-medium px-1.5 py-0.5 rounded-full bg-brand/10 text-brand align-middle">
                상위 {pct}%
              </span>
            )}
          </p>
          <p className="text-xs text-foreground-muted truncate">
            {row.districtName} {row.dongName} · {row.divisionName}
          </p>
        </div>
      </div>
      <dl className="mt-3 space-y-1.5 text-sm">
        <div className="flex items-center justify-between">
          <dt className="text-foreground-muted">점포당 매출</dt>
          <dd className="font-medium tabular-nums">{won(row.salesPerStore)}원</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-foreground-muted">점포수</dt>
          <dd className="font-medium tabular-nums">
            {row.storeCount != null ? `${row.storeCount.toLocaleString()}개` : "—"}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-foreground-muted">전분기 대비</dt>
          <dd
            className={`font-medium tabular-nums ${
              row.salesQoq == null ? "" : up ? "text-emerald-600" : "text-rose-600"
            }`}
          >
            {row.salesQoq == null ? "—" : `${up ? "+" : ""}${row.salesQoq}%`}
          </dd>
        </div>
      </dl>
    </Link>
    </div>
  );
}

// 비교 시트 — 메모리의 행 3개면 충분하다. 새 라우트·새 API를 만들지 않는다.
function CompareBar({ rows, onClear }: { rows: AreaRankingRow[]; onClear: () => void }) {
  const METRICS: [string, (r: AreaRankingRow) => string][] = [
    ["점포당 매출", (r) => `${won(r.salesPerStore)}원`],
    ["월 매출", (r) => `${won(r.monthlySales)}원`],
    ["점포수", (r) => (r.storeCount != null ? `${r.storeCount.toLocaleString()}개` : "—")],
    ["전분기 대비", (r) => (r.salesQoq == null ? "—" : `${r.salesQoq > 0 ? "+" : ""}${r.salesQoq}%`)],
    ["점포 밀도", (r) => {
      const d = density(r.storeCount, r.areaSize);
      return d ? `${d.toFixed(1)}개/ha` : "—";
    }],
    ["폐업률", (r) => (r.closureRate != null ? `${r.closureRate}%` : "—")],
  ];
  return (
    <div className="sticky bottom-4 rounded-2xl bg-surface border border-brand/30 shadow-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-semibold">상권 비교 ({rows.length}/3)</p>
        <button onClick={onClear} className="text-xs text-foreground-muted hover:text-foreground">
          비우기
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-foreground-muted">
              <th className="text-left font-normal py-1 pr-3">지표</th>
              {rows.map((r) => (
                <th key={r.trdarCode} className="text-right font-semibold text-foreground py-1 px-2 whitespace-nowrap">
                  {r.trdarName}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METRICS.map(([label, render]) => (
              <tr key={label} className="border-t border-border">
                <td className="text-xs text-foreground-muted py-1.5 pr-3 whitespace-nowrap">{label}</td>
                {rows.map((r) => (
                  <td key={r.trdarCode} className="text-right tabular-nums py-1.5 px-2 whitespace-nowrap">
                    {render(r)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
