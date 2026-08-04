import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/shell/AppShell";
import AuthModal from "@/components/seoul/AuthModal";
import AuthProvider from "@/components/seoul/AuthProvider";
import Providers from "./providers";


const TITLE = "redoceanmap — 서울 상권 분석";
const DESCRIPTION = "예산이랑 업종만 알려주세요. 괜찮은 동네 골라드릴게요.";

export const metadata: Metadata = {
  // 링크를 공유했을 때 미리보기가 뜨게 한다. images는 public/og.png(1200×630)를
  // 만든 뒤에 붙인다 — 자산 없이 넣으면 깨진 카드가 뜬다.
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://127.0.0.1:3000"),
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
    <html lang="ko" className="h-full antialiased">
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
