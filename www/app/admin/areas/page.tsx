"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Download, Search } from "lucide-react";
import { downloadCsv, fetchAdminAreas, formatSalesMan, type AdminAreaRow } from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import Empty from "@/components/admin/Empty";
import Kpi from "@/components/admin/Kpi";
import { Button } from "@/components/ui/button";

// 폐업률이 이 값 이상이면 "주의" 배지 — 어드민 목록 표시용 임계값
const CLOSURE_WARN = 7;

type SortKey = "store_count" | "monthly_sales" | "closure_rate";

const SORT_COLUMNS: { key: SortKey; label: string }[] = [
  { key: "store_count", label: "점포수" },
  { key: "monthly_sales", label: "추정매출(월)" },
  { key: "closure_rate", label: "폐업률" },
];

export default function AreasPage() {
  // REACT_RULES 패턴 B: 실시간 필터·정렬 상태는 단일 객체 useState
  const [filter, setFilter] = useState<{
    q: string;
    gu: string;
    sort: { key: SortKey; dir: "asc" | "desc" } | null;
  }>({ q: "", gu: "전체", sort: null });
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-areas"],
    queryFn: fetchAdminAreas,
  });

  const areas = data?.areas ?? [];

  const guList = useMemo(
    () => ["전체", ...Array.from(new Set(areas.map((a) => a.gu_name).filter(Boolean))).sort()],
    [areas],
  );

  const rows = useMemo(() => {
    const filtered = areas.filter(
      (a) =>
        (filter.gu === "전체" || a.gu_name === filter.gu) &&
        (!filter.q || a.trdar_name.includes(filter.q) || a.dong_name.includes(filter.q)),
    );
    if (!filter.sort) return filtered;
    const { key, dir } = filter.sort;
    return [...filtered].sort((a, b) => {
      const av = a[key];
      const bv = b[key];
      if (av == null && bv == null) return 0;
      if (av == null) return 1; // null은 항상 뒤로
      if (bv == null) return -1;
      return dir === "asc" ? av - bv : bv - av;
    });
  }, [areas, filter]);

  const warnCount = rows.filter(
    (a) => a.closure_rate != null && a.closure_rate >= CLOSURE_WARN,
  ).length;

  const toggleSort = (key: SortKey) =>
    setFilter((prev) => ({
      ...prev,
      sort:
        prev.sort?.key !== key
          ? { key, dir: "desc" }
          : prev.sort.dir === "desc"
            ? { key, dir: "asc" }
            : null,
    }));

  const exportCsv = () =>
    downloadCsv(
      "admin-areas.csv",
      ["상권코드", "상권", "자치구", "행정동", "점포수", "추정매출(월,원)", "폐업률(%)"],
      rows.map((a) => [
        a.trdar_code,
        a.trdar_name,
        a.gu_name,
        a.dong_name,
        a.store_count ?? "",
        a.monthly_sales ?? "",
        a.closure_rate != null ? a.closure_rate.toFixed(1) : "",
      ]),
    );

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">상권 관리</h1>
          <p className="mt-1 text-sm text-foreground-muted">서울시 등록 상권 데이터 (최신 분기 집계)</p>
        </div>
        <Button
          type="button"
          onClick={exportCsv}
          disabled={rows.length === 0}
          variant="outline"
        >
          <Download size={15} /> CSV 내보내기
        </Button>
      </div>

      {/* 요약 */}
      <div className="grid grid-cols-3 gap-3 sm:gap-4">
        <Kpi label="전체 상권" value={areas.length.toLocaleString()} />
        <Kpi label="조회 결과" value={rows.length.toLocaleString()} />
        <Kpi label={`주의 (폐업률 ${CLOSURE_WARN}%↑)`} value={warnCount.toLocaleString()} />
      </div>

      {/* 검색 + 자치구 필터 */}
      <label className="flex items-center gap-2 px-3.5 h-10 rounded-full bg-surface border border-border text-sm">
        <Search size={16} className="text-foreground-muted shrink-0" />
        <input
          value={filter.q}
          onChange={(e) => setFilter((prev) => ({ ...prev, q: e.target.value }))}
          placeholder="상권명·행정동 검색"
          className="bg-transparent outline-none flex-1 placeholder:text-foreground-muted"
        />
      </label>
      <div className="flex gap-2 overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0 pb-1">
        {guList.map((gu) => (
          <button
            key={gu}
            type="button"
            onClick={() => setFilter((prev) => ({ ...prev, gu }))}
            className={`shrink-0 px-3.5 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter.gu === gu
                ? "bg-brand text-white"
                : "bg-surface border border-border text-foreground/70 hover:text-foreground"
            }`}
          >
            {gu}
          </button>
        ))}
      </div>

      {/* 목록 */}
      <section className="rounded-2xl bg-surface border border-border overflow-hidden">
        {isPending && <BlockSkeleton rows={6} />}
        {isError && <Empty msg="상권 데이터를 불러오지 못했습니다." />}
        {!isPending && !isError && rows.length === 0 && <Empty msg="조건에 맞는 상권이 없습니다." />}
        {rows.length > 0 && (
          <>
            <div className="hidden sm:block max-h-[32rem] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface">
                  <tr className="text-left text-xs text-foreground-muted border-b border-border bg-background/60">
                    <th className="font-medium px-5 py-2.5">상권</th>
                    <th className="font-medium px-5 py-2.5">자치구</th>
                    <th className="font-medium px-5 py-2.5">행정동</th>
                    {SORT_COLUMNS.map((c) => (
                      <th key={c.key} className="font-medium px-5 py-2.5 text-right">
                        <button
                          type="button"
                          onClick={() => toggleSort(c.key)}
                          className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
                        >
                          {c.label}
                          {filter.sort?.key === c.key &&
                            (filter.sort.dir === "desc" ? (
                              <ArrowDown size={12} />
                            ) : (
                              <ArrowUp size={12} />
                            ))}
                        </button>
                      </th>
                    ))}
                    <th className="font-medium px-5 py-2.5 text-right">상태</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a) => (
                    <tr key={a.trdar_code} className="border-b border-border last:border-0 hover:bg-background/40">
                      <td className="px-5 py-3 font-medium">
                        <Link
                          href={`/market?trdar=${a.trdar_code}`}
                          className="hover:text-brand hover:underline transition-colors"
                          title="서비스 지도에서 열기"
                        >
                          {a.trdar_name}
                        </Link>
                      </td>
                      <td className="px-5 py-3 text-foreground-muted">{a.gu_name || "—"}</td>
                      <td className="px-5 py-3 text-foreground-muted">{a.dong_name || "—"}</td>
                      <td className="px-5 py-3 text-right tabular-nums">
                        {a.store_count?.toLocaleString() ?? "—"}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums">{formatSalesMan(a.monthly_sales)}</td>
                      <td className="px-5 py-3 text-right tabular-nums">
                        {a.closure_rate != null ? `${a.closure_rate.toFixed(1)}%` : "—"}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Badge row={a} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="sm:hidden divide-y divide-border max-h-[32rem] overflow-y-auto">
              {rows.map((a) => (
                <Link
                  key={a.trdar_code}
                  href={`/market?trdar=${a.trdar_code}`}
                  className="px-4 py-3 flex items-center justify-between gap-3 hover:bg-background/40 transition-colors"
                >
                  <div className="min-w-0">
                    <p className="font-medium">{a.trdar_name}</p>
                    <p className="text-xs text-foreground-muted mt-0.5">
                      {a.gu_name || "—"} · 점포 {a.store_count?.toLocaleString() ?? "—"} · 매출{" "}
                      {formatSalesMan(a.monthly_sales)} · 폐업{" "}
                      {a.closure_rate != null ? `${a.closure_rate.toFixed(1)}%` : "—"}
                    </p>
                  </div>
                  <Badge row={a} />
                </Link>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function Badge({ row }: { row: AdminAreaRow }) {
  if (row.closure_rate == null) {
    return (
      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-foreground/5 text-foreground-muted">
        데이터 없음
      </span>
    );
  }
  const warn = row.closure_rate >= CLOSURE_WARN;
  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
        warn ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"
      }`}
    >
      {warn ? "주의" : "활성"}
    </span>
  );
}
