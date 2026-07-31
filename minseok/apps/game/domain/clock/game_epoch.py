"""게임 시계 — 에포크 상수와 틱 변환.

game-harness §1-1의 고정 상수가 사는 **유일한 파일**이다. 이 파일 밖에서 시간 리터럴을 쓰지 않는다.
현재 시각(`datetime.now`)은 여기서도 읽지 않는다 — 어댑터가 시각을 틱으로 바꿔 넣는다.
게임 상태는 저장된 값이 아니라 시각의 함수이며(§1-A), 그 시각의 단위가 틱이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

# --- 시즌 식별 ---------------------------------------------------------------
# 계수·모델을 바꾸면 반드시 올린다(§1-4). 올리지 않으면 과거 전 구간이 소급 변조된다.
GAME_EPOCH_ID = 1
RULES_VERSION = "v1"

# 시즌 1 시작 — 2026-07-31 17:00 KST(실배포 시각). 확정 후 불변이다.
#
# 원래 09:00 KST로 박혀 있었는데 그대로 배포하면 게임이 7일차(현실 1시간 = 게임 1일)부터
# 시작한다 — 아무도 플레이하지 않은 과거가 이미 지나간 상태가 된다. 배포 시각으로 옮겼다.
GAME_EPOCH_START_UTC = datetime(2026, 7, 31, 8, 0, 0, tzinfo=timezone.utc)

# --- 시간 축 -----------------------------------------------------------------
TICK_SECONDS = 60           # 프론트 폴링 하한과 정합
TICKS_PER_GAME_DAY = 60     # 실제 1시간 = 게임 1일
GAME_DAYS_PER_QUARTER = 90  # 게임 1분기 = 현실 90시간 = 3.75일
QUARTERS_PER_SEASON = 8     # 1시즌 = 현실 약 30일
SEASON_TICKS = TICKS_PER_GAME_DAY * GAME_DAYS_PER_QUARTER * QUARTERS_PER_SEASON  # 43_200

# 게임이 읽는 상권 실데이터 분기 — 에포크에 박는다(§1-5).
# market이 새 분기를 적재해도 진행 중인 시즌의 기준선은 바뀌지 않는다.
DATA_QUARTER = 20254


def tick_at(now: datetime) -> int:
    """UTC 시각 → 틱 번호. 에포크 이전이면 0.

    naive datetime은 받지 않는다 — 로컬 시각을 UTC로 오인하면 게임 시각이 9시간 어긋난다.
    """
    if now.tzinfo is None:
        raise ValueError("tzinfo 없는 naive datetime은 받지 않는다")
    elapsed = (now - GAME_EPOCH_START_UTC).total_seconds()
    if elapsed < 0:
        return 0
    return int(elapsed // TICK_SECONDS)


@dataclass(frozen=True)
class GameTime:
    """틱을 게임 달력으로 푼 값."""

    tick: int
    game_day: int          # 0부터
    game_quarter: int      # 1..8
    day_of_quarter: int    # 1..90
    season_over: bool
    ticks_remaining: int   # 시즌 종료까지, 종료 후 0


def describe(tick: int) -> GameTime:
    """틱 → 게임 달력. 시즌을 넘긴 틱은 마지막 분기 마지막 날로 고정한다."""
    capped = min(max(tick, 0), SEASON_TICKS - 1)
    game_day = capped // TICKS_PER_GAME_DAY
    quarter_index = min(game_day // GAME_DAYS_PER_QUARTER, QUARTERS_PER_SEASON - 1)
    return GameTime(
        tick=tick,
        game_day=game_day,
        game_quarter=quarter_index + 1,
        day_of_quarter=game_day - quarter_index * GAME_DAYS_PER_QUARTER + 1,
        season_over=tick >= SEASON_TICKS,
        ticks_remaining=max(SEASON_TICKS - tick, 0),
    )
