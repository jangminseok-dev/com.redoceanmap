"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Coins, TrendingUp } from "lucide-react";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import Empty from "@/components/admin/Empty";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  fetchAdminGameBoard,
  fetchAdminGameWallet,
  grantAdminGameCapital,
  interveneAdminGamePrice,
  type AdminGameSymbol,
} from "@/lib/adminApi";

const won = (v: number) => `${v.toLocaleString()}원`;
const signed = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;

// 백엔드 price_intervention.SCOPES와 같은 축
const SCOPE_LABEL: Record<string, string> = {
  symbol: "종목 1개",
  sector: "묶음 업종",
  market: "시장 전체",
};

/** 폼 상태는 서로 물려 있어 한 객체로 든다(REACT_RULES 패턴 B) */
type Form = {
  userId: string;
  amount: string;
  reason: string;
  scope: "symbol" | "sector" | "market";
  target: string;
  mode: "pct" | "price"; // 즉시 충격을 %로 넣을지 목표가로 넣을지
  shockPct: string;
  targetPrice: string;
  driftPct: string;
  durationDays: string;
  headline: string;
  note: string;
  notice: string | null;
};

const EMPTY: Form = {
  userId: "",
  amount: "1000000",
  reason: "",
  scope: "symbol",
  target: "",
  mode: "pct",
  shockPct: "10",
  targetPrice: "",
  driftPct: "0",
  durationDays: "2",
  headline: "",
  note: "",
  notice: null,
};

