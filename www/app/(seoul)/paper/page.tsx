"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bot, ClipboardList, LineChart as LineChartIcon, Trophy, UserRound, Wallet } from "lucide-react";
import { fetchPaperAccount, fetchPaperBoard, fetchPaperDecisions, fetchPaperMe, fetchPaperScorecard } from "@/lib/api";
import { useUIStore } from "@/lib/uiStore";
import { Button } from "@/components/ui/button";
import Disclaimer from "@/components/stock/Disclaimer";
import DecisionFeed from "@/components/paper/DecisionFeed";
import EquityCurve from "@/components/paper/EquityCurve";
import Leaderboard from "@/components/paper/Leaderboard";
import OrderForm from "@/components/paper/OrderForm";
import PositionTable from "@/components/paper/PositionTable";
import RulesNotice from "@/components/paper/RulesNotice";
import Scorecard from "@/components/paper/Scorecard";
import TimeScrubber from "@/components/paper/TimeScrubber";
import TradeLog from "@/components/paper/TradeLog";
import { fmtKrw, fmtPct } from "@/components/paper/format";
import type { PaperEquityPoint } from "@/lib/types";

const DAY_STALE = 10 * 60_000; // 일 1회 갱신 데이터 — 재방문마다 다시 받을 이유가 없다

