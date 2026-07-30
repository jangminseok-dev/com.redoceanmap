"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiConsentPending, apiMe, apiSocialConsent } from "@/lib/authApi";
import { useUIStore } from "@/lib/uiStore";

// 신규 소셜 가입자의 약관 동의 페이지 — auth 서버 콜백이 consent 쿠키(httpOnly)를 심고
// 여기로 302 시킨다. 프로필 표시는 서버(consent/pending)에서, 제출도 쿠키 기반.
const CONSENT_TERMS = [
  { name: "age", label: "(필수) 만 14세 이상입니다.", required: true },
  { name: "terms", label: "(필수) 이용약관 동의", required: true, href: "/terms" },
  { name: "privacy", label: "(필수) 개인정보 수집 및 이용 동의", required: true, href: "/privacy" },
  { name: "marketing", label: "(선택) 마케팅 정보 수신 동의", required: false },
];

function ConsentPage() {
  const search = useSearchParams();
  const router = useRouter();
  const setUser = useUIStore((s) => s.setUser);
  // 단일 객체 상태 — phase에 따라 로딩 / 동의 폼 / 에러로 분기 (REACT_RULES 단일 객체 패턴)
  const [state, setState] = useState<{
    phase: "loading" | "consent" | "error";
    error: string;
    loading: boolean;
    profile: { name: string; email: string } | null;
  }>({ phase: "loading", error: "", loading: false, profile: null });

  const returnTo = (() => {
    const raw = search?.get("return_to") ?? "/";
    return raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
  })();

  useEffect(() => {
    apiConsentPending()
      .then((p) => setState((prev) => ({ ...prev, phase: "consent", profile: p })))
      .catch(() =>
        setState((prev) => ({
          ...prev,
          phase: "error",
          error: "동의 대기 상태가 아니거나 만료되었습니다. 다시 로그인해 주세요.",
        })),
      );
  }, []);

  // FormData 패턴 — 체크박스는 uncontrolled, 제출 시점에 일괄 수집한다.
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    setState((prev) => ({ ...prev, error: "", loading: true }));
    try {
      await apiSocialConsent(formData.get("marketing") === "on");  // 세션 쿠키 발급됨
      setUser(await apiMe());
      router.replace(returnTo);
    } catch (err) {
      setState((prev) => ({
        ...prev,
        error: err instanceof Error ? err.message : "약관 동의 처리에 실패했습니다.",
        loading: false,
      }));
    }
  };

  const toggleAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    const form = e.currentTarget.form;
    if (!form) return;
    for (const t of CONSENT_TERMS) {
      const box = form.elements.namedItem(t.name);
      if (box instanceof HTMLInputElement) box.checked = e.currentTarget.checked;
    }
  };

  if (state.phase === "consent" && state.profile) {
    return (
      <div className="min-h-screen grid place-items-center px-4">
        <div className="w-full max-w-md bg-surface rounded-2xl shadow-xl p-8">
          <h1 className="text-xl font-bold text-center">redoceanmap</h1>
          <p className="mt-3 text-sm text-foreground-muted text-center">
            {state.profile.name}님({state.profile.email}), 처음 오셨네요.
            <br />
            서비스 이용을 위해 약관 동의가 필요합니다.
          </p>
          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-2 text-sm">
            <label className="flex items-center gap-2 font-semibold cursor-pointer">
              <input type="checkbox" className="accent-brand" onChange={toggleAll} />
              전체 동의합니다.
            </label>
            {CONSENT_TERMS.map((t) => (
              <label
                key={t.name}
                className="flex items-center gap-2 text-foreground-muted cursor-pointer pl-5"
              >
                <input type="checkbox" name={t.name} required={t.required} className="accent-brand" />
                {t.href ? (
                  <span>
                    {t.label.replace(" 동의", "")}{" "}
                    <a
                      href={t.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-foreground"
                    >
                      보기
                    </a>
                  </span>
                ) : (
                  t.label
                )}
              </label>
            ))}
            {state.error && <p className="text-sm text-red-500 text-center">{state.error}</p>}
            <button
              type="submit"
              disabled={state.loading}
              className="mt-4 w-full bg-brand text-white py-3 rounded-xl font-medium hover:bg-brand-deep transition-colors disabled:opacity-60"
            >
              {state.loading ? "처리 중..." : "동의하고 시작하기"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="text-center">
        {state.phase === "error" ? (
          <>
            <p className="text-sm text-red-500">{state.error}</p>
            <button
              type="button"
              onClick={() => router.replace("/")}
              className="mt-4 text-sm underline text-foreground-muted hover:text-foreground"
            >
              홈으로 돌아가기
            </button>
          </>
        ) : (
          <p className="text-sm text-foreground-muted">확인 중...</p>
        )}
      </div>
    </div>
  );
}

export default function OauthConsentPage() {
  return (
    <Suspense fallback={null}>
      <ConsentPage />
    </Suspense>
  );
}
