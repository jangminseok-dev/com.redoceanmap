"use client";

import { useMemo, useState } from "react";
import { Star } from "lucide-react";
import type { GameSymbolPrices } from "@/lib/types";
import SymbolMark from "@/components/common/SymbolMark";

const ALL = "전체";

// 정렬 축 — 레퍼런스(토스증권 실시간 차트)의 칩과 같은 역할이다.
// **거래대금·거래량·시총 축은 없다**: symbols에 종목별 거래량·시총이 없어(선택 종목에만 있다)
// 지금 만들면 빈 컬럼이 된다. 백엔드가 실어주면 여기에 축을 더한다.
const SORTS = [
  { key: "change", label: "등락률" },
  { key: "gain", label: "급상승" },
  { key: "loss", label: "급하락" },
  { key: "name", label: "이름" },
] as const;

type SortKey = (typeof SORTS)[number]["key"];

const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const tone = (v: number) =>
  v > 0 ? "text-up" : v < 0 ? "text-down" : "text-foreground-muted";
// 등락액 — changePct가 "게임 1일 전 대비"이므로 그 기준가를 역산해 차액을 구한다
const changeAmt = (s: GameSymbolPrices) =>
  s.priceKrw - Math.round(s.priceKrw / (1 + s.changePct / 100));

/**
 * 종목 표 — 이 화면의 주인공(레퍼런스 토스증권 홈의 좌측 표).
 * 컬럼: 순위 · 마크 · 종목 · 현재가 · 등락액 · 등락률 · 산업.
 * 등락은 토스 표와 같게 **색 텍스트**로만 말한다(배경 하이라이트는 히어로 전용 — 표 전체에
 * 깔면 화면이 색면으로 뒤덮여 오히려 아무것도 두드러지지 않는다).
 */
