"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark as BookmarkIcon, CandlestickChart, MapPin, Trash2 } from "lucide-react";
import { fetchBookmarks, removeBookmark } from "@/lib/api";
import type { Bookmark } from "@/lib/types";
import { useUIStore } from "@/lib/uiStore";
import { Button } from "@/components/ui/button";

const SECTION_META: Record<
  Bookmark["target_type"],
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

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" });
}

/** 북마크 — 찜해둔 종목·상권으로 바로 돌아가는 재개 지점. 등록은 각 화면의 북마크 버튼이 한다. */
export default function BookmarksPage() {
  const user = useUIStore((s) => s.user);
  const openAuth = useUIStore((s) => s.openAuth);
  const queryClient = useQueryClient();
  const { data, isPending, isError } = useQuery({
    queryKey: ["bookmarks"],
    queryFn: fetchBookmarks,
    enabled: !!user,
  });
  const remove = useMutation({
    mutationFn: ({ target_type, target_key }: Pick<Bookmark, "target_type" | "target_key">) =>
      removeBookmark(target_type, target_key),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["bookmarks"] }),
  });

  const items = data?.items ?? [];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight">북마크</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            주식·상권 화면의 <BookmarkIcon size={13} className="inline -mt-0.5" /> 버튼으로 찜한
            종목과 상권입니다.
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
              <div key={i} className="skeleton h-14 rounded-xl" />
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
