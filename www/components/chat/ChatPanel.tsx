"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowUpRight, TrendingDown, TrendingUp, Minus, Sparkles } from "lucide-react";
import { useChatStore } from "@/lib/store";
import type { Area, NewsCardItem, StockAnalysis } from "@/lib/types";
import { formatPrice } from "@/lib/currency";
import ChatInput from "@/components/seoul/ChatInput";
import SymbolMark from "@/components/common/SymbolMark";

// 방향 색은 DESIGN.md §2 Direction roles 토큰을 쓴다 — Tailwind 기본 팔레트를 직접 쓰지 않는다
const DIRECTION_META = {
  UP: { label: "상승 신호", icon: TrendingUp, className: "text-up bg-up-weak border-up/20" },
  DOWN: { label: "하락 신호", icon: TrendingDown, className: "text-down bg-down-weak border-down/20" },
  NEUTRAL: { label: "중립", icon: Minus, className: "text-foreground-muted bg-surface border-border" },
} as const;

function PinMark({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={Math.round((size * 20) / 16)} viewBox="0 0 16 20" aria-hidden>
      <path d="M8 0C3.6 0 0 3.6 0 8c0 6 8 12 8 12s8-6 8-12c0-4.4-3.6-8-8-8z" fill="#991B1B" />
      <circle cx="8" cy="8" r="2.5" fill="#FFFFFF" />
    </svg>
  );
}

type ChatPanelProps = {
  workspace: "stock" | "market";
  placeholder: string;
  emptyPrompts: string[]; // 빈 대화 상태에서 보여줄 예시 질문
  onSelectStock?: (stock: StockAnalysis) => void; // stock 워크스페이스: 카드 클릭 → ?symbol 갱신
  onSelectArea?: (area: Area) => void; // market 워크스페이스: 카드 클릭 → 핀 포커스
};

