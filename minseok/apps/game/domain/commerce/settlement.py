"""분기 결산 — 밀린 분기를 순서대로 확정한다 (game-strategy §4-7).

**지연 실행이다.** cron도 스케줄러도 없이, 유저가 조회할 때 밀린 분기를 계산해 확정한다
(game-harness §2 — game의 cron 목표 개수는 0). 며칠 접속하지 않아도 분기는 밀려 있다가
한 번에 정산되고, 그 결과는 순차 정산과 같아야 한다.

일별 매출은 저장하지 않으므로 결산도 재계산이다. 다만 **결산 자체는 저장한다** —
분기 손익이 지갑에 반영되는 것은 캐시가 아니라 게임 규칙상 실재하는 사건이기 때문이다
(game-harness §4-2).
"""
from __future__ import annotations

from dataclasses import dataclass

from game.domain.clock.game_epoch import GAME_DAYS_PER_QUARTER, QUARTERS_PER_SEASON


@dataclass(frozen=True)
class QuarterWindow:
    """정산 대상 분기 한 구간."""

    game_quarter: int  # 1..8
    start_day: int
    end_day: int

    @property
    def days(self) -> int:
        return self.end_day - self.start_day + 1


def quarter_of(game_day: int) -> int:
    """게임일이 속한 분기(1부터)."""
    return game_day // GAME_DAYS_PER_QUARTER + 1


def pending_quarters(
    *, opened_game_day: int, settled_through_day: int, today: int, closed_game_day: int | None
) -> tuple[QuarterWindow, ...]:
    """아직 정산되지 않은 **완료된** 분기들.

    진행 중인 분기는 넣지 않는다 — 분기가 끝나야 결산이다. 창업일이 분기 중간이면
    그 분기는 남은 날짜만 센다.
    """
    # settled_through_day의 초기값은 0이라 "0일차까지 정산됨"과 "미정산"이 겹친다.
    # 창업일 직전을 하한으로 두어 그 모호함을 없앤다.
    cursor = max(settled_through_day, opened_game_day - 1)
    last_active = today if closed_game_day is None else min(today, closed_game_day)

    windows: list[QuarterWindow] = []
    index = max(cursor + 1, opened_game_day) // GAME_DAYS_PER_QUARTER
    while index < QUARTERS_PER_SEASON:
        start = max(opened_game_day, index * GAME_DAYS_PER_QUARTER, cursor + 1)
        end = (index + 1) * GAME_DAYS_PER_QUARTER - 1
        if end > last_active:  # 아직 끝나지 않은 분기
            break
        if start <= end:
            windows.append(QuarterWindow(game_quarter=index + 1, start_day=start, end_day=end))
        index += 1
    return tuple(windows)


@dataclass(frozen=True)
class SettlementAdvice:
    tone: str  # good | warn | bad
    message: str


def advise(
    *,
    profit_krw: int,
    average_turned_away_ratio: float,
    performance_ratio: float,
    fitness: float,
) -> tuple[SettlementAdvice, ...]:
    """다음 분기 조언. 템플릿 룩업이며 LLM을 쓰지 않는다(결정론 위반 + 추론 비용).

    `performance_ratio` — 내 매출 ÷ 상권 평균 점포가 같은 규모였을 때의 매출.
    1.0이면 평균만큼 판 것이다.
    """
    out: list[SettlementAdvice] = []

    if average_turned_away_ratio >= 0.2:
        out.append(
            SettlementAdvice(
                "bad",
                f"손님의 {average_turned_away_ratio:.0%}가 자리가 없어 돌아갔습니다. "
                "시설을 늘리면 같은 상권에서 더 받을 수 있습니다.",
            )
        )

    if profit_krw < 0:
        if fitness < 0.9:
            out.append(
                SettlementAdvice(
                    "bad",
                    "적자입니다. 입지와 업종이 서로 맞지 않습니다 — "
                    "폐업하고 적합도가 높은 조합으로 옮기는 편이 낫습니다.",
                )
            )
        else:
            out.append(
                SettlementAdvice(
                    "warn",
                    "적자입니다. 입지는 나쁘지 않으니 고정비(직원·시설)를 줄이거나 "
                    "인지도가 오를 때까지 버티는 선택지가 있습니다.",
                )
            )
    elif performance_ratio >= 1.0:
        out.append(
            SettlementAdvice(
                "good",
                f"상권 평균 점포의 {performance_ratio:.1f}배를 팔았습니다. "
                "규모를 키울 여지가 있습니다.",
            )
        )
    else:
        out.append(
            SettlementAdvice(
                "warn",
                f"흑자지만 상권 평균의 {performance_ratio:.0%} 수준입니다. "
                "가격이나 시설을 조정해 볼 수 있습니다.",
            )
        )

    if 0 < average_turned_away_ratio < 0.05 and profit_krw > 0:
        out.append(
            SettlementAdvice(
                "good", "자리가 남습니다. 지금 규모로는 손님을 놓치지 않고 있습니다."
            )
        )

    return tuple(out[:3])
