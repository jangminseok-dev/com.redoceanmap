"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, UserRound } from "lucide-react";
import {
  createPriceAlert,
  deletePriceAlert,
  fetchAlertSetting,
  fetchPriceAlerts,
  fetchProfile,
  removeProfile,
  saveAlertSetting,
  saveProfile,
} from "@/lib/api";
import type { InvestorProfile } from "@/lib/types";
import { useUIStore } from "@/lib/uiStore";
import { apiMe, apiRequestEmailVerification } from "@/lib/authApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// 선택지 라벨은 백엔드 도메인(profile_entity.py)의 매핑과 같은 문구를 쓴다 —
// 채팅 답변에 주입되는 라벨과 화면 표기가 어긋나지 않게.
const PURPOSES = [
  { value: "startup", label: "창업 준비" },
  { value: "invest", label: "주식 투자" },
  { value: "both", label: "창업·투자 둘 다" },
] as const;

const RISK_LEVELS = [
  { value: "1", label: "안정형" },
  { value: "2", label: "안정추구형" },
  { value: "3", label: "위험중립형" },
  { value: "4", label: "적극투자형" },
  { value: "5", label: "공격투자형" },
] as const;

const BUDGET_BANDS = [
  { value: "under_30m", label: "3천만원 미만" },
  { value: "30m_50m", label: "3천만~5천만원" },
  { value: "50m_100m", label: "5천만~1억원" },
  { value: "100m_300m", label: "1억~3억원" },
  { value: "over_300m", label: "3억원 이상" },
] as const;

const DEBT_BURDENS = [
  { value: "none", label: "없음" },
  { value: "manageable", label: "감당 가능" },
  { value: "heavy", label: "부담됨" },
] as const;

const HORIZONS = [
  { value: "short", label: "단기(1년 미만)" },
  { value: "mid", label: "중기(1~3년)" },
  { value: "long", label: "장기(3년 이상)" },
] as const;

