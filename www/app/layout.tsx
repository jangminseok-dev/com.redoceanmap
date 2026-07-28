import type { Metadata } from "next";
import "./globals.css";
import TopNav from "@/components/seoul/TopNav";
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
      <body className="min-h-full flex flex-col">
        <Providers>
          <AuthProvider />
          <TopNav />
          <main className="flex-1 flex flex-col min-h-0">{children}</main>
          <AuthModal />
        </Providers>
      </body>
    </html>
  );
}
