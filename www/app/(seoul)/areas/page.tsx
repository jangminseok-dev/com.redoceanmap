"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, MapPin, Search } from "lucide-react";
import { fetchAreaRanking } from "@/lib/api";
import type { AreaRankingRow } from "@/lib/types";

type SortKey = "salesPerStore" | "monthlySales" | "storeCount" | "salesQoq";

const SORT_COLUMNS: { key: SortKey; label: string; hint: string }[] = [
  { key: "salesPerStore", label: "점포당 매출", hint: "규모가 아니라 '돈이 되는가'" },
  { key: "monthlySales", label: "월 매출", hint: "상권 전체 규모" },
  { key: "storeCount", label: "점포수", hint: "경쟁 밀도" },
  { key: "salesQoq", label: "전분기 대비", hint: "성장 흐름" },
];

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
    sort: { key: SortKey; dir: "asc" | "desc" };
  }>({ text: "", gu: "전체", division: "전체", sort: { key: "salesPerStore", dir: "desc" } });

  // 서버 필터는 걸지 않는다 — 1,650행을 한 번 받고 클라이언트에서 좁힌다(왕복 제거).
  const { data, isPending, isError } = useQuery({
    queryKey: ["area-ranking"],
    queryFn: () => fetchAreaRanking({}),
  });

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
      const av = a[key];
      const bv = b[key];
      if (av == null && bv == null) return 0;
      if (av == null) return 1; // 팩트 없는 상권은 항상 뒤로
      if (bv == null) return -1;
      return dir === "asc" ? av - bv : bv - av;
    });
  }, [all, q]);

  const toggleSort = (key: SortKey) =>
    setQ((prev) => ({
      ...prev,
      sort: { key, dir: prev.sort.key === key && prev.sort.dir === "desc" ? "asc" : "desc" },
    }));

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
          <input
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
          value={q.division}
          onChange={(e) => setQ((p) => ({ ...p, division: e.target.value }))}
          className="px-3 py-2 rounded-xl bg-surface border border-border text-sm"
        >
          {divisionList.map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
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

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {rows.slice(0, 120).map((r) => (
          <AreaCard key={r.trdarCode} row={r} />
        ))}
      </div>
      {rows.length > 120 && (
        <p className="text-xs text-foreground-muted text-center">
          상위 120곳만 보여주고 있어요. 자치구·업종으로 좁혀보세요. (전체 {rows.length.toLocaleString()}곳)
        </p>
      )}
    </div>
  );
}

function AreaCard({ row }: { row: AreaRankingRow }) {
  const up = row.salesQoq != null && row.salesQoq > 0;
  return (
    <Link
      href={`/market?trdar=${row.trdarCode}`}
      className="block rounded-2xl bg-surface border border-border p-4 hover:border-brand/40 transition-colors"
    >
      <div className="flex items-start gap-2">
        <span className="grid place-items-center w-9 h-9 rounded-xl bg-brand/10 text-brand shrink-0">
          <MapPin size={16} strokeWidth={1.9} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold truncate">{row.trdarName}</p>
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
  );
}
