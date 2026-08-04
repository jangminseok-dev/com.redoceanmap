"use client";

import { useMemo, useState } from "react";
import { Star } from "lucide-react";
import type { GameSymbolPrices } from "@/lib/types";
import SymbolMark from "@/components/common/SymbolMark";
import GamePriceLine from "./GamePriceLine";

const ALL = "전체";

// 정렬 축 — 레퍼런스(토스증권 실시간 차트)의 칩과 같은 역할이다.
// **거래대금·거래량 축은 없다**: 게임 응답의 symbols에 종목별 거래량이 없어(선택 종목의 봉에만 있다)
// 지금 만들면 빈 컬럼이 된다. 백엔드가 실어주면 여기에 축을 더한다.
const SORTS = [
  { key: "change", label: "등락률" },
  { key: "gain", label: "급상승" },
  { key: "loss", label: "급하락" },
  { key: "name", label: "이름" },
] as const;

type SortKey = (typeof SORTS)[number]["key"];

const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const toneOf = (v: number) => (v >= 0 ? "text-up" : "text-down");
// 등락률 배경 하이라이트 — 값보다 방향이 먼저 읽힌다(DESIGN.md §2)
const toneBox = (v: number) =>
  v > 0 ? "bg-up-weak text-up" : v < 0 ? "bg-down-weak text-down" : "text-foreground-muted";

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
    <section className="rounded-2xl border border-border bg-surface overflow-hidden">
      <div className="flex flex-wrap items-center gap-1.5 px-3 pt-3 pb-2">
        <Chip active={view.onlyFavorites} onClick={() => setView((p) => ({ ...p, onlyFavorites: !p.onlyFavorites }))}>
          <Star size={11} strokeWidth={2.4} className={view.onlyFavorites ? "fill-current" : ""} />
          관심
        </Chip>
        <span className="mx-0.5 h-4 w-px bg-border" aria-hidden />
        {SORTS.map((s) => (
          <Chip key={s.key} active={view.sort === s.key} onClick={() => setView((p) => ({ ...p, sort: s.key }))}>
            {s.label}
          </Chip>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-1.5 px-3 pb-2.5">
        {groups.map((g) => (
          <Chip key={g} active={view.group === g} onClick={() => setView((p) => ({ ...p, group: g }))}>
            {g}
          </Chip>
        ))}
      </div>

      {/* 컬럼 라벨 — 좁은 폭에서는 열이 접혀 라벨이 값과 어긋나므로 감춘다 */}
      <div className="hidden sm:flex items-center gap-2.5 px-3 pb-1.5 text-xs text-foreground-muted border-b border-border">
        <span className="w-5 shrink-0">#</span>
        <span className="w-6 shrink-0" />
        <span className="flex-1">종목</span>
        <span className="w-12 shrink-0" />
        <span className="w-20 shrink-0 text-right">현재가</span>
        <span className="w-[68px] shrink-0 text-right">등락률</span>
      </div>

      <ul className="max-h-[520px] overflow-y-auto">
        {rows.map((s, i) => {
          const active = s.symbol === selected;
          const fav = favorites.includes(s.symbol);
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
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5">
                      <span className="text-sm font-medium truncate">{s.name}</span>
                      {/* 밈 종목은 변동성이 다른 종목의 2배 이상이다 — 목록에서 바로 보이게 */}
                      {s.meme && (
                        <span className="shrink-0 rounded-md px-1 py-px text-xs font-bold bg-up/10 text-up">
                          밈
                        </span>
                      )}
                    </span>
                    <span className="block text-xs text-foreground-muted truncate">{s.sector}</span>
                  </span>

                  <GamePriceLine points={s.series} compact className="hidden sm:block w-12 h-6 shrink-0" />

                  <span className="w-20 shrink-0 text-right text-sm font-medium tabular-nums">
                    {s.priceKrw.toLocaleString()}
                  </span>
                  <span
                    className={`w-[68px] shrink-0 text-right text-sm font-medium tabular-nums px-1.5 py-0.5 rounded-md ${toneBox(s.changePct)}`}
                  >
                    {signed(s.changePct)}
                  </span>
                </button>
              </div>
            </li>
          );
        })}

        {rows.length === 0 && (
          <li className="px-3 py-8 text-center text-sm text-foreground-muted">
            {view.onlyFavorites ? "관심 종목이 없습니다. 목록에서 별을 눌러 담아보세요." : "조건에 맞는 종목이 없습니다."}
          </li>
        )}
      </ul>
    </section>
  );
}

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
      className={`inline-flex items-center gap-1 h-7 px-2.5 rounded-full text-xs font-medium transition-colors duration-150 ${
        active
          ? "bg-brand text-white"
          : "border border-border text-foreground-muted hover:bg-accent hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

export { toneOf };
