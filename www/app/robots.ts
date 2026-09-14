import type { MetadataRoute } from "next";

import { SITE_URL as SITE } from "@/lib/siteUrl";

// 공개 페이지(/areas/{code})만 색인 대상이다. 로그인 뒤 화면과 프록시는 크롤러가 볼 이유가 없다.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/admin", "/profile", "/history", "/bookmarks", "/oauth", "/rom"],
    },
    sitemap: `${SITE}/sitemap.xml`,
  };
}
