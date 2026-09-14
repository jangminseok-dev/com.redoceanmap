import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/shell/AppShell";
import AuthModal from "@/components/seoul/AuthModal";
import AuthProvider from "@/components/seoul/AuthProvider";
import Providers from "./providers";
import { SITE_URL } from "@/lib/siteUrl";


const TITLE = "redoceanmap — 상권·주식 분석";
const DESCRIPTION = "서울 어디에 창업할지, 이 주식이 지금 어떤지 — 공공데이터·주가·뉴스를 근거로 답합니다. AI 모의투자 기록도 봅니다.";

export const metadata: Metadata = {
  // 링크를 공유했을 때 미리보기가 뜨게 한다. images는 public/og.png(1200×630)를
  // 만든 뒤에 붙인다 — 자산 없이 넣으면 깨진 카드가 뜬다.
  metadataBase: new URL(SITE_URL),
  title: TITLE,
  description: DESCRIPTION,
  openGraph: {
    type: "website",
    locale: "ko_KR",
    siteName: "redoceanmap",
    title: TITLE,
    description: DESCRIPTION,
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // suppressHydrationWarning — 아래 인라인 스크립트가 hydration 전에 data-theme을 심어
    // 서버 HTML(속성 없음)과 어긋난다. 의도된 어긋남이므로 경고만 끈다(html 한 단계에만 적용).
    <html lang="ko" className="h-full antialiased" suppressHydrationWarning>
      <head>
        {/* FOUC 방지 — 첫 페인트 전에 저장된 테마(없으면 시스템 선호)를 적용한다.
            React 밖에서 실행돼야 하므로 인라인 스크립트다. 키는 lib/uiStore.ts THEME_KEY와 동일. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("rom-theme");if(t!=="dark"&&t!=="light"){t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}document.documentElement.dataset.theme=t}catch(e){}})()`,
          }}
        />
      </head>
      <body className="min-h-full">
        <Providers>
          <AuthProvider />
          {/* AppShell이 h-dvh를 잡고 레일/하단탭을 그린다. 어드민·/rom은 자체 셸이라 그대로 통과시킨다. */}
          <AppShell>
            {/* 셸이 h-dvh를 잡으므로 페이지 스크롤은 여기서 난다. 홈·게임처럼 자연 높이로 긴
                페이지가 잘리지 않게 하는 자리다. 스스로 높이를 관리하는 화면(워크스페이스·/rom)은
                루트에 `h-full`을 두어 이 컨테이너를 넘기지 않는다. */}
            <main className="flex-1 min-h-0 overflow-y-auto flex flex-col">{children}</main>
          </AppShell>
          <AuthModal />
        </Providers>
      </body>
    </html>
  );
}