export default function GameSymbolTable({
  symbols,
  selected,
  favorites,
  onSelect,
  onToggleFavorite,
}: {
  symbols: GameSymbolPrices[];
  selected: string | null;
  favorites: string[];
  onSelect: (symbol: string) => void;
  onToggleFavorite: (symbol: string) => void;
}) {
  // 필터·정렬은 함께 바뀌는 한 축이라 단일 객체로 둔다(REACT_RULES 패턴 B)
  const [view, setView] = useState<{ group: string; sort: SortKey; onlyFavorites: boolean }>({
    group: ALL,
    sort: "change",
    onlyFavorites: false,
  });

  // 섹터 그룹은 도메인이 정한 축이다 — 프론트가 목록을 지어내지 않는다
  const groups = useMemo(
    () => [ALL, ...Array.from(new Set(symbols.map((s) => s.sectorGroup)))],
    [symbols],
  );

  const rows = useMemo(() => {
    let list = symbols;
    if (view.onlyFavorites) list = list.filter((s) => favorites.includes(s.symbol));
    if (view.group !== ALL) list = list.filter((s) => s.sectorGroup === view.group);
    const sorted = [...list];
    if (view.sort === "name") sorted.sort((a, b) => a.name.localeCompare(b.name, "ko"));
    else if (view.sort === "loss") sorted.sort((a, b) => a.changePct - b.changePct);
    // change와 gain은 같은 내림차순이다 — 칩을 나눠 둔 것은 사용자가 무엇을 찾는지 말하게 하려는 것
    else sorted.sort((a, b) => b.changePct - a.changePct);
    return sorted;
  }, [symbols, favorites, view]);

  return (
    <section className="h-full min-h-0 flex flex-col rounded-2xl border border-border bg-surface overflow-hidden">
      {/* 칩은 각각 **한 줄**로 두고 넘치면 옆으로 민다 — wrap이면 필터가 목록 높이를 먹는다 */}
      <div className={CHIP_ROW}>
        <Chip
          active={view.onlyFavorites}
          onClick={() => setView((p) => ({ ...p, onlyFavorites: !p.onlyFavorites }))}
        >
          <Star size={11} strokeWidth={2.4} className={view.onlyFavorites ? "fill-current" : ""} />
          관심
        </Chip>
        <span className="mx-0.5 h-4 w-px bg-border shrink-0" aria-hidden />
        {SORTS.map((s) => (
          <Chip key={s.key} active={view.sort === s.key} onClick={() => setView((p) => ({ ...p, sort: s.key }))}>
            {s.label}
          </Chip>
        ))}
      </div>

      <div className={`${CHIP_ROW} pb-2.5`}>
        {groups.map((g) => (
          <Chip key={g} active={view.group === g} onClick={() => setView((p) => ({ ...p, group: g }))}>
            {g}
          </Chip>
        ))}
      </div>

      <div className="flex items-center gap-2.5 px-3 pb-1.5 text-xs text-foreground-muted border-b border-border">
        <span className="w-5 shrink-0">#</span>
        <span className="w-6 shrink-0" />
        <span className="flex-1">종목</span>
        <span className="w-24 shrink-0 text-right">현재가</span>
        <span className="hidden md:block w-20 shrink-0 text-right">등락액</span>
        <span className="w-[74px] shrink-0 text-right">등락률</span>
        <span className="hidden lg:block w-24 shrink-0 text-center">산업</span>
      </div>

      <ul className="flex-1 min-h-0 overflow-y-auto">
        {rows.map((s, i) => {
          const active = s.symbol === selected;
          const fav = favorites.includes(s.symbol);
          const amt = changeAmt(s);
          return (
            <li key={s.symbol}>
              <div
                className={`group flex items-center gap-2.5 px-3 py-2 border-b border-border transition-colors ${
                  active ? "bg-accent" : "hover:bg-accent"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onToggleFavorite(s.symbol)}
                  aria-label={fav ? `${s.name} 관심 해제` : `${s.name} 관심 등록`}
                  aria-pressed={fav}
                  className="w-5 shrink-0 grid place-items-center text-foreground-muted hover:text-brand transition-colors"
                >
                  {fav ? (
                    <Star size={13} strokeWidth={2.2} className="fill-brand text-brand" />
                  ) : (
                    <span className="text-xs tabular-nums group-hover:hidden">{i + 1}</span>
                  )}
                  {!fav && <Star size={13} strokeWidth={2.2} className="hidden group-hover:block" />}
                </button>

                <button
                  type="button"
                  onClick={() => onSelect(s.symbol)}
                  aria-current={active}
                  className="flex-1 min-w-0 flex items-center gap-2.5 text-left"
                >
                  <SymbolMark name={s.name} />
                  <span className="min-w-0 flex-1 flex items-center gap-1.5">
                    <span className="text-sm font-medium truncate">{s.name}</span>
                    {/* 밈 종목은 변동성이 다른 종목의 2배 이상이다 — 목록에서 바로 보이게 */}
                    {s.meme && (
                      <span className="shrink-0 rounded-md px-1 py-px text-xs font-bold bg-up/10 text-up">
                        밈
                      </span>
                    )}
                  </span>

                  <span className="w-24 shrink-0 text-right text-sm font-medium tabular-nums">
                    {s.priceKrw.toLocaleString()}원
                  </span>
                  <span
                    className={`hidden md:block w-20 shrink-0 text-right text-sm tabular-nums ${tone(amt)}`}
                  >
                    {amt >= 0 ? "+" : ""}
                    {amt.toLocaleString()}원
                  </span>
                  <span
                    className={`w-[74px] shrink-0 text-right text-sm font-medium tabular-nums ${tone(s.changePct)}`}
                  >
                    {signed(s.changePct)}
                  </span>
                  {/* 산업 태그 — 토스 표의 카테고리 칩 자리. 액션이 아니라 정보라 뱃지 형태다 */}
                  <span className="hidden lg:flex w-24 shrink-0 justify-center">
                    <span className="max-w-full truncate rounded-md bg-accent px-1.5 py-0.5 text-xs text-foreground-muted">
                      {s.sector}
                    </span>
                  </span>
                </button>
              </div>
            </li>
          );
        })}

        {rows.length === 0 && (
          <li className="px-3 py-8 text-center text-sm text-foreground-muted">
            {view.onlyFavorites
              ? "관심 종목이 없습니다. 목록에서 별을 눌러 담아보세요."
              : "조건에 맞는 종목이 없습니다."}
          </li>
        )}
      </ul>
    </section>
  );
}

// 칩 한 줄 — 넘치면 가로로 밀린다. 스크롤바는 숨긴다(칩이 잘려 보이는 것이 스크롤 힌트다)
const CHIP_ROW =
  "shrink-0 flex items-center gap-1.5 px-3 pt-3 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden";

// 낮은 위계 요소라 알약을 쓴다 — Button 스케일과 섞지 않는다(DESIGN.md §5)
function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`shrink-0 inline-flex items-center gap-1 h-7 px-2.5 rounded-full text-xs font-medium transition-colors duration-150 ${
        active
          ? "bg-brand text-white"
          : "border border-border text-foreground-muted hover:bg-accent hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}
