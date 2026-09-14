import type { AreaIndexRow, AreaPublic } from "@/lib/types";

/**
 * 서버 컴포넌트 전용 백엔드 조회 — 공개(비로그인) 경로만 다룬다.
 *
 * 브라우저 fetch는 절대 URL 금지(/api/backend rewrite 경유)이지만, 이 파일은 Next 서버에서만
 * 실행된다(page.tsx 서버 컴포넌트·sitemap.ts). rewrite는 브라우저 요청에만 걸리므로 서버는
 * next.config가 쓰는 같은 env(NEXT_PUBLIC_API_URL)로 백엔드에 직접 간다. 클라이언트 컴포넌트에서
 * import하면 안 된다 — 그쪽은 lib/api.ts.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// 분기 데이터라 하루 캐시(ISR). 백엔드도 같은 값의 Cache-Control을 낸다.
const REVALIDATE_SECONDS = 86400;

export async function fetchAreaPublic(trdarCode: string): Promise<AreaPublic | null> {
  const res = await fetch(`${API_BASE}/market/areas/${encodeURIComponent(trdarCode)}/public`, {
    next: { revalidate: REVALIDATE_SECONDS },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`공개 상권 조회 실패: ${res.status}`);
  return res.json();
}

export async function fetchAreaIndex(): Promise<AreaIndexRow[]> {
  const res = await fetch(`${API_BASE}/market/areas/public-index`, {
    next: { revalidate: REVALIDATE_SECONDS },
  });
  if (!res.ok) throw new Error(`상권 인덱스 조회 실패: ${res.status}`);
  const body: { rows: AreaIndexRow[] } = await res.json();
  return body.rows;
}
