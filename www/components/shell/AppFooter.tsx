import Link from "next/link";

/**
 * 문서형 페이지 하단 푸터 — 소개·정책으로 나가는 자리.
 *
 * **전역 푸터로 쓰지 않는다.** 이 서비스는 앱 셸(데스크탑 레일 · 모바일 하단탭)이 상시
 * 내비게이션을 이미 담당하고, 홈·북마크처럼 화면을 꽉 채우는 페이지(`flex-1` / `h-full`)에
 * 붙이면 없던 스크롤이 생긴다. 특히 홈은 "물어보는 자리 하나만 둔다"(2026-08-16 리뉴얼)가
 * 명시된 화면이다. 자연 높이로 흐르는 문서 페이지(처리방침·약관)에서만 쓴다.
 *
 * 전 화면에서 닿아야 하는 정책 링크는 AppShell "더보기" 시트가 담당한다 — 그전까지는
 * 회원가입 동의 체크박스가 유일한 진입로라 이미 가입한 사용자는 도달할 방법이 없었다.
 *
 * 메일 주소는 여기에 두지 않는다. 법이 요구하는 연락처는 처리방침 8항에 있고,
 * 같은 주소를 자리마다 평문으로 늘리면 수집만 늘고 얻는 게 없다.
 */
export default function AppFooter() {
  return (
    <footer className="mt-16 border-t border-border pt-6 pb-10 text-xs text-foreground-muted">
      <nav className="flex flex-wrap items-center gap-x-4 gap-y-2" aria-label="소개 및 정책">
        <Link href="/about" className="hover:text-foreground transition-colors">
          서비스 소개
        </Link>
        <Link href="/privacy" className="hover:text-foreground transition-colors">
          개인정보처리방침
        </Link>
        <Link href="/terms" className="hover:text-foreground transition-colors">
          이용약관
        </Link>
      </nav>
      <p className="mt-3 leading-relaxed">
        상권 데이터는 서울 열린데이터광장·국토교통부 공공데이터를 사용합니다. 분석 결과는 참고
        자료이며 투자·창업 판단은 본인 책임입니다.
      </p>
    </footer>
  );
}
