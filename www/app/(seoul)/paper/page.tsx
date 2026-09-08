"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bot, ChevronDown, Wallet } from "lucide-react";
import { fetchPaperAccount, fetchPaperBoard, fetchPaperDecisions, fetchPaperMe, fetchPaperScorecard } from "@/lib/api";
import { useUIStore } from "@/lib/uiStore";
import Disclaimer from "@/components/stock/Disclaimer";
import ActivityFeed from "@/components/paper/ActivityFeed";
import DecisionFeed from "@/components/paper/DecisionFeed";
import EquityCurve from "@/components/paper/EquityCurve";
import HoldingsGrid from "@/components/paper/HoldingsGrid";
import OrderForm from "@/components/paper/OrderForm";
import RulesNotice from "@/components/paper/RulesNotice";
import ScoreBoard from "@/components/paper/ScoreBoard";
import Scorecard from "@/components/paper/Scorecard";
import TimeScrubber from "@/components/paper/TimeScrubber";
import TradeLog from "@/components/paper/TradeLog";
import { fmtDay } from "@/components/paper/format";
import type { PaperEquityPoint } from "@/lib/types";

const DAY_STALE = 10 * 60_000; // 일 1회 갱신 데이터 — 재방문마다 다시 받을 이유가 없다

function Card({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <div className="flex items-baseline gap-2 flex-wrap">
        <h2 className="text-base font-semibold">{title}</h2>
        {sub && <span className="text-xs text-foreground-muted">{sub}</span>}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/**
 * AI 모의투자 — 게임처럼 읽히는 순서: 점수판 → AI가 오늘 한 일 → AI 지갑 → 나도 사보기.
 * 곡선·판단 원문·채점 같은 분석은 맨 아래 "자세히 보기"로 접는다. 전부 기록이지 권유가 아니다.
 */
export default function PaperPage() {
  const user = useUIStore((s) => s.user);
  const openAuth = useUIStore((s) => s.openAuth);
  // 단일 객체 패턴 — 상세 펼침과 되감기 위치(REACT_RULES 패턴 B)
  const [view, setView] = useState<{ details: boolean; dateIndex: number | null }>({ details: false, dateIndex: null });

  const boardQ = useQuery({ queryKey: ["paper-board"], queryFn: fetchPaperBoard, staleTime: DAY_STALE });
  const exaoneQ = useQuery({ queryKey: ["paper-account", "exaone"], queryFn: () => fetchPaperAccount("exaone"), staleTime: DAY_STALE, retry: false });
  const signalQ = useQuery({ queryKey: ["paper-account", "signal"], queryFn: () => fetchPaperAccount("signal"), staleTime: DAY_STALE, retry: false });
  const meQ = useQuery({ queryKey: ["paper-me"], queryFn: fetchPaperMe, enabled: !!user, retry: false });
  const decisionsQ = useQuery({ queryKey: ["paper-decisions", "exaone"], queryFn: () => fetchPaperDecisions("exaone"), staleTime: DAY_STALE });
  const scorecardQ = useQuery({ queryKey: ["paper-scorecard", "exaone"], queryFn: () => fetchPaperScorecard("exaone"), staleTime: DAY_STALE, retry: false, enabled: view.details });

  const decisions = decisionsQ.data?.decisions ?? []; // as_of 내림차순
  const latest = decisions[0] ?? null;
  const dates = decisions.map((d) => d.as_of.slice(0, 10)).reverse();
  const dateIndex = view.dateIndex ?? Math.max(dates.length - 1, 0);
  const selectedDate = dates[dateIndex] ?? null;
  const selected = selectedDate ? decisions.find((d) => d.as_of.startsWith(selectedDate)) ?? null : null;
  const pickDate = (date: string) => {
    const i = dates.indexOf(date);
    if (i >= 0) setView((prev) => ({ ...prev, details: true, dateIndex: i }));
  };

  const series: Record<string, PaperEquityPoint[]> = {};
  if (exaoneQ.data) series.exaone = exaoneQ.data.equity;
  if (signalQ.data) series.signal = signalQ.data.equity;
  if (meQ.data) series.me = meQ.data.equity;
  const aiTickers = exaoneQ.data?.positions.map((p) => p.ticker) ?? [];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight flex items-center gap-2"><Bot size={20} /> AI 모의투자</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            EXAONE이 매일 우리 뉴스·신호를 읽고 1억원으로 사고팝니다. 같은 돈으로 겨뤄 보세요.
          </p>
        </div>

        {boardQ.isLoading && <div className="skeleton h-40 rounded-2xl" />}
        {boardQ.isError && (
          <p className="rounded-2xl border border-border bg-surface p-6 text-center text-sm text-foreground-muted">
            기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
          </p>
        )}
        {boardQ.data && (
          <>
            <ScoreBoard board={boardQ.data} myKey={user ? `user:${user.id}` : null} onJoin={() => (user ? undefined : openAuth("login"))} />

            <Card title="AI가 한 일" sub={latest ? `${fmtDay(latest.as_of)} 판단까지 · 체결은 다음 장 시가` : undefined}>
              {latest?.market_view && <p className="mb-3 text-sm leading-relaxed">💬 {latest.market_view}</p>}
              <ActivityFeed trades={exaoneQ.data?.trades ?? []} latest={latest} />
            </Card>

            <Card title="AI 지갑" sub={exaoneQ.data ? `보유 ${exaoneQ.data.positions.length}종목` : undefined}>
              <HoldingsGrid positions={exaoneQ.data?.positions ?? []} empty="지금은 다 현금이에요." />
            </Card>

            <Card title="나도 사보기" sub="같은 1억원 · 같은 수수료 · 최신 저장 시세에 바로 체결">
              {!user ? (
                <p className="text-sm text-foreground-muted">
                  <button type="button" onClick={() => openAuth("login")} className="text-brand font-medium underline-offset-2 hover:underline">로그인</button>
                  하면 1억원 계정이 생기고 AI와 나란히 성적이 붙습니다.
                </p>
              ) : meQ.isLoading ? (
                <div className="skeleton h-24 rounded-xl" />
              ) : meQ.data ? (
                <div className="space-y-4">
                  <OrderForm suggestions={aiTickers} />
                  <div>
                    <h3 className="text-xs font-semibold text-foreground-muted flex items-center gap-1"><Wallet size={12} /> 내 지갑</h3>
                    <div className="mt-2">
                      <HoldingsGrid positions={meQ.data.positions} empty="아직 아무것도 안 샀어요. 위에서 종목을 골라 보세요." />
                    </div>
                  </div>
                  {meQ.data.trades.length > 0 && (
                    <div>
                      <h3 className="text-xs font-semibold text-foreground-muted">내 체결</h3>
                      <TradeLog trades={meQ.data.trades} limit={10} />
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-foreground-muted">내 계정을 불러오지 못했습니다.</p>
              )}
            </Card>

            <RulesNotice rules={boardQ.data.rules} replayUntil={boardQ.data.replay_until} />

            {/* 분석은 접어 둔다 — 궁금한 사람만 연다 */}
            <button
              type="button"
              onClick={() => setView((prev) => ({ ...prev, details: !prev.details }))}
              aria-expanded={view.details}
              className="w-full flex items-center justify-center gap-1.5 py-3 text-sm text-foreground-muted hover:text-foreground transition-colors"
            >
              <ChevronDown size={15} className={`transition-transform ${view.details ? "rotate-180" : ""}`} />
              자세히 보기 — 자산 곡선 · 판단 원문 · 채점 · 지표 규칙 계정
            </button>

            {view.details && (
              <div className="space-y-5">
                <Card title="자산 곡선" sub="점은 EXAONE의 체결 · 음영은 리플레이 구간 · 클릭하면 그날 판단으로">
                  <EquityCurve
                    series={series}
                    spy={boardQ.data.spy}
                    markerKey="exaone"
                    trades={exaoneQ.data?.trades ?? []}
                    replayUntil={boardQ.data.replay_until}
                    selectedDate={selectedDate}
                    onPickDate={pickDate}
                  />
                </Card>
                <Card title="EXAONE의 판단 원문" sub={`${dates.length}일치 · 되감기`}>
                  <TimeScrubber dates={dates} index={dateIndex} onChange={(i) => setView((prev) => ({ ...prev, dateIndex: i }))} />
                  <div className="mt-4">
                    {decisionsQ.isLoading ? <div className="skeleton h-32 rounded-xl" /> : <DecisionFeed decision={selected} />}
                  </div>
                </Card>
                <Card title="EXAONE 판단 채점" sub="검증되지 않은 판단 — 표본이 쌓이면 숫자가 열립니다">
                  {scorecardQ.data ? <Scorecard card={scorecardQ.data} /> : <p className="text-sm text-foreground-muted">아직 채점된 판단이 없습니다.</p>}
                </Card>
                <Card title="지표 규칙 계정" sub="검증된 신호만 그대로 따르는 대조군">
                  <HoldingsGrid positions={signalQ.data?.positions ?? []} empty="지금은 다 현금이에요." />
                  {signalQ.data && signalQ.data.trades.length > 0 && (
                    <div className="mt-4">
                      <h3 className="text-xs font-semibold text-foreground-muted">최근 체결</h3>
                      <TradeLog trades={signalQ.data.trades} limit={10} />
                    </div>
                  )}
                </Card>
              </div>
            )}
          </>
        )}

        <footer className="pt-2 border-t border-border">
          <Disclaimer />
        </footer>
      </div>
    </div>
  );
}