// 워크스페이스 공용 채팅 패널 — 메시지 리스트 + 입력창.
// 현재 워크스페이스와 같은 도메인 카드는 스테이지 조작(onSelect*),
// 다른 도메인 카드는 해당 워크스페이스로 가는 링크 칩만 렌더한다(자동 이동 금지).
export default function ChatPanel({
  workspace,
  placeholder,
  emptyPrompts,
  onSelectStock,
  onSelectArea,
}: ChatPanelProps) {
  const messages = useChatStore((s) => s.messages);
  const isLoading = useChatStore((s) => s.isLoading);
  const loadingStage = useChatStore((s) => s.loadingStage);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const conversationId = useChatStore((s) => s.conversationId);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const cParam = conversationId ? `&c=${conversationId}` : "";

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 flex flex-col gap-5" aria-live="polite">
        {messages.length === 0 && !isLoading && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-2">
            <PinMark size={18} />
            <p className="text-sm text-foreground-muted">
              {workspace === "stock"
                ? "종목에 대해 무엇이든 물어보세요"
                : "동네·업종·예산으로 물어보세요"}
            </p>
            <div className="flex flex-col gap-2 w-full">
              {emptyPrompts.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => void sendMessage(p)}
                  className="w-full text-left text-sm px-3.5 py-2.5 rounded-xl border border-border bg-surface hover:border-brand/40 transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => {
          if (m.role === "user") {
            return (
              <div key={m.id} className="flex justify-end animate-fade-in-up">
                <div className="max-w-[85%] bg-accent rounded-2xl px-3.5 py-2.5 text-sm text-foreground whitespace-pre-wrap">
                  {m.content}
                </div>
              </div>
            );
          }
          // AI 답변은 카드로 세운다 — 이 제품이 시세 화면과 다른 지점이 여기인데,
          // 회색 본문 한 덩어리로 두면 사용자가 흘려 읽는다(레퍼런스 토스 "왜 떨어졌을까?" 카드).
          return (
            <div
              key={m.id}
              className="animate-fade-in-up rounded-xl border border-border bg-surface p-3.5"
            >
              <div className="flex items-center gap-1.5 mb-2">
                <Sparkles size={13} strokeWidth={2} className="text-brand" />
                <span className="text-xs font-medium text-foreground-muted">AI 분석</span>
              </div>
              <div className="min-w-0">
                <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                  {withCitations(m.content)}
                </p>

                {m.stock && (
                  workspace === "stock" ? (
                    <StockSummaryCard stock={m.stock} onClick={() => onSelectStock?.(m.stock!)} />
                  ) : (
                    <Link
                      href={`/stock?symbol=${encodeURIComponent(m.stock.symbol)}${cParam}`}
                      className="mt-3 inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-brand text-white text-xs font-medium hover:bg-brand-deep transition-colors"
                    >
                      {m.stock.symbol} 주식 워크스페이스에서 열기
                      <ArrowUpRight size={13} strokeWidth={2.25} />
                    </Link>
                  )
                )}

                {m.news && m.news.length > 0 && <NewsEvidenceList items={m.news} />}

                {m.recommendations && m.recommendations.length > 0 && (
                  workspace === "market" ? (
                    <div className="mt-3 flex flex-col gap-2">
                      {/* 번호 뱃지는 지도 핀·칩과 같은 순번 — 카드→핀→상세가 한 흐름으로 읽힌다.
                          1번(첫 추천)만 브랜드 면 + 테두리로 세운다. */}
                      {m.recommendations.map((r, i) => (
                        <button
                          key={r.id}
                          type="button"
                          onClick={() => onSelectArea?.(r)}
                          className={`w-full text-left bg-background border rounded-xl p-3 transition-colors ${
                            i === 0
                              ? "border-brand/40 hover:border-brand/60"
                              : "border-border hover:border-brand/40"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <span
                              aria-hidden
                              className={`grid place-items-center w-[18px] h-[18px] shrink-0 rounded-full text-xs font-bold tabular-nums ${
                                i === 0 ? "bg-brand text-white" : "bg-accent text-brand"
                              }`}
                            >
                              {i + 1}
                            </span>
                            <span className="text-sm font-semibold flex-1 min-w-0 truncate">{r.name}</span>
                            <span className="text-xs text-foreground-muted shrink-0">{r.category}</span>
                          </div>
                          <p className="text-xs mt-1.5 text-foreground/80 leading-snug">{r.reason}</p>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <Link
                      href={`/market?trdar=${m.recommendations[0].id}${cParam}`}
                      className="mt-3 inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-brand text-white text-xs font-medium hover:bg-brand-deep transition-colors"
                    >
                      추천 상권 {m.recommendations.length}곳 지도에서 열기
                      <ArrowUpRight size={13} strokeWidth={2.25} />
                    </Link>
                  )
                )}
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div
            className="animate-fade-in-up rounded-xl border border-border bg-surface p-3.5"
            role="status"
            aria-label="응답 생성 중"
          >
            <div className="flex items-center gap-1.5 mb-2">
              <Sparkles size={13} strokeWidth={2} className="text-brand" />
              {/* 진행 단계(SSE) — phase 왕복 동안 지금 뭘 하는지 보여준다. 없으면 기본 문구 */}
              <span className="text-xs font-medium text-foreground-muted">
                {loadingStage ?? "분석 중…"}
              </span>
            </div>
            <div className="flex flex-col gap-2">
              <div className="skeleton h-3.5 rounded-md w-[85%]" />
              <div className="skeleton h-3.5 rounded-md w-[65%]" />
              <div className="skeleton h-3.5 rounded-md w-[45%]" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="shrink-0 px-3 pb-3 pt-1">
        <ChatInput
          onSubmit={(text) => void sendMessage(text)}
          disabled={isLoading}
          placeholder={placeholder}
        />
      </div>
    </div>
  );
}

const fmtNum = (v: number, digits = 2) =>
  v.toLocaleString("ko-KR", { maximumFractionDigits: digits });

// 확신도 %를 그대로 띄우면(예: "중립 9%") 초보자가 상승 확률로 오독한다 — 페이지 StockHero와
// 같은 결로 신호 세기(약/보통/강)로 바꾼다. 기준은 방향 임계값(±0.3)의 1·2배.
function signalStrength(confidence: number): string {
  if (confidence < 0.3) return "약";
  if (confidence < 0.6) return "보통";
  return "강";
}

function StockSummaryCard({ stock, onClick }: { stock: StockAnalysis; onClick: () => void }) {
  const meta = DIRECTION_META[stock.direction] ?? DIRECTION_META.NEUTRAL;
  const DirectionIcon = meta.icon;
  // 신규 6필드는 optional(구버전 히스토리 payload 호환) — 있을 때만 지표 그리드 렌더
  const indicators: [string, string][] | null =
    stock.atrPct !== undefined
      ? [
          ["RSI", fmtNum(stock.rsi, 1)],
          ["밴드 위치", fmtNum(stock.bbPercentB ?? 0.5)],
          ["거래량비", `${fmtNum(stock.volumeRatio ?? 1)}x`],
          ["1년 추세", `${fmtNum((stock.momentum12To1 ?? 0) * 100, 1)}%`],
          ["ATR (변동성)", `${fmtNum(stock.atrPct * 100, 1)}%`],
          ["자금 흐름", fmtNum(stock.obvSlope ?? 0, 3)],
        ]
      : null;
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-3 w-full text-left bg-background border border-border rounded-xl p-3 hover:border-brand/40 transition-colors"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <SymbolMark name={stock.symbol} />
          <span className="text-sm font-semibold truncate">{stock.symbol}</span>
        </div>
        {/* 이 카드는 질문 시점에 얼어붙은 값이다. 스테이지 헤더는 방금 재분석한 값이라
            둘이 어긋날 수 있어(상승 36% vs 중립 16% 실사례) 시점을 명시한다. */}
        <div className="shrink-0 text-right">
          <div className="text-base font-bold tabular-nums">
            {formatPrice(stock.price, stock.symbol)}
          </div>
          <span className={`mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium ${meta.className}`}>
            <DirectionIcon size={12} strokeWidth={2} />
            {meta.label} · 신호 {stock.strength || signalStrength(stock.confidence)}
          </span>
          <div className="mt-1 text-xs text-foreground-muted">질문 시점 기준</div>
        </div>
      </div>
      {/* 결론 한 줄 — 서버가 페이지와 같은 verdict로 계산(구버전 payload엔 없어 생략) */}
      {stock.headline && (
        <p className="mt-2 text-sm font-semibold leading-snug">{stock.headline}</p>
      )}
      {stock.watch && (
        <p className="mt-1 text-xs text-foreground-muted leading-snug">지켜볼 점 {stock.watch}</p>
      )}
      {stock.value && stock.value.length > 0 && (
        <p className="mt-1 text-xs text-foreground-muted leading-snug">
          가치·체력 {stock.value.join(" · ")}
        </p>
      )}
      {indicators && (
        <div className="mt-2.5 grid grid-cols-3 gap-1.5">
          {indicators.map(([label, value]) => (
            <div key={label} className="rounded-lg bg-surface border border-border px-2 py-1.5">
              <div className="text-xs text-foreground-muted">{label}</div>
              <div className="text-xs font-semibold mt-0.5">{value}</div>
            </div>
          ))}
        </div>
      )}
      <div className="mt-2 flex items-center gap-1.5 flex-wrap">
        {stock.referenceUpSignal && (
          <span className="inline-flex px-2 py-0.5 rounded-full bg-up-weak border border-up/20 text-up text-xs font-medium">
            백테스트 검증 참고 신호
          </span>
        )}
        {stock.sentimentLabel && (
          <span className="text-xs text-foreground-muted">뉴스 감성 {stock.sentimentLabel}</span>
        )}
        {/* 영향 키워드(B2) — 최근 헤드라인 빈도의 관측 요약(예측 아님, 구버전 payload엔 없음) */}
        {stock.keywords && stock.keywords.length > 0 &&
          stock.keywords.map((k) => (
            <span
              key={k}
              className="inline-flex px-2 py-0.5 rounded-full bg-accent text-brand text-xs font-medium"
            >
              #{k}
            </span>
          ))}
      </div>
      <p className="mt-2 text-xs text-foreground-muted">차트에 반영하려면 클릭</p>
    </button>
  );
}

// 답변 본문의 인용 마커 [n]을 근거 배지로 렌더 — 번호는 아래 근거 뉴스 목록의 [n]과 대응한다
// (백엔드가 컨텍스트에 '근거 [n]'으로 번호를 부여하고 모델이 문장 끝에 인용한다 — R4).
function withCitations(text: string): React.ReactNode {
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const marker = /^\[(\d+)\]$/.exec(part);
    if (!marker) return part;
    return (
      <sup
        key={i}
        title={`근거 ${marker[1]}번`}
        className="ml-0.5 text-[10px] font-semibold text-brand tabular-nums"
      >
        [{marker[1]}]
      </sup>
    );
  });
}

function NewsEvidenceList({ items }: { items: NewsCardItem[] }) {
  return (
    <div className="mt-3 flex flex-col gap-1.5">
      <p className="text-xs font-medium text-foreground-muted">
        근거 뉴스 {items.length}건 — 본문의 [n]이 아래 번호입니다
      </p>
      {items.map((n, i) => (
        <div key={i} className="bg-background border border-border rounded-xl px-3 py-2">
          <p className="text-xs font-medium leading-snug">
            <span className="mr-1 font-semibold text-brand tabular-nums">[{i + 1}]</span>
            {n.title}
          </p>
          <p className="text-xs text-foreground-muted mt-0.5">
            {n.publishedAt ?? "날짜 미상"} · {n.ticker ?? "종목 무관"} · {sentimentText(n)}
          </p>
        </div>
      ))}
    </div>
  );
}

function sentimentText(n: NewsCardItem): string {
  if (n.sentiment === null) return n.eventType ?? "라벨 없음";
  const direction = n.sentiment > 0 ? "호재" : n.sentiment < 0 ? "악재" : "중립";
  const label = `${direction} ${n.sentiment > 0 ? "+" : ""}${n.sentiment.toFixed(1)}`;
  return n.eventType ? `${label} · ${n.eventType}` : label;
}
