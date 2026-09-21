// BFF 인증 클라이언트 — 토큰은 httpOnly 쿠키에만 산다(JS는 만질 수 없음).
//
// AUTH_BASE 단일 상수(bff-cloudflared B.0) 외에 분기 코드를 퍼뜨리지 않는다:
// - prod: NEXT_PUBLIC_AUTH_ORIGIN(https://auth.redoceanmap.com) 설정 → 이중문 직행
//   (cross-origin이므로 credentials: "include" 필수)
// - dev/미설정: /api/backend/auth 프록시(same-origin) 폴백 — rewrites가 9000으로 전달
const AUTH_ORIGIN = process.env.NEXT_PUBLIC_AUTH_ORIGIN;
export const AUTH_BASE = AUTH_ORIGIN ? `${AUTH_ORIGIN}/auth` : "/api/backend/auth";
const CREDENTIALS: RequestCredentials = AUTH_ORIGIN ? "include" : "same-origin";

export type SessionUser = { name: string; email: string };

async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${AUTH_BASE}${path}`, {
    credentials: CREDENTIALS,
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
}

async function jsonOrThrow<T>(res: Response, fallback: string): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail ?? fallback);
  return data as T;
}

export async function apiLogin(email: string, password: string): Promise<SessionUser> {
  const res = await authFetch("/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return jsonOrThrow<SessionUser>(res, "로그인에 실패했습니다.");
}

export async function apiRegister(
  email: string,
  password: string,
  name: string,
  marketingAgreed: boolean,
): Promise<SessionUser> {
  const res = await authFetch("/register", {
    method: "POST",
    // terms_agreed: 필수 약관 체크를 통과해야만 제출되므로 항상 true
    body: JSON.stringify({ email, password, name, terms_agreed: true, marketing_agreed: marketingAgreed }),
  });
  return jsonOrThrow<SessionUser>(res, "회원가입에 실패했습니다.");
}

/** 쿠키 세션 갱신(리프레시 회전) — 성공 시 새 쿠키가 응답에 실려 온다. */
export async function tryRefreshSession(): Promise<boolean> {
  try {
    const res = await authFetch("/refresh", { method: "POST" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function apiLogout(): Promise<void> {
  try {
    await authFetch("/logout", { method: "POST" });
  } catch {
    // 로그아웃은 베스트 에포트 — 쿠키 삭제가 실패해도 UI 상태는 정리된다
  }
}

/** 로그인 상태 판정의 단일 소스 — 쿠키가 유효하면 사용자 정보를 준다. */
// emailVerified — 알림 메일은 인증된 주소로만 나간다(가입·로그인과는 무관). 구버전 응답 호환을 위해 옵셔널
export async function apiMe(): Promise<{ id: number; email: string; name: string; emailVerified?: boolean }> {
  const res = await authFetch("/me");
  if (!res.ok) throw new Error("인증이 만료되었습니다.");
  return res.json();
}

/** 로그인한 본인 주소로 인증 메일을 보낸다. 실패 사유(하루 한도·발송 불가 주소 등)는 서버 문구를 그대로 던진다. */
export async function apiRequestEmailVerification(): Promise<{ outcome: string; message: string }> {
  const res = await authFetch("/email/verify-request", { method: "POST" });
  return jsonOrThrow(res, "인증 메일을 보내지 못했어요.");
}

/** 메일 링크의 토큰 확인 — 로그인 없이도 된다(토큰이 주소 소유를 증명한다). */
export async function apiVerifyEmail(token: string): Promise<{ verified: boolean }> {
  const res = await authFetch("/email/verify", { method: "POST", body: JSON.stringify({ token }) });
  return jsonOrThrow(res, "링크를 확인하지 못했어요.");
}

/** 보이는 탭 키 목록 — 등급(역할) 합집합. 비로그인은 기본 등급 구성. */
export async function apiTabs(): Promise<{ tabs: string[] }> {
  const res = await authFetch("/tabs");
  if (!res.ok) throw new Error("탭 구성을 불러오지 못했습니다.");
  return res.json();
}

/** 동의 대기 프로필 — 소셜 콜백이 심은 consent 쿠키 기준. 대기 상태 아니면 throw. */
export async function apiConsentPending(): Promise<{ provider: string; name: string; email: string }> {
  const res = await authFetch("/social/consent/pending");
  return jsonOrThrow(res, "동의 대기 정보를 불러오지 못했습니다.");
}

/** 신규 소셜 유저의 약관 동의 완료 — consent 쿠키로 가입되고 세션 쿠키가 발급된다. */
export async function apiSocialConsent(marketingAgreed: boolean): Promise<SessionUser> {
  const res = await authFetch("/social/consent", {
    method: "POST",
    body: JSON.stringify({ marketing_agreed: marketingAgreed }),
  });
  return jsonOrThrow<SessionUser>(res, "약관 동의 처리에 실패했습니다.");
}
