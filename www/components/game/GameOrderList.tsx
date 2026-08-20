"use client";

import type { GameLimitOrder } from "@/lib/types";

type Props = {
  pending: GameLimitOrder[];
  recent: GameLimitOrder[];
  currentTick: number;
  ticksPerGameDay: number;
  busyId: number | null;
  onCancel: (orderId: number) => void;
  onExtend: (orderId: number) => void;
};

const won = (v: number) => `${v.toLocaleString()}원`;

// 백엔드 limit_order_schema.py의 status와 같은 축 — 값이 늘면 여기도 늘린다
const STATUS_LABEL: Record<GameLimitOrder["status"], string> = {
  pending: "대기",
  filled: "체결",
  cancelled: "취소",
  expired: "만료",
};

const STATUS_TONE: Record<GameLimitOrder["status"], string> = {
  pending: "text-foreground-muted",
  filled: "text-brand",
  cancelled: "text-foreground-muted",
  expired: "text-amber-700",
};

/**
 * 예약 주문 목록.
 *
 * 진입(ENTRY)과 청산(EXIT, 익절·손절)이 한 목록에 섞인다 — 백엔드가 한 테이블로 다루고,
 * 유저에게도 "지금 걸려 있는 예약"은 하나의 관심사다.
 *
 * 만료를 노출하는 이유: 만료는 없앨 수 없다(체결 판정 시 훑을 틱 범위를 묶는 성능 장치).
 * 대신 연장 버튼을 반드시 둔다 — game-harness §2가 "만료되고 포기 불가능한 것"을 금지한다.
 */
export default function GameOrderList({
  pending,
  recent,
  currentTick,
  ticksPerGameDay,
  busyId,
  onCancel,
  onExtend,
}: Props) {
  if (pending.length === 0 && recent.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-surface p-8 text-center">
        <p className="text-sm text-foreground-muted">걸어둔 예약 주문이 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <ul className="space-y-2">
        {pending.map((o) => {
          const isLong = o.side === "LONG";
          const isExit = o.kind === "EXIT";
          // 익절·손절 구분은 trigger로 판정한다 — 롱 포지션은 ge가 익절, le가 손절이고
          // 숏 포지션은 반대다(백엔드 limit_fill.py와 같은 규칙).
          const exitLabel = isExit ? ((isLong ? o.trigger === "ge" : o.trigger === "le") ? "익절" : "손절") : null;
          const daysLeft = Math.max(0, Math.ceil((o.expiresTick - currentTick) / ticksPerGameDay));
          return (
            <li
              key={o.id}
              className="rounded-2xl border border-border bg-surface p-4 flex flex-wrap items-center gap-x-4 gap-y-2"
            >
              <span
                className={`px-2 py-0.5 rounded-md text-xs font-bold text-white ${
                  isExit ? "bg-foreground-muted" : isLong ? "bg-up" : "bg-down"
                }`}
              >
                {exitLabel ?? (isLong ? "롱" : "숏")}
                {!isExit && o.leverage > 1 && ` ${o.leverage}배`}
              </span>

              <span className="min-w-0">
                <span className="block text-sm font-semibold truncate">{o.name}</span>
                <span className="block text-xs text-foreground-muted tabular-nums">
                  {o.quantity.toLocaleString()}주 · {won(o.limitPriceKrw)}{" "}
                  {o.trigger === "le" ? "이하" : "이상"}에 체결
                </span>
              </span>

              <span className="ml-auto text-right">
                <span className="block text-xs text-foreground-muted tabular-nums">
                  게임 {daysLeft}일 뒤 만료
                </span>
                {o.reservedCashKrw > 0 && (
                  <span className="block text-xs text-foreground-muted tabular-nums">
                    {won(o.reservedCashKrw)} 묶임
                  </span>
                )}
              </span>

              <span className="flex gap-1.5">
                <button
                  type="button"
                  onClick={() => onExtend(o.id)}
                  disabled={busyId !== null}
                  className="px-3 h-10 rounded-xl border border-border text-xs font-medium hover:bg-accent disabled:opacity-40 transition-colors"
                >
                  연장
                </button>
                <button
                  type="button"
                  onClick={() => onCancel(o.id)}
                  disabled={busyId !== null}
                  className="px-3 h-10 rounded-xl border border-border text-xs font-medium hover:bg-accent disabled:opacity-40 transition-colors"
                >
                  {busyId === o.id ? "처리 중…" : "취소"}
                </button>
              </span>
            </li>
          );
        })}
      </ul>

      {recent.length > 0 && (
        <ul className="space-y-1 pt-1">
          {recent.map((o) => (
            <li
              key={o.id}
              className="flex items-baseline gap-2 px-1 text-xs text-foreground-muted tabular-nums"
            >
              <span className={`font-medium ${STATUS_TONE[o.status]}`}>{STATUS_LABEL[o.status]}</span>
              <span className="truncate">{o.name}</span>
              <span>
                {o.quantity.toLocaleString()}주 ·{" "}
                {o.filledPriceKrw !== null ? won(o.filledPriceKrw) : won(o.limitPriceKrw)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