function GameOps() {
  // 회원관리의 "게임 지갑" 버튼이 /admin/game?userId=16 으로 넘겨준다 — 사람이 ID를 옮겨 적지 않는다.
  const initialUserId = useSearchParams()?.get("userId") ?? "";
  const [form, setForm] = useState<Form>({ ...EMPTY, userId: initialUserId });
  const patch = (next: Partial<Form>) => setForm((prev) => ({ ...prev, ...next }));
  const queryClient = useQueryClient();

  const boardQ = useQuery({ queryKey: ["admin-game-board"], queryFn: fetchAdminGameBoard });
  const userId = Number(form.userId);
  const walletQ = useQuery({
    queryKey: ["admin-game-wallet", userId],
    queryFn: () => fetchAdminGameWallet(userId),
    enabled: Number.isInteger(userId) && userId > 0,
  });

  const grant = useMutation({
    mutationFn: () =>
      grantAdminGameCapital(userId, {
        amount_krw: Number(form.amount),
        reason: form.reason.trim(),
      }),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["admin-game-wallet", userId] });
      patch({
        notice: `${r.user_id}번 유저에게 ${won(r.amount_krw)} 반영 — 잔고 ${won(r.cash_krw)}`,
        reason: "",
      });
    },
    onError: (e) => patch({ notice: e instanceof Error ? e.message : "지급에 실패했습니다." }),
  });

  const intervene = useMutation({
    mutationFn: () =>
      interveneAdminGamePrice({
        scope: form.scope,
        target: form.scope === "market" ? "" : form.target,
        shock_pct: form.mode === "pct" ? Number(form.shockPct) : 0,
        drift_pct_per_day: Number(form.driftPct),
        duration_days: Number(form.durationDays),
        headline: form.headline.trim(),
        note: form.note.trim() || null,
        target_price_krw:
          form.mode === "price" && form.targetPrice ? Number(form.targetPrice) : null,
      }),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["admin-game-board"] });
      patch({
        notice: `${r.target_name} 개입 반영 — 즉시 ${signed(r.shock_pct)} · ${r.duration_days}게임일`,
        headline: "",
        note: "",
      });
    },
    onError: (e) => patch({ notice: e instanceof Error ? e.message : "개입에 실패했습니다." }),
  });

  const board = boardQ.data;
  const wallet = walletQ.data;
  const selected: AdminGameSymbol | undefined = board?.symbols.find(
    (s) => s.symbol === form.target,
  );
  const targetOptions =
    form.scope === "symbol"
      ? (board?.symbols ?? []).map((s) => ({ value: s.symbol, label: `${s.name} (${won(s.price_krw)})` }))
      : form.scope === "sector"
        ? (board?.sector_groups ?? []).map((g) => ({ value: g, label: g }))
        : [];

  const grantReady =
    Number.isInteger(userId) && userId > 0 && Number(form.amount) !== 0 && !!form.reason.trim();
  const interveneReady =
    !!form.headline.trim() &&
    (form.scope === "market" || !!form.target) &&
    (form.mode === "pct" ? Number(form.shockPct) !== 0 || Number(form.driftPct) !== 0 : !!form.targetPrice);

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight">게임 운영</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          모의투자 게임의 자본과 주가에 직접 개입합니다. 개입은{" "}
          <span className="font-medium text-foreground">지금부터 앞으로만</span> 적용되며 과거
          주가는 바뀌지 않습니다 — 이미 체결된 체결가·분기 결산이 소급 변조되지 않게 하기
          위해서입니다.
        </p>
      </div>

      {form.notice && (
        <p className="rounded-xl border border-border bg-surface px-4 py-2.5 text-sm">
          {form.notice}
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        {/* ── 자본 지급 ── */}
        <section className="rounded-2xl bg-surface border border-border p-5">
          <h2 className="flex items-center gap-2 text-sm font-bold tracking-tight">
            <Coins size={15} strokeWidth={2} />
            자본 지급
          </h2>
          <p className="mt-1 text-xs text-foreground-muted">
            원장에 <code>admin</code> 한 줄이 함께 남습니다. 음수를 넣으면 회수입니다.
          </p>

          <div className="mt-4 space-y-3">
            <label className="block text-xs text-foreground-muted">
              유저 ID
              <Input
                type="number"
                value={form.userId}
                onChange={(e) => patch({ userId: e.target.value })}
                placeholder="회원 관리에서 확인한 ID"
                className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
              />
            </label>

            {walletQ.isFetching && <BlockSkeleton rows={2} />}
            {wallet && (
              <div className="rounded-xl border border-border px-3 py-2.5 text-xs space-y-1">
                <p className="font-medium text-sm">{wallet.email || "(이메일 없음)"}</p>
                {wallet.exists ? (
                  <>
                    <p className="tabular-nums">
                      잔고 <span className="font-semibold">{won(wallet.cash_krw)}</span> · 보유
                      포지션 {wallet.open_position_count}건 · 시즌 {wallet.epoch_id}(
                      {wallet.rule_version})
                    </p>
                    {!wallet.ledger_matches && (
                      <p className="flex items-start gap-1.5 text-[#DC2626]">
                        <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                        원장 합계({won(wallet.ledger_total_krw)})가 잔고와 다릅니다 — 어딘가에서
                        돈이 샜습니다.
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-foreground-muted">
                    아직 게임을 시작하지 않은 유저입니다. 지급하면 초기 자본으로 지갑이 먼저
                    열립니다.
                  </p>
                )}
              </div>
            )}

            <label className="block text-xs text-foreground-muted">
              금액 (음수 = 회수)
              <Input
                type="number"
                step={100000}
                value={form.amount}
                onChange={(e) => patch({ amount: e.target.value })}
                className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
              />
            </label>

            <label className="block text-xs text-foreground-muted">
              사유 (원장·감사에 남습니다)
              <Input
                value={form.reason}
                onChange={(e) => patch({ reason: e.target.value })}
                maxLength={200}
                placeholder="예: 베타 테스트 보상"
                className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm"
              />
            </label>

            <Button
              type="button"
              onClick={() => grant.mutate()}
              disabled={!grantReady || grant.isPending}
              size="lg"
              className="w-full"
            >
              {grant.isPending
                ? "반영 중…"
                : Number(form.amount) < 0
                  ? `${won(Math.abs(Number(form.amount)))} 회수`
                  : `${won(Number(form.amount) || 0)} 지급`}
            </Button>
          </div>
        </section>

        {/* ── 주가 개입 ── */}
        <section className="rounded-2xl bg-surface border border-border p-5">
          <h2 className="flex items-center gap-2 text-sm font-bold tracking-tight">
            <TrendingUp size={15} strokeWidth={2} />
            주가 개입
          </h2>
          <p className="mt-1 text-xs text-foreground-muted">
            유저 화면에는 <span className="font-medium text-foreground">일반 뉴스로</span> 보입니다.
            취소는 없습니다 — 잘못 넣었으면 반대 방향으로 한 번 더 넣어 정정하고, 개입은{" "}
            {board?.max_duration_days ?? 5}게임일 안에 저절로 소멸합니다.
          </p>

          <div className="mt-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-foreground-muted">
                범위
                <select
                  value={form.scope}
                  onChange={(e) =>
                    patch({ scope: e.target.value as Form["scope"], target: "", mode: "pct" })
                  }
                  className="mt-1 w-full h-10 px-2 rounded-xl border border-border bg-background text-sm text-foreground"
                >
                  {Object.entries(SCOPE_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>

              {form.scope !== "market" && (
                <label className="block text-xs text-foreground-muted">
                  대상
                  <select
                    value={form.target}
                    onChange={(e) => patch({ target: e.target.value })}
                    className="mt-1 w-full h-10 px-2 rounded-xl border border-border bg-background text-sm text-foreground"
                  >
                    <option value="">선택하세요</option>
                    {targetOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>

            {/* 목표가 지정은 현재가를 아는 종목 개입에서만 성립한다 */}
            {form.scope === "symbol" && (
              <div className="flex gap-1.5">
                {(["pct", "price"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => patch({ mode: m })}
                    className={`h-8 px-3 rounded-lg text-xs font-medium transition-colors ${
                      form.mode === m
                        ? "bg-brand text-white"
                        : "text-foreground-muted hover:bg-accent"
                    }`}
                  >
                    {m === "pct" ? "퍼센트로" : "목표가로"}
                  </button>
                ))}
              </div>
            )}

            <div className="grid grid-cols-3 gap-3">
              {form.mode === "price" && form.scope === "symbol" ? (
                <label className="col-span-3 block text-xs text-foreground-muted">
                  목표가 {selected && `(현재 ${won(selected.price_krw)})`}
                  <Input
                    type="number"
                    value={form.targetPrice}
                    onChange={(e) => patch({ targetPrice: e.target.value })}
                    className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
                  />
                </label>
              ) : (
                <label className="block text-xs text-foreground-muted">
                  즉시 충격 %
                  <Input
                    type="number"
                    step={1}
                    value={form.shockPct}
                    onChange={(e) => patch({ shockPct: e.target.value })}
                    className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
                  />
                </label>
              )}
              <label className="block text-xs text-foreground-muted">
                드리프트 %/일
                <Input
                  type="number"
                  step={0.5}
                  value={form.driftPct}
                  onChange={(e) => patch({ driftPct: e.target.value })}
                  className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
                />
              </label>
              <label className="block text-xs text-foreground-muted">
                지속 게임일
                <Input
                  type="number"
                  min={1}
                  max={board?.max_duration_days ?? 5}
                  value={form.durationDays}
                  onChange={(e) => patch({ durationDays: e.target.value })}
                  className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
                />
              </label>
            </div>

            <label className="block text-xs text-foreground-muted">
              유저에게 보일 뉴스 문구
              <Input
                value={form.headline}
                onChange={(e) => patch({ headline: e.target.value })}
                maxLength={120}
                placeholder="예: 세빛반도체 신규 대형 수주 공시"
                className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm"
              />
            </label>

            <label className="block text-xs text-foreground-muted">
              관리자 메모 (유저에게 보이지 않습니다)
              <Input
                value={form.note}
                onChange={(e) => patch({ note: e.target.value })}
                maxLength={200}
                className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm"
              />
            </label>

            <Button
              type="button"
              onClick={() => intervene.mutate()}
              disabled={!interveneReady || intervene.isPending}
              size="lg"
              className="w-full"
            >
              {intervene.isPending ? "반영 중…" : "지금부터 적용"}
            </Button>
          </div>
        </section>
      </div>

      {/* ── 개입 이력 ── */}
      <section className="rounded-2xl bg-surface border border-border">
        <h2 className="px-5 pt-5 text-sm font-bold tracking-tight">개입 이력 (현재 시즌)</h2>
        {boardQ.isPending && <BlockSkeleton rows={4} />}
        {board && board.interventions.length === 0 && <Empty msg="아직 개입한 적이 없습니다." />}
        {board && board.interventions.length > 0 && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-foreground-muted">
                <tr className="border-b border-border">
                  <th className="text-left font-medium px-5 py-2">대상</th>
                  <th className="text-left font-medium px-3 py-2">문구</th>
                  <th className="text-right font-medium px-3 py-2">즉시</th>
                  <th className="text-right font-medium px-3 py-2">드리프트</th>
                  <th className="text-right font-medium px-3 py-2">게임일</th>
                  <th className="text-left font-medium px-5 py-2">상태</th>
                </tr>
              </thead>
              <tbody>
                {board.interventions.map((i) => (
                  <tr key={i.id} className="border-b border-border last:border-0">
                    <td className="px-5 py-2.5">
                      <span className="font-medium">{i.target_name}</span>
                      <span className="ml-1.5 text-xs text-foreground-muted">
                        {SCOPE_LABEL[i.scope] ?? i.scope}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      {i.headline}
                      {i.note && (
                        <span className="block text-xs text-foreground-muted">메모: {i.note}</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{signed(i.shock_pct)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {signed(i.drift_pct_per_day)}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{i.from_game_day}일차</td>
                    <td className="px-5 py-2.5">
                      <span
                        className={
                          i.in_effect ? "text-[#DC2626] font-medium" : "text-foreground-muted"
                        }
                      >
                        {i.in_effect ? "반영 중" : "소멸"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default function GameOpsPage() {
  // useSearchParams는 Suspense 경계 안에서만 쓴다(market/page.tsx와 같은 형태).
  return (
    <Suspense>
      <GameOps />
    </Suspense>
  );
}
