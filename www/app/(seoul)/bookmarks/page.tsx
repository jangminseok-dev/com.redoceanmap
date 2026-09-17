"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bookmark as BookmarkIcon,
  CandlestickChart,
  MapPin,
  Minus,
  Trash2,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { fetchBookmarkBoard, removeBookmark } from "@/lib/api";
import { formatPrice } from "@/lib/currency";
import type { BookmarkBoardItem, BookmarkStockStatus } from "@/lib/types";
import { useUIStore } from "@/lib/uiStore";
import { Button } from "@/components/ui/button";

const SECTION_META: Record<
  BookmarkBoardItem["target_type"],
  { title: string; icon: typeof MapPin; href: (key: string) => string }
> = {
  stock: {
    title: "관심 종목",
    icon: CandlestickChart,
    href: (key) => `/stock?symbol=${encodeURIComponent(key)}`,
  },
  area: {
    title: "관심 상권",
    icon: MapPin,
    // 지도 오버레이의 열림은 URL(?trdar)이 단일 진실 — 딥링크로 바로 연다
    href: (key) => `/market?trdar=${encodeURIComponent(key)}`,
  },
};

// 방향은 신호 관측이지 매수 추천이 아니다 — 라벨·색은 주식 보드(MarketBoard)와 동일
const DIRECTION_META: Record<
  BookmarkStockStatus["direction"],
  { label: string; icon: LucideIcon; className: string }
> = {
  UP: { label: "반등 신호", icon: TrendingUp, className: "text-up bg-up-weak" },
  DOWN: { label: "조정 신호", icon: TrendingDown, className: "text-down bg-down-weak" },
  NEUTRAL: { label: "중립", icon: Minus, className: "text-foreground-muted bg-border/40" },
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" });
}

// change_pct는 비율(0.012), 상권 QoQ는 이미 % 단위(3.2) — 호출부가 구분해 넘긴다
const signedPct = (percent: number) => `${percent > 0 ? "+" : ""}${percent.toFixed(1)}%`;

const pctTone = (v: number) => (v > 0 ? "text-up" : v < 0 ? "text-down" : "text-foreground-muted");

function StockStatusLine({ status }: { status: BookmarkStockStatus }) {
  const meta = DIRECTION_META[status.direction] ?? DIRECTION_META.NEUTRAL;
  const Icon = meta.icon;
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
      <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-medium ${meta.className}`}>
        <Icon size={12} /> {meta.label}
      </span>
      {status.ready && (
        <span className="rounded-md border border-border px-1.5 py-0.5 text-foreground-muted">
          검증 참고 신호
        </span>
      )}
      <span className="tabular-nums font-medium">{formatPrice(status.price, status.ticker)}</span>
      {status.change_pct != null && (
        <span className={`tabular-nums font-medium ${pctTone(status.change_pct)}`}>
          {signedPct(status.change_pct * 100)}
        </span>
      )}
      <span className="text-foreground-muted">
        신호 {new Date(status.as_of).toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" })} 기준
      </span>
    </div>
  );
}

function AreaStatusLine({ status }: { status: NonNullable<BookmarkBoardItem["area"]> }) {
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
      <span className="rounded-md bg-border/40 px-1.5 py-0.5 font-medium">
        종합 {Math.round(status.total)}점 · {status.grade}
      </span>
      {status.sales_qoq_pct != null && (
        <span className={`tabular-nums font-medium ${pctTone(status.sales_qoq_pct)}`}>
          매출 전분기 대비 {signedPct(status.sales_qoq_pct)}
        </span>
      )}
      {status.seoul_qoq_pct != null && (
        <span className="text-foreground-muted tabular-nums">서울 {signedPct(status.seoul_qoq_pct)}</span>
      )}
    </div>
  );
}

/** 관심 보드 — 찜한 종목·상권의 "지금"(신호·점수)을 한눈에. 등록은 각 화면의 북마크 버튼이 한다. */
export default function BookmarksPage() {
  const user = useUIStore((s) => s.user);
  const openAuth = useUIStore((s) => s.openAuth);
  const queryClient = useQueryClient();
  const { data, isPending, isError } = useQuery({
    queryKey: ["bookmark-board"],
    queryFn: fetchBookmarkBoard,
    enabled: !!user,
  });
  const remove = useMutation({
    mutationFn: ({ target_type, target_key }: Pick<BookmarkBoardItem, "target_type" | "target_key">) =>
      removeBookmark(target_type, target_key),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bookmark-board"] });
      // 다른 화면의 북마크 토글 버튼이 보는 목록도 함께 갱신한다
      queryClient.invalidateQueries({ queryKey: ["bookmarks"] });
    },
  });

  const items = data?.items ?? [];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight">북마크</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            주식·상권 화면의 <BookmarkIcon size={13} className="inline -mt-0.5" /> 버튼으로 찜한
            항목의 지금 상태입니다. 신호·가격은 일일 수집 기준이라 준실시간이 아니며, 매수·매도
            추천이 아닙니다.
          </p>
        </div>

        {!user ? (
          <section className="rounded-2xl bg-surface border border-border p-8 text-center space-y-3">
            <p className="text-sm text-foreground-muted">로그인하면 북마크가 기기와 무관하게 유지됩니다.</p>
            <Button size="md" onClick={() => openAuth("login")}>로그인</Button>
          </section>
        ) : isPending ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton h-16 rounded-xl" />
            ))}
          </div>
        ) : isError ? (
          <section className="rounded-2xl bg-surface border border-border p-8 text-center text-sm text-foreground-muted">
            북마크를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
          </section>
        ) : items.length === 0 ? (
          <section className="rounded-2xl bg-surface border border-border p-8 text-center text-sm text-foreground-muted">
            아직 찜한 항목이 없습니다 — 종목·상권 화면에서 북마크 버튼을 눌러 추가하세요.
          </section>
        ) : (
          (["stock", "area"] as const).map((type) => {
            const rows = items.filter((b) => b.target_type === type);
            if (rows.length === 0) return null;
            const meta = SECTION_META[type];
            const Icon = meta.icon;
            return (
              <section key={type} className="space-y-2">
                <h2 className="text-sm font-semibold text-foreground-muted flex items-center gap-1.5">
                  <Icon size={14} /> {meta.title} ({rows.length})
                </h2>
                <ul className="space-y-2">
                  {rows.map((b) => (
                    <li
                      key={b.id}
                      className="flex items-center gap-3 rounded-xl bg-surface border border-border px-4 py-3"
                    >
                      <Link href={meta.href(b.target_key)} className="min-w-0 flex-1 group">
                        <p className="text-sm font-medium truncate group-hover:text-brand">
                          {b.label}
                        </p>
                        <p className="text-xs text-foreground-muted">
                          {b.target_key} · {formatDate(b.created_at)} 저장
                        </p>
                        {b.stock ? (
                          <StockStatusLine status={b.stock} />
                        ) : b.area ? (
                          <AreaStatusLine status={b.area} />
                        ) : (
                          <p className="mt-1 text-xs text-foreground-muted">
                            상태 준비 중 — 수집 데이터가 쌓이면 표시됩니다
                          </p>
                        )}
                      </Link>
                      <button
                        type="button"
                        aria-label={`${b.label} 북마크 삭제`}
                        disabled={remove.isPending}
                        onClick={() => remove.mutate(b)}
                        className="shrink-0 rounded-md p-1.5 text-foreground-muted hover:bg-border/50 hover:text-foreground"
                      >
                        <Trash2 size={15} />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })
        )}
      </div>
    </div>
  );
}
