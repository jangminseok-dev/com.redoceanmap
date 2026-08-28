import type { NextConfig } from "next";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
// 인증 전용 컨테이너(auth_main, /auth/*) — 발급은 분리 배포된 auth가 담당한다.
const AUTH_BASE = process.env.NEXT_PUBLIC_AUTH_URL ?? "http://127.0.0.1:9000";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  // 백엔드 GET 조회 프록시 — 엔드포인트마다 route.ts를 만들지 않는다.
  // (POST /api/chat은 에러 메시지 가공이 있어 기존 route.ts 유지)
  async rewrites() {
    return [
      // 구체 규칙이 일반 규칙보다 앞 — /auth/*만 인증 컨테이너로 분기
      {
        source: "/api/backend/auth/:path*",
        destination: `${AUTH_BASE}/auth/:path*`,
      },
      {
        source: "/api/backend/:path*",
        destination: `${API_BASE}/:path*`,
      },
    ];
  },
  // 구 지도 페이지 → 상권 워크스페이스
  // 구 소개 페이지 → 블로그로 이관(2026-08-28). permanent를 켜면 브라우저가 영구 캐시해
  // 되돌리기 어려워지므로 /map과 같이 임시로 둔다.
  async redirects() {
    return [
      { source: "/map", destination: "/market", permanent: false },
      {
        source: "/about",
        destination: "https://blog.redoceanmap.com/about/",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