function RadioGroup({
  name,
  legend,
  options,
  defaultValue,
}: {
  name: string;
  legend: string;
  options: readonly { value: string; label: string }[];
  defaultValue?: string;
}) {
  return (
    <fieldset>
      <legend className="text-sm font-semibold">{legend}</legend>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((o) => (
          <label key={o.value} className="cursor-pointer">
            <input
              type="radio"
              name={name}
              value={o.value}
              defaultChecked={o.value === defaultValue}
              required
              className="peer sr-only"
            />
            <span className="inline-flex items-center rounded-full border border-border px-3 py-1.5 text-sm text-foreground-muted peer-checked:border-brand peer-checked:bg-brand/10 peer-checked:font-medium peer-checked:text-brand">
              {o.label}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** 관심 대상(종목·상권) 알림 설정 — 수신 토글 + 텔레그램 채널(I-7). 미설정은 기본 수신. */
function AlertSettingSection() {
  const queryClient = useQueryClient();
  const { data, isPending } = useQuery({
    queryKey: ["alert-setting"],
    queryFn: fetchAlertSetting,
  });
  const save = useMutation({
    mutationFn: saveAlertSetting,
    onSuccess: (saved) => queryClient.setQueryData(["alert-setting"], saved),
  });

  const enabled = data?.email_alerts ?? true;
  const chatId = data?.telegram_chat_id ?? null;

  // 이메일 인증 — 메일 알림은 인증된 주소로만 나간다(텔레그램은 무관). 로그인 직후에는 스토어에 값이 없어 /auth/me로 확인한다
  const me = useQuery({ queryKey: ["auth-me"], queryFn: apiMe, staleTime: 60_000 });
  const verification = useMutation({ mutationFn: apiRequestEmailVerification });
  const needsVerification = me.data !== undefined && me.data.emailVerified === false;

  // 텔레그램 등록/해제 — 폼 제출 흐름이라 FormData 패턴(REACT_RULES 패턴 A)
  const handleTelegramSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const value = String(formData.get("telegram_chat_id") ?? "").trim();
    save.mutate({ email_alerts: enabled, telegram_chat_id: value || null });
  };

  return (
    <section className="rounded-2xl bg-surface border border-border p-6">
      <h2 className="text-sm font-semibold flex items-center gap-1.5">
        <BellRing size={15} /> 관심 종목·상권 알림
      </h2>
      <p className="mt-1 text-xs text-foreground-muted">
        북마크한 종목의 상승·하락 신호, 북마크한 상권의 새 분기 반영·등급 변동을
        알려드립니다(하루 1회 스캔, 같은 상태가 이어지면 다시 보내지 않습니다).
        끄면 이메일·텔레그램 모두 스캔 대상에서 빠집니다.
      </p>
      {isPending ? (
        <div className="mt-3 skeleton h-10 w-40 rounded-xl" />
      ) : (
        <>
          <div className="mt-3 flex gap-2">
            {([true, false] as const).map((value) => (
              <Button
                key={String(value)}
                size="md"
                variant={enabled === value ? "default" : "weak"}
                loading={save.isPending && save.variables?.email_alerts === value}
                onClick={() =>
                  enabled !== value &&
                  save.mutate({ email_alerts: value, telegram_chat_id: chatId })
                }
              >
                {value ? "알림 켬" : "알림 끔"}
              </Button>
            ))}
          </div>
          {needsVerification && (
            <div className="mt-3 rounded-xl border border-border bg-background p-3">
              <p className="text-xs leading-relaxed">
                <span className="font-medium">메일 알림을 받으려면 이메일 인증이 필요해요.</span>{" "}
                <span className="text-foreground-muted">
                  {me.data?.email}로 보낸 링크를 누르면 끝나요. 인증 전에도 서비스는 그대로 쓸 수 있고,
                  텔레그램 알림은 인증 없이 받습니다.
                </span>
              </p>
              <div className="mt-2 flex items-center gap-2">
                <Button
                  size="sm"
                  variant="weak"
                  loading={verification.isPending}
                  disabled={verification.isSuccess}
                  onClick={() => verification.mutate()}
                >
                  {verification.isSuccess ? "메일을 보냈어요" : "인증 메일 보내기"}
                </Button>
                {(verification.data || verification.error) && (
                  <span className="text-xs text-foreground-muted" role="status">
                    {verification.data?.message ?? (verification.error as Error).message}
                  </span>
                )}
              </div>
            </div>
          )}
          <form onSubmit={handleTelegramSubmit} className="mt-4 space-y-2">
            <Label htmlFor="telegram_chat_id" className="text-xs font-medium">
              텔레그램으로도 받기 (선택)
            </Label>
            <p className="text-xs text-foreground-muted">
              봇(@redoceanmap_bot)에게 /start를 보낸 뒤 안내받은 chat ID를 입력하세요.
              비워서 저장하면 해제됩니다.
            </p>
            <div className="flex gap-2">
              <Input
                id="telegram_chat_id"
                name="telegram_chat_id"
                defaultValue={chatId ?? ""}
                key={chatId ?? "empty"} // 조회 결과 도착 시 defaultValue 재적용
                placeholder="예: 123456789"
                inputMode="numeric"
                className="flex-1"
              />
              <Button type="submit" size="md" variant="weak" loading={save.isPending}>
                저장
              </Button>
            </div>
            {chatId && (
              <p className="text-xs text-foreground-muted">현재 등록됨: {chatId}</p>
            )}
          </form>
        </>
      )}
      {save.isError && (
        <p className="mt-2 text-xs text-brand">저장에 실패했습니다. 다시 시도해 주세요.</p>
      )}
    </section>
  );
}

/** 가격 도달 알림([6]) — 사용자가 직접 건 손절·익절선. 도달 시 1회 통지 후 자동 꺼짐. */
function PriceAlertSection() {
  const queryClient = useQueryClient();
  // 종목 화면 "이 가격 되면 알림"에서 넘어오면 ?ticker= 로 종목 칸을 미리 채운다(하이드레이션 뒤에 읽는다)
  const [prefill, setPrefill] = useState("");
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("ticker");
    if (t) setPrefill(t);
  }, []);
  const { data, isPending } = useQuery({
    queryKey: ["price-alerts"],
    queryFn: fetchPriceAlerts,
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["price-alerts"] });
  const create = useMutation({ mutationFn: createPriceAlert, onSuccess: invalidate });
  const remove = useMutation({ mutationFn: deletePriceAlert, onSuccess: invalidate });

  // 조건 등록 — 폼 제출 흐름이라 FormData 패턴(REACT_RULES 패턴 A)
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const ticker = String(formData.get("ticker") ?? "").trim();
    const price = Number(formData.get("target_price"));
    const direction = String(formData.get("direction")) as "above" | "below";
    if (!ticker || !(price > 0)) return;
    create.mutate({ ticker, target_price: price, direction });
    e.currentTarget.reset();
  };

  const alerts = data?.alerts ?? [];
  const fmtPrice = (a: { ticker: string; target_price: number }) =>
    /^\d+$/.test(a.ticker.split(".")[0])
      ? `${Math.round(a.target_price).toLocaleString("ko-KR")}원`
      : `$${a.target_price.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}`;

  return (
    <section id="price-alert" className="rounded-2xl bg-surface border border-border p-6">
      <h2 className="text-sm font-semibold flex items-center gap-1.5">
        <BellRing size={15} /> 가격 도달 알림
      </h2>
      <p className="mt-1 text-xs text-foreground-muted">
        원하는 가격(손절·익절선)에 닿으면 이메일·텔레그램으로 알려드립니다. 방향 예측이
        아니라 직접 정한 가격의 도달 사실 통지예요. 도달하면 1회 알림 후 자동으로 꺼지고,
        수집 주기 기준이라 최대 1시간가량 늦을 수 있습니다.
      </p>
      <form onSubmit={handleSubmit} className="mt-3 flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="pa-ticker" className="text-xs font-medium">종목</Label>
          <Input id="pa-ticker" name="ticker" defaultValue={prefill} key={prefill || "empty"} placeholder="005930 · AAPL" className="w-32" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="pa-price" className="text-xs font-medium">가격</Label>
          <Input
            id="pa-price" name="target_price" type="number" step="any" min="0"
            placeholder="70000" className="w-32"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="pa-direction" className="text-xs font-medium">조건</Label>
          {/* 네이티브 select 유지 — shadcn 미이관 목록(www CLAUDE §4)과 동일 취급 */}
          <select
            id="pa-direction" name="direction" defaultValue="below"
            className="h-10 rounded-xl border border-border bg-surface px-3 text-sm"
          >
            <option value="below">이하로 내려오면</option>
            <option value="above">이상으로 올라가면</option>
          </select>
        </div>
        <Button type="submit" size="md" variant="weak" loading={create.isPending}>
          조건 걸기
        </Button>
      </form>
      {create.isError && (
        <p className="mt-2 text-xs text-brand">
          {create.error instanceof Error ? create.error.message : "등록에 실패했습니다."}
        </p>
      )}
      {isPending ? (
        <div className="mt-3 skeleton h-10 rounded-xl" />
      ) : alerts.length === 0 ? (
        <p className="mt-3 text-xs text-foreground-muted">아직 등록한 조건이 없어요.</p>
      ) : (
        <ul className="mt-3 divide-y divide-border">
          {alerts.map((a) => (
            <li key={a.id} className="flex items-center gap-2 py-2 text-sm">
              <span className="font-semibold">{a.ticker}</span>
              <span className="text-foreground-muted">
                {fmtPrice(a)} {a.direction === "above" ? "이상" : "이하"}
              </span>
              {a.active ? (
                <span className="text-xs px-2 py-0.5 rounded-full bg-up-weak text-up">감시 중</span>
              ) : (
                <span className="text-xs px-2 py-0.5 rounded-full bg-border/60 text-foreground-muted">
                  도달 통지됨
                </span>
              )}
              <Button
                size="sm" variant="ghost" className="ml-auto text-foreground-muted"
                loading={remove.isPending && remove.variables === a.id}
                onClick={() => remove.mutate(a.id)}
              >
                삭제
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** 투자·창업 프로파일 설문 — 밴드(구간)만 저장하고 채팅 분석 서술의 관점 조정에 쓴다. */
export default function ProfilePage() {
  const user = useUIStore((s) => s.user);
  const openAuth = useUIStore((s) => s.openAuth);
  const queryClient = useQueryClient();
  const { data, isPending, isError } = useQuery({
    queryKey: ["profile"],
    queryFn: fetchProfile,
    enabled: !!user,
  });
  const save = useMutation({
    mutationFn: saveProfile,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });
  const remove = useMutation({
    mutationFn: removeProfile,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  const profile = data?.profile ?? null;

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const formProps = Object.fromEntries(formData.entries());
    save.mutate({
      purpose: formProps.purpose as InvestorProfile["purpose"],
      risk_level: Number(formProps.risk_level) as InvestorProfile["risk_level"],
      budget_band: formProps.budget_band as InvestorProfile["budget_band"],
      debt_burden: formProps.debt_burden as InvestorProfile["debt_burden"],
      horizon: formProps.horizon as InvestorProfile["horizon"],
    });
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <UserRound size={20} /> 내 프로파일
          </h1>
          <p className="mt-1 text-sm text-foreground-muted">
            답해두면 채팅의 상권·주식 분석이 내 상황에 맞는 관점으로 설명됩니다. 정확한
            금액·계좌·신용점수는 받지 않고 구간만 저장하며, 매매 지시나 상품 추천에는 쓰이지
            않습니다.
          </p>
        </div>

        {!user ? (
          <section className="rounded-2xl bg-surface border border-border p-8 text-center space-y-3">
            <p className="text-sm text-foreground-muted">로그인하면 프로파일을 저장할 수 있습니다.</p>
            <Button size="md" onClick={() => openAuth("login")}>로그인</Button>
          </section>
        ) : isPending ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton h-20 rounded-xl" />
            ))}
          </div>
        ) : isError ? (
          <section className="rounded-2xl bg-surface border border-border p-8 text-center text-sm text-foreground-muted">
            프로파일을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
          </section>
        ) : (
          <>
          <AlertSettingSection />
          <PriceAlertSection />
          <form
            key={profile ? profile.updated_at : "empty"} // 조회 결과 도착 시 defaultChecked 재적용
            onSubmit={handleSubmit}
            className="rounded-2xl bg-surface border border-border p-6 space-y-6"
          >
            <RadioGroup
              name="purpose"
              legend="이 서비스를 쓰는 목적"
              options={PURPOSES}
              defaultValue={profile?.purpose}
            />
            <RadioGroup
              name="risk_level"
              legend="투자성향"
              options={RISK_LEVELS}
              defaultValue={profile ? String(profile.risk_level) : undefined}
            />
            <RadioGroup
              name="budget_band"
              legend="가용 예산 (창업 자금 또는 운용 가능 금액)"
              options={BUDGET_BANDS}
              defaultValue={profile?.budget_band}
            />
            <RadioGroup
              name="debt_burden"
              legend="부채 부담"
              options={DEBT_BURDENS}
              defaultValue={profile?.debt_burden}
            />
            <RadioGroup
              name="horizon"
              legend="투자·회수 기간"
              options={HORIZONS}
              defaultValue={profile?.horizon}
            />

            <div className="space-y-2">
              <Button type="submit" size="lg" className="w-full" loading={save.isPending}>
                {profile ? "프로파일 다시 저장" : "프로파일 저장"}
              </Button>
              {save.isSuccess && (
                <p className="text-sm text-foreground-muted text-center">
                  저장되었습니다 — 다음 채팅 답변부터 반영됩니다.
                </p>
              )}
              {save.isError && (
                <p className="text-sm text-brand text-center">저장에 실패했습니다. 다시 시도해 주세요.</p>
              )}
              {profile && (
                <Button
                  type="button"
                  variant="weak"
                  size="md"
                  className="w-full"
                  loading={remove.isPending}
                  onClick={() => remove.mutate()}
                >
                  프로파일 삭제 (개인화 끄기)
                </Button>
              )}
            </div>
          </form>
          </>
        )}
      </div>
    </div>
  );
}
