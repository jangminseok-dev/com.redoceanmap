"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { MessageSquare, ChevronRight } from "lucide-react";
import { fetchConversations } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import { useUIStore } from "@/lib/uiStore";
import { Button } from "@/components/ui/button";
import type { ConversationSummary } from "@/lib/types";

const DAY_MS = 86_400_000;

// 시간 그룹 — 최근일수록 크게, 오래될수록 조여서(밀도 체감) "재개 지점"이 먼저 보이게 한다
function groupOf(iso: string): "오늘" | "이번 주" | "이전" {
  const t = Date.parse(iso);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (t >= startOfToday) return "오늘";
  if (t >= startOfToday - 6 * DAY_MS) return "이번 주";
  return "이전";
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ko-KR", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// 도메인 필터 — 백엔드가 마지막 카드 요약(domain·label)을 실어준다(2026-08-17)
const FILTERS = [
  { key: "ALL", label: "전체" },
  { key: "market", label: "상권" },
  { key: "stock", label: "주식" },
] as const;
type FilterKey = (typeof FILTERS)[number]["key"];

const DOMAIN_BADGE: Record<"stock" | "market", { label: string; className: string }> = {
  stock: { label: "주식", className: "bg-up-weak text-up" },
  market: { label: "상권", className: "bg-accent text-brand" },
};

/**
 * 지난 대화 — "기록 목록"이 아니라 **작업 재개 지점**이다(핸드오프 §지난 대화).
 * 항목을 고르면 그때의 카드(추천 상권/종목)가 복원된 워크스페이스로 돌아간다.
 * 오늘 항목은 좌측 브랜드 엣지 + "이어서 보기"로 크게, 이전 항목은 1줄로 조인다.
 */
export default function HistoryPage() {
  const router = useRouter();
  const user = useUIStore((s) => s.user);
  const openAuth = useUIStore((s) => s.openAuth);
  const loadConversation = useChatStore((s) => s.loadConversation);
  // 단일 객체 패턴(REACT_RULES) — 여는 중 표시와 도메인 필터를 한 상태로 든다
  const [ui, setUi] = useState<{ openingId: number | null; filter: FilterKey }>({
    openingId: null,
    filter: "ALL",
  });
  const { openingId, filter } = ui;
  const setOpeningId = (openingId: number | null) => setUi((prev) => ({ ...prev, openingId }));

  const { data, isLoading, isError } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => fetchConversations(),
    enabled: !!user,
  });

  const open = async (id: number) => {
    if (openingId !== null) return;
    setOpeningId(id);
    try {
      const raw = await loadConversation(id);
      // 마지막 구조화 카드 기준으로 이동할 워크스페이스 결정
      const lastPayload = [...raw].reverse().find((m) => m.payload)?.payload;
      if (lastPayload?.stock) {
        router.push(`/stock?symbol=${encodeURIComponent(lastPayload.stock.symbol)}&c=${id}`);
      } else if (lastPayload?.recommendations?.length) {
        router.push(`/market?trdar=${lastPayload.recommendations[0].id}&c=${id}`);
      } else {
        router.push(`/stock?c=${id}`);
      }
    } catch {
      setOpeningId(null);
    }
  };

  if (!user) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-6">
        <MessageSquare size={36} className="text-foreground-muted" strokeWidth={1.5} />
        <p className="text-sm text-foreground-muted">지난 대화를 보려면 로그인이 필요해요.</p>
        <Button type="button" onClick={() => openAuth("login")}>
          로그인
        </Button>
      </div>
    );
  }

  const filtered = (data ?? []).filter((c) => filter === "ALL" || c.domain === filter);
  const counts = (data ?? []).reduce(
    (acc, c) => {
      if (c.domain === "stock" || c.domain === "market") acc[c.domain] += 1;
      return acc;
    },
    { stock: 0, market: 0 },
  );
  const groups = filtered.reduce<Record<string, ConversationSummary[]>>((acc, c) => {
    (acc[groupOf(c.createdAt)] ??= []).push(c);
    return acc;
  }, {});

  return (
    <div className="flex-1 px-6 py-8">
      <div className="w-full max-w-2xl mx-auto">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <MessageSquare size={18} className="text-brand" strokeWidth={2} />
          지난 대화
        </h1>
        <p className="mt-1 mb-3 text-xs text-foreground-muted">
          항목을 누르면 그때의 카드가 복원된 워크스페이스로 돌아가요
        </p>

        {/* 도메인 필터 — 알약 칩(낮은 위계, Button 스케일과 섞지 않는다) */}
        {data && data.length > 0 && (
          <div className="mb-4 flex items-center gap-1.5">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setUi((prev) => ({ ...prev, filter: f.key }))}
                aria-pressed={filter === f.key}
                className={`inline-flex items-center gap-1 h-7 px-2.5 rounded-full text-xs font-medium transition-colors duration-150 ${
                  filter === f.key
                    ? "bg-brand text-white"
                    : "border border-border text-foreground-muted hover:bg-accent hover:text-foreground"
                }`}
              >
                {f.label}
                <span className="tabular-nums opacity-70">
                  {f.key === "ALL" ? data.length : counts[f.key]}
                </span>
              </button>
            ))}
          </div>
        )}

        {data && data.length > 0 && filtered.length === 0 && (
          <p className="text-sm text-foreground-muted">
            {filter === "stock" ? "주식" : "상권"} 대화가 아직 없어요. 전체를 눌러 다른 대화를
            보거나 홈에서 물어보세요.
          </p>
        )}

        {isLoading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="skeleton h-16 rounded-xl" />
            ))}
          </div>
        )}
        {isError && (
          <p className="text-sm text-foreground-muted">
            대화 목록을 불러오지 못했습니다. 잠시 후 새로고침해 주세요.
          </p>
        )}
        {data && data.length === 0 && (
          <p className="text-sm text-foreground-muted">
            아직 대화가 없어요. 홈에서 질문을 시작해보세요.
          </p>
        )}

        {(["오늘", "이번 주", "이전"] as const).map(
          (g) =>
            groups[g]?.length > 0 && (
              <section key={g} className="mb-6">
                <h2 className="mb-2 text-xs font-semibold text-foreground-muted">{g}</h2>
                <ul className="flex flex-col gap-2">
                  {groups[g].map((c) =>
                    g === "오늘" ? (
                      // 오늘 — 재개 확률이 가장 높은 항목. 좌측 브랜드 엣지 + 행선 문구로 세운다.
                      <li key={c.id}>
                        <button
                          type="button"
                          onClick={() => void open(c.id)}
                          disabled={openingId !== null}
                          className="w-full text-left bg-surface border border-border rounded-xl px-4 py-3.5 shadow-[inset_3px_0_0_var(--brand)] hover:border-brand/40 transition-colors disabled:opacity-60"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            {c.domain && (
                              <span
                                className={`shrink-0 inline-flex px-1.5 py-0.5 rounded-full text-xs font-medium ${DOMAIN_BADGE[c.domain].className}`}
                              >
                                {DOMAIN_BADGE[c.domain].label}
                              </span>
                            )}
                            <p className="text-sm font-semibold truncate">{c.title}</p>
                          </div>
                          <div className="mt-1.5 flex items-center justify-between gap-2">
                            <span className="text-xs text-foreground-muted truncate">
                              {formatDate(c.createdAt)}
                              {c.label && ` · ${c.label}`}
                            </span>
                            <span className="text-[13px] font-medium text-brand shrink-0">
                              {openingId === c.id ? "여는 중…" : "이어서 보기 →"}
                            </span>
                          </div>
                        </button>
                      </li>
                    ) : (
                      // 이전 — 1줄 행으로 조인다. 위계는 크기와 밀도가 만든다.
                      <li key={c.id}>
                        <button
                          type="button"
                          onClick={() => void open(c.id)}
                          disabled={openingId !== null}
                          className="w-full flex items-center gap-3 text-left bg-surface border border-border rounded-xl px-4 py-2.5 hover:border-brand/40 transition-colors disabled:opacity-60"
                        >
                          {c.domain && (
                            <span
                              className={`shrink-0 inline-flex px-1.5 py-0.5 rounded-full text-xs font-medium ${DOMAIN_BADGE[c.domain].className}`}
                            >
                              {DOMAIN_BADGE[c.domain].label}
                            </span>
                          )}
                          <span className="flex-1 min-w-0 text-sm truncate">{c.title}</span>
                          {c.label && (
                            <span className="shrink-0 max-w-[96px] sm:max-w-[160px] text-xs text-foreground-muted truncate">
                              {c.label}
                            </span>
                          )}
                          <span className="shrink-0 text-xs text-foreground-muted tabular-nums">
                            {formatDate(c.createdAt)}
                          </span>
                          {openingId === c.id ? (
                            <span className="text-xs text-foreground-muted animate-pulse shrink-0">
                              여는 중…
                            </span>
                          ) : (
                            <ChevronRight size={16} className="text-foreground-muted shrink-0" />
                          )}
                        </button>
                      </li>
                    ),
                  )}
                </ul>
              </section>
            ),
        )}
      </div>
    </div>
  );
}
