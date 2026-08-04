"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ApiError,
  fetchFundamentals,
  fetchPriceHistory,
  fetchStockAnalysis,
  fetchStockForecast,
  fetchStockNews,
  fetchStockQuote,
} from "@/lib/api";
import { useChatStore } from "@/lib/store";
import { useDensityStore } from "@/lib/uiStore";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";
import ChatPanel from "@/components/chat/ChatPanel";
import SymbolHeader from "@/components/stock/SymbolHeader";
import StockPanel from "@/components/stock/StockPanel";
import StageSummary from "@/components/stock/StageSummary";
import StockVerdictHero from "@/components/stock/StockVerdictHero";
import SymbolSummary from "@/components/stock/SymbolSummary";
import MarketBoard from "@/components/stock/MarketBoard";

// lightweight-charts는 SSR 불가 — 클라이언트에서만 로드
const CandleChart = dynamic(() => import("@/components/stock/CandleChart"), {
  ssr: false,
  loading: () => <div className="flex-1 m-4 skeleton rounded-xl" />,
});

type Timeframe = "1d" | "5m";

const EMPTY_PROMPTS = [
  "삼성전자 주가 어때요?",
  "엔비디아 지금 상황 어때요?",
  "요즘 시장 분위기 어때요?",
];

// 표시 구간 프리셋 — 전체 구간(2y)으로 열면 5거래일 예측 밴드가 오른쪽 끝 실오라기가 된다.
// 5분봉은 60일치만 보유하므로 프리셋도 그 안에서만 의미가 있다.
const RANGE_PRESETS: Record<Timeframe, { label: string; days: number | null }[]> = {
  "1d": [
    { label: "1개월", days: 30 },
    { label: "3개월", days: 90 },
    { label: "6개월", days: 180 },
    { label: "1년", days: 365 },
    { label: "전체", days: null },
  ],
  "5m": [
    { label: "1주", days: 7 },
    { label: "1개월", days: 30 },
    { label: "전체", days: null },
  ],
};
const DEFAULT_RANGE: Record<Timeframe, number | null> = { "1d": 180, "5m": 7 };

