import TabGuard from "@/components/seoul/TabGuard";

// 상권 디렉터리는 "상권 분석"의 하위다 — 새 탭 키를 만들지 않는다.
// TAB_KEYS에 키를 추가하면 hub 온톨로지 → auth role_tabs 시드 → admin 등급 화면까지 파급된다.
export default function Layout({ children }: { children: React.ReactNode }) {
  return <TabGuard tab="market">{children}</TabGuard>;
}