function Section({ icon: Icon, title, children, aside }: { icon: typeof Bot; title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <div className="flex items-baseline gap-2 flex-wrap">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold"><Icon size={15} /> {title}</h2>
        {aside}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** AI 모의투자 — 리더보드·자산 곡선·판단 되감기·채점·내 계정. 전부 기록 열람이며 권유가 아니다. */
export default function PaperPage() {
  const user = useUIStore((s) => s.user);
  const openAuth = useUIStore((s) => s.openAuth);
  // 단일 객체 패턴 — 선택 계정과 되감기 위치는 함께 움직인다(REACT_RULES 패턴 B)
  const [view, setView] = useState<{ account: string; dateIndex: number | null }>({ account: "exaone", dateIndex: null });

  const boardQ = useQuery({ queryKey: ["paper-board"], queryFn: fetchPaperBoard, staleTime: DAY_STALE });
  const exaoneQ = useQuery({ queryKey: ["paper-account", "exaone"], queryFn: () => fetchPaperAccount("exaone"), staleTime: DAY_STALE, retry: false });
  const signalQ = useQuery({ queryKey: ["paper-account", "signal"], queryFn: () => fetchPaperAccount("signal"), staleTime: DAY_STALE, retry: false });
  const meQ = useQuery({ queryKey: ["paper-me"], queryFn: fetchPaperMe, enabled: !!user, retry: false });
  const selectedIsAi = view.account === "exaone" || view.account === "signal";
  // 다른 참가자 계정 — AI 두 계정은 위 쿼리를 그대로 쓴다
  const otherQ = useQuery({
    queryKey: ["paper-account", view.account],
    queryFn: () => fetchPaperAccount(view.account),
    enabled: view.account.startsWith("user:"),
    staleTime: DAY_STALE,
    retry: false,
  });
  const decisionsQ = useQuery({
    queryKey: ["paper-decisions", view.account],
    queryFn: () => fetchPaperDecisions(view.account),
    enabled: selectedIsAi,
    staleTime: DAY_STALE,
  });
  const scorecardQ = useQuery({ queryKey: ["paper-scorecard", "exaone"], queryFn: () => fetchPaperScorecard("exaone"), staleTime: DAY_STALE, retry: false });

  const series: Record<string, PaperEquityPoint[]> = {};
  if (exaoneQ.data) series.exaone = exaoneQ.data.equity;
  if (signalQ.data) series.signal = signalQ.data.equity;
  if (meQ.data) series.me = meQ.data.equity;
  const markerKey = selectedIsAi ? view.account : "me";
  const selectedAccount = view.account === "exaone" ? exaoneQ.data : view.account === "signal" ? signalQ.data : otherQ.data;
  const markerTrades = selectedIsAi ? selectedAccount?.trades : meQ.data?.trades;

  // 되감기 — 판단이 있는 날짜(오름차순). 기본은 최신.
  const decisions = decisionsQ.data?.decisions ?? [];
  const dates = decisions.map((d) => d.as_of.slice(0, 10)).reverse();
  const dateIndex = view.dateIndex ?? Math.max(dates.length - 1, 0);
  const selectedDate = dates[dateIndex] ?? null;
  const decision = selectedDate ? decisions.find((d) => d.as_of.startsWith(selectedDate)) ?? null : null;
  const pickDate = (date: string) => {
    const i = dates.indexOf(date);
    if (i >= 0) setView((prev) => ({ ...prev, dateIndex: i }));
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight flex items-center gap-2"><Bot size={20} /> AI 모의투자</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            EXAONE이 매일 우리 데이터(예측 스냅샷·뉴스 라벨)를 읽고 내린 매매 판단을 사후 체결해 기록합니다.
            검증된 지표 규칙 계정과 SPY 보유를 나란히 두고, 같은 규칙으로 직접 참가할 수도 있습니다.
          </p>
        </div>

        {boardQ.isLoading && <div className="skeleton h-40 rounded-2xl" />}
        {boardQ.isError && (
          <p className="rounded-2xl border border-border bg-surface p-6 text-center text-sm text-foreground-muted">
            모의투자 기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
          </p>
        )}
        {boardQ.data && (
          <>
            <RulesNotice rules={boardQ.data.rules} replayUntil={boardQ.data.replay_until} />

            {boardQ.data.rows.length === 0 ? (
              <p className="rounded-2xl border border-border bg-surface p-6 text-center text-sm text-foreground-muted">
                아직 판단 기록이 없습니다. 첫 배치(매일 14:00) 뒤에 리더보드가 생깁니다.
              </p>
            ) : (
              <Leaderboard board={boardQ.data} selected={view.account} onSelect={(key) => setView({ account: key, dateIndex: null })} />
            )}

            <Section icon={LineChartIcon} title="자산 곡선" aside={<span className="text-xs text-foreground-muted">점은 선택 계정의 체결 · 음영은 리플레이 구간 · 클릭하면 그날 판단으로</span>}>
              <EquityCurve
                series={series}
                spy={boardQ.data.spy}
                markerKey={markerKey}
                trades={markerTrades ?? []}
                replayUntil={boardQ.data.replay_until}
                selectedDate={selectedIsAi ? selectedDate : null}
                onPickDate={selectedIsAi ? pickDate : undefined}
              />
            </Section>

            {selectedIsAi && (
              <Section icon={ClipboardList} title={`${view.account === "exaone" ? "EXAONE" : "지표 규칙"}의 판단`} aside={decisionsQ.data && <span className="text-xs text-foreground-muted">{dates.length}일치 기록</span>}>
                <TimeScrubber dates={dates} index={dateIndex} onChange={(i) => setView((prev) => ({ ...prev, dateIndex: i }))} />
                <div className="mt-4">
                  {decisionsQ.isLoading ? <div className="skeleton h-32 rounded-xl" /> : <DecisionFeed decision={decision} />}
                </div>
              </Section>
            )}

            {selectedAccount && (
              <Section icon={Wallet} title={`${selectedAccount.label} 계정`} aside={<span className="text-xs text-foreground-muted tabular-nums">자산 {fmtKrw(selectedAccount.equity_krw)} · 현금 {fmtKrw(selectedAccount.cash_krw)} · {fmtPct(selectedAccount.equity_krw / selectedAccount.initial_cash_krw - 1, 2)}</span>}>
                <PositionTable positions={selectedAccount.positions} />
                <h3 className="mt-4 text-xs font-semibold text-foreground-muted">최근 체결</h3>
                <TradeLog trades={selectedAccount.trades} />
              </Section>
            )}

            <Section icon={Trophy} title="EXAONE 판단 채점" aside={<span className="rounded-full bg-border/40 px-2 py-0.5 text-[11px] text-foreground-muted">검증되지 않은 판단 — 표본이 쌓이면 숫자가 열립니다</span>}>
              {scorecardQ.data ? <Scorecard card={scorecardQ.data} /> : <p className="text-sm text-foreground-muted">아직 채점된 판단이 없습니다.</p>}
            </Section>

            <Section icon={UserRound} title="내 계정" aside={meQ.data && <span className="text-xs text-foreground-muted tabular-nums">자산 {fmtKrw(meQ.data.equity_krw)} · {fmtPct(meQ.data.equity_krw / meQ.data.initial_cash_krw - 1, 2)}</span>}>
              {!user ? (
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-sm text-foreground-muted">로그인하면 같은 규칙으로 참가해 AI와 성적을 겨룰 수 있습니다.</p>
                  <Button size="md" onClick={() => openAuth("login")}>로그인</Button>
                </div>
              ) : meQ.isLoading ? (
                <div className="skeleton h-24 rounded-xl" />
              ) : meQ.data ? (
                <div className="space-y-4">
                  <OrderForm />
                  <PositionTable positions={meQ.data.positions} />
                  <h3 className="text-xs font-semibold text-foreground-muted">내 체결</h3>
                  <TradeLog trades={meQ.data.trades} />
                </div>
              ) : (
                <p className="text-sm text-foreground-muted">내 계정을 불러오지 못했습니다.</p>
              )}
            </Section>
          </>
        )}

        <footer className="pt-2 border-t border-border">
          <Disclaimer />
        </footer>
      </div>
    </div>
  );
}