function StockWorkspace() {
  const params = useSearchParams();
  const symbol = params?.get("symbol") ?? "";
  const c = params?.get("c") ?? null;
  // 단일 객체 패턴 — 타임프레임과 표시 구간은 항상 함께 바뀐다(REACT_RULES 패턴 B)
  const [view, setView] = useState<{
    timeframe: Timeframe;
    rangeDays: number | null;
    pattern: string | null;
  }>({
    timeframe: "1d",
    rangeDays: DEFAULT_RANGE["1d"],
    pattern: null,
  });
  const { timeframe, rangeDays } = view;

  const expert = useDensityStore((s) => s.expert);
  const toggleExpert = useDensityStore((s) => s.toggleExpert);

  const conversationId = useChatStore((s) => s.conversationId);
  const messages = useChatStore((s) => s.messages);
  const loadConversation = useChatStore((s) => s.loadConversation);

  // 같은 라우트에서 쿼리만 바꾸는 이동 — 초기 URL에 쿼리가 있으면 router.replace/push가
  // 프로덕션 빌드에서 무시된다(Next 16.2.6). 공식 shallow 라우팅인 history.replaceState는
  // useSearchParams와 동기화되므로 이쪽을 쓴다.
  const setSymbol = (next: string) => {
    const cid = conversationId ?? c;
    window.history.replaceState(
      null,
      "",
      `/stock?symbol=${encodeURIComponent(next)}${cid ? `&c=${cid}` : ""}`,
    );
  };

  // 채팅 응답에 종목 카드가 오면 URL(?symbol)에 반영 — 마운트 시 기존 메시지는 건너뛴다
  const handledRef = useRef<string | null>(messages[messages.length - 1]?.id ?? null);

  // 새로고침 복원 — URL의 c를 실제 대화로 되살린다. 복원하지 않으면 채팅이 빈 채로 남아
  // 다음 질문이 새 대화가 되고 멀티턴 맥락이 끊긴다. 복원된 메시지는 이미 URL에 반영된
  // 상태이므로 handledRef를 최신 메시지로 맞춰 위 이펙트가 재이동하지 않게 한다.
  const restoredRef = useRef(false);
  useEffect(() => {
    if (restoredRef.current || !c || conversationId !== null) return;
    restoredRef.current = true;
    void loadConversation(Number(c))
      .then(() => {
        const restored = useChatStore.getState().messages;
        handledRef.current = restored[restored.length - 1]?.id ?? null;
      })
      .catch(() => {}); // 남의 대화·미로그인은 404/401 — 빈 채팅으로 열화
  }, [c, conversationId, loadConversation]);

  useEffect(() => {
    const last = messages[messages.length - 1];
    if (!last || last.role !== "assistant" || handledRef.current === last.id) return;
    handledRef.current = last.id;
    if (last.stock && last.stock.symbol !== symbol) setSymbol(last.stock.symbol);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  const analyzeQ = useQuery({
    queryKey: ["stock-analyze", symbol],
    queryFn: () => fetchStockAnalysis(symbol),
    enabled: !!symbol,
    staleTime: 5 * 60_000, // 분석은 yfinance+LLM 경유라 느림 — 심볼 전환 재방문 캐시 히트
  });
  const pricesQ = useQuery({
    queryKey: ["prices", symbol, timeframe],
    queryFn: () => fetchPriceHistory(symbol, timeframe),
    enabled: !!symbol,
    retry: false,
    // 탭 포커스마다 재조회 방지 — 라이브 폴백 종목은 요청마다 yfinance 2y 다운로드라 낭비가 큼.
    // 봉은 일 단위 갱신이고 실시간성은 quote 폴링이 담당한다.
    staleTime: 5 * 60_000,
  });
  // 확률·예측 밴드 — 저장 일봉 기반이라 미수집 종목은 404(카드·밴드 미표시로 열화)
  const forecastQ = useQuery({
    queryKey: ["forecast", symbol],
    queryFn: () => fetchStockForecast(symbol),
    enabled: !!symbol,
    retry: false,
    staleTime: 10 * 60_000, // 백엔드가 일 단위 캐시 — 재조회 부담 최소화
  });
  // 준실시간 현재가(지연 시세) — 탭 활성 시에만 30초 폴링.
  // 에러(미지원 심볼·일시 네트워크 오류)는 5분 간격 저속 재시도 — 영구 중단하면
  // 일시 오류 한 번에 그 심볼의 시세 갱신이 리마운트까지 멈춘다.
  const quoteQ = useQuery({
    queryKey: ["quote", symbol],
    queryFn: () => fetchStockQuote(symbol),
    enabled: !!symbol,
    retry: false,
    refetchInterval: (query) => (query.state.status === "error" ? 300_000 : 30_000),
  });
  // 차트 감성 마커용 — NewsPanel과 같은 쿼리 키라 캐시를 공유한다(추가 요청 없음)
  const newsQ = useQuery({
    queryKey: ["stock-news", symbol],
    queryFn: () => fetchStockNews(symbol),
    enabled: !!symbol,
    staleTime: 5 * 60_000,
  });
  // 가치·체력 한 줄용 — FundamentalsPanel과 같은 쿼리 키라 캐시 공유(추가 요청 없음).
  // 미수집 종목은 빈 배열/404 → 히어로가 가치 줄을 생략(열화).
  const fundamentalsQ = useQuery({
    queryKey: ["fundamentals", symbol],
    queryFn: () => fetchFundamentals(symbol),
    enabled: !!symbol,
    retry: false,
    staleTime: 30 * 60_000,
  });

  const pricesNotCollected = pricesQ.error instanceof ApiError && pricesQ.error.status === 404;

  // 차트 형태 — 기본은 꺼둔다. 이미 이평선·밴드·감성 마커가 올라가 있어 보조선을
  // 하나 더 얹으려면 사용자가 고르게 하는 편이 낫다.
  const patterns = pricesQ.data?.patterns ?? [];
  const activePattern = view.pattern
    ? (patterns.find((p) => p.name === view.pattern) ?? null)
    : null;

  // 전일 대비 등락 — 백엔드 quote가 단일 소스다. 봉 계산은 quote가 전일 종가를 못 줄 때의
  // 폴백. 기준 봉은 "표시 중인 가격이 어느 세션인가"로 가른다: 현재가가 마지막 봉과 같으면
  // (장 마감) 그 직전 봉이, 다르면(장중 틱) 마지막 봉이 전일 종가다.
  // 마지막 봉을 무조건 기준으로 삼으면 장 마감 중 등락률이 항상 0.00%가 된다.
  const bars = pricesQ.data?.bars;
  const dailyBars = timeframe === "1d" ? bars : undefined;
  const lastClose = dailyBars?.[dailyBars.length - 1]?.close;
  const price = quoteQ.data?.price ?? lastClose;
  const sameSession =
    price !== undefined && lastClose !== undefined && Math.abs(price - lastClose) <= Math.abs(lastClose) * 1e-6;
  const previousClose =
    quoteQ.data?.previous_close ??
    (sameSession ? dailyBars?.[dailyBars.length - 2]?.close : lastClose);

  // 이 종목을 설명한 마지막 챗 답변 — 채팅을 스크롤해도 사라지지 않게 스테이지에 고정한다
  const pinnedSummary = [...messages]
    .reverse()
    .find((m) => m.role === "assistant" && m.stock?.symbol === symbol)?.content;

  const stage = !symbol ? (
    <MarketBoard onSelect={setSymbol} />
  ) : (
    <>
      <SymbolHeader
        symbol={symbol}
        resolvedTicker={pricesQ.data?.resolvedTicker}
        analyze={analyzeQ.data}
        isLoading={analyzeQ.isLoading}
        quotePrice={quoteQ.data?.price}
        previousClose={previousClose}
      />
      <StockVerdictHero
        symbol={pricesQ.data?.resolvedTicker ?? symbol}
        price={quoteQ.data?.price}
        analyze={analyzeQ.data}
        forecast={forecastQ.data}
        fundamentals={fundamentalsQ.data}
        expert={expert}
        onToggleExpert={toggleExpert}
      />
      {pinnedSummary && <SymbolSummary text={pinnedSummary} />}
      <StageSummary
        symbol={pricesQ.data?.resolvedTicker ?? symbol}
        price={quoteQ.data?.price}
        analyze={analyzeQ.data}
        forecast={forecastQ.data}
        expert={expert}
      />
      {pricesQ.isLoading && <div className="flex-1 m-4 skeleton rounded-xl" />}
      {pricesNotCollected && (
        <div className="flex-1 grid place-items-center px-6 text-center">
          <div>
            <p className="text-sm font-medium">이 종목의 시세를 찾지 못했어요</p>
            <p className="mt-1.5 text-xs text-foreground-muted leading-relaxed">
              종목 코드나 티커를 확인해주세요.
              <br />
              (미수집 종목도 라이브 조회로 차트가 제공됩니다 — 이 안내는 조회 자체가 실패한 경우예요)
            </p>
          </div>
        </div>
      )}
      {pricesQ.data && (
        <CandleChart
          bars={pricesQ.data.bars}
          support={analyzeQ.data?.support}
          resistance={analyzeQ.data?.resistance}
          forecast={timeframe === "1d" ? forecastQ.data : null}
          quotePrice={timeframe === "1d" ? quoteQ.data?.price : null}
          rangeDays={rangeDays}
          news={timeframe === "1d" ? newsQ.data : undefined}
          intraday={timeframe === "5m"}
          pattern={activePattern}
        />
      )}
      {activePattern && (
        <p className="shrink-0 px-4 pb-1 text-[11px] leading-relaxed text-foreground-muted">
          {activePattern.note} 점선이 그 형태의 꼭짓점을 잇습니다. 형태를 알아본 것일 뿐 앞으로의
          방향을 뜻하지 않습니다.
        </p>
      )}
      <div className="shrink-0 flex flex-wrap items-center gap-1 px-4 py-2 border-t border-border">
        {(["1d", "5m"] as const).map((tf) => (
          <button
            key={tf}
            type="button"
            // 타임프레임이 바뀌면 봉 배열이 통째로 달라져 형태 좌표가 무효가 된다
            onClick={() => setView({ timeframe: tf, rangeDays: DEFAULT_RANGE[tf], pattern: null })}
            aria-pressed={timeframe === tf}
            className={`px-3 h-7 rounded-md text-xs font-medium transition-colors ${
              timeframe === tf
                ? "bg-brand text-white"
                : "text-foreground-muted hover:bg-accent"
            }`}
          >
            {tf === "1d" ? "일봉" : "5분봉"}
          </button>
        ))}
        <span className="mx-1 h-4 w-px bg-border" aria-hidden />
        {RANGE_PRESETS[timeframe].map((preset) => (
          <button
            key={preset.label}
            type="button"
            onClick={() => setView((prev) => ({ ...prev, rangeDays: preset.days }))}
            aria-pressed={rangeDays === preset.days}
            className={`px-2.5 h-7 rounded-md text-xs font-medium transition-colors ${
              rangeDays === preset.days
                ? "border border-brand text-brand"
                : "text-foreground-muted hover:bg-accent"
            }`}
          >
            {preset.label}
          </button>
        ))}
        {timeframe === "5m" && (
          <span className="ml-2 text-[11px] text-foreground-muted">최근 60일 보유</span>
        )}
        {timeframe === "5m" && forecastQ.data?.band && (
          <span className="text-[11px] text-foreground-muted">· 예측 밴드는 일봉에서만 표시</span>
        )}
        {pricesQ.data?.live && (
          <span className="ml-2 px-2 py-0.5 rounded-full border border-border bg-surface text-[10px] text-foreground-muted">
            라이브 조회 · 수집 대상 아님
          </span>
        )}
        {patterns.length > 0 && (
          <>
            <span className="mx-1 h-4 w-px bg-border" aria-hidden />
            <span className="text-[11px] text-foreground-muted">형태</span>
            {patterns.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() =>
                  setView((prev) => ({
                    ...prev,
                    // 같은 칩을 다시 누르면 보조선을 끈다
                    pattern: prev.pattern === p.name ? null : p.name,
                  }))
                }
                aria-pressed={activePattern?.name === p.name}
                className={`px-2.5 h-7 rounded-md text-xs font-medium transition-colors ${
                  activePattern?.name === p.name
                    ? "bg-foreground text-background"
                    : "text-foreground-muted hover:bg-accent"
                }`}
              >
                {p.label}
                <span className="ml-1 tabular-nums opacity-70">
                  {Math.round(p.confidence * 100)}
                </span>
              </button>
            ))}
          </>
        )}
      </div>
    </>
  );

  return (
    <WorkspaceShell
      stageLabel="차트"
      stage={stage}
      panel={<StockPanel symbol={symbol} analyze={analyzeQ.data} />}
      chat={
        <ChatPanel
          workspace="stock"
          placeholder="종목명이나 티커로 물어보세요"
          emptyPrompts={EMPTY_PROMPTS}
          onSelectStock={(stock) => setSymbol(stock.symbol)}
        />
      }
    />
  );
}

export default function StockPage() {
  return (
    <Suspense>
      <StockWorkspace />
    </Suspense>
  );
}
