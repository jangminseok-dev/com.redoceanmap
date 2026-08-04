// 종목 마크 — 목록에서 종목을 눈으로 잡아채는 앵커.
//
// 실제 기업 로고는 쓰지 않는다: 상표 자산이고 우리에게 사용 권한이 없다.
// 레퍼런스(토스증권)도 로고가 없는 종목은 이니셜로 그린다 — 그 방식만 따른다.
//
// 색은 만들지 않는다(DESIGN.md §7). 중립 면 하나로 통일하고, 강조가 필요한 종목만
// 호출부가 `tone`으로 브랜드 면을 고른다 — 종목마다 색을 흩뿌리면 화면이 색으로 시끄러워지고
// 정작 값의 방향(up/down)을 말하는 색과 경쟁한다.
const SIZE = {
  sm: "w-6 h-6 text-[11px]",
  md: "w-8 h-8 text-xs",
} as const;

export default function SymbolMark({
  name,
  tone = "neutral",
  size = "sm",
  className = "",
}: {
  name: string;
  tone?: "neutral" | "brand";
  size?: keyof typeof SIZE;
  className?: string;
}) {
  // 한글은 첫 글자, 영문 티커는 앞 두 글자가 더 잘 구분된다(NVDA·NVDX)
  const initial = /^[A-Za-z]/.test(name) ? name.slice(0, 2).toUpperCase() : name.slice(0, 1);

  return (
    <span
      aria-hidden // 종목명이 바로 옆에 있다 — 보조기술에는 같은 정보를 두 번 읽히지 않는다
      className={`shrink-0 grid place-items-center rounded-full font-bold tabular-nums ${
        SIZE[size]
      } ${tone === "brand" ? "bg-brand text-white" : "bg-accent text-foreground-muted"} ${className}`}
    >
      {initial}
    </span>
  );
}
