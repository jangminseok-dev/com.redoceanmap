import type { MetadataRoute } from "next";
import { fetchAreaIndex } from "@/lib/publicApi.server";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "http://127.0.0.1:3000";

// 공개 상권 상세 1,650건 + 홈. 인덱스는 하루 캐시(ISR)라 분기 적재 뒤 하루 안에 따라온다.
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const rows = await fetchAreaIndex();
  return [
    { url: `${SITE}/`, changeFrequency: "weekly", priority: 1 },
    ...rows.map((r) => ({
      url: `${SITE}/areas/${r.trdarCode}`,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    })),
  ];
}
