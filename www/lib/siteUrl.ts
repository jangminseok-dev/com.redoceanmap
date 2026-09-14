// 사이트 공개 주소 — sitemap·robots·metadataBase가 공유한다.
// NEXT_PUBLIC_SITE_URL 이 우선. 없으면 Vercel이 빌드마다 자동 주입하는 프로덕션 도메인
// (VERCEL_PROJECT_PRODUCTION_URL, 스킴 없음)으로 폴백해 실배포에서 127.0.0.1 이 새지 않게 한다.
const vercelProd = process.env.VERCEL_PROJECT_PRODUCTION_URL;

export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (vercelProd ? `https://${vercelProd}` : "http://127.0.0.1:3000");
