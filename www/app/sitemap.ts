import type { MetadataRoute } from "next";
import { fetchAreaIndex } from "@/lib/publicApi.server";

import { SITE_URL as SITE } from "@/lib/siteUrl";

// 공개 상권 상세 1,650건 + 홈. 인덱스는 하루 캐시(ISR)라 분기 적재 뒤 하루 안에 따라온다.
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // 빌드 서버에서 백엔드 공개 API에 못 닿으면(방화벽·챌린지·일시 장애) 빌드 전체가 실패했다 —
  // 2026-09-15 11:32부터 Vercel 프로덕션 배포가 전부 실패(로컬 빌드는 성공). 인덱스를 못 받으면 홈만 싣고,
  // ISR(하루)로 다음 재생성 때 상권 URL이 채워진다.
  const rows = await fetchAreaIndex().catch((err: unknown) => {
    console.error("[sitemap] 상권 인덱스 조회 실패 — 홈만 싣는다", err);
    return [];
  });
  return [
    { url: `${SITE}/`, changeFrequency: "weekly", priority: 1 },
    ...rows.map((r) => ({
      url: `${SITE}/areas/${r.trdarCode}`,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    })),
  ];
}
