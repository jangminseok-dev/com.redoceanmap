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
GAME_EPOCH_ID = 2
RULES_VERSION = "v2"

# 시즌 2 — 2026-08-04 09:00 KST. 확정 후 불변이다(21단계, game-strategy §15).
#
# 시즌 1(에포크 1)은 계수 개편으로 닫는다: 종목 12 → 36개(밈 종목 도입) · σ 재배정 ·
# MIN_STORE_SCALE 0.02 → 0.0005 · 이벤트 확률 0.25 → 0.40. 전부 §1-4의 "계수 변경"이라
# 에포크를 유지하면 과거 전 구간이 소급 변조된다. 에포크 1의 지갑·원장은 그대로 남아
# 과거 시즌으로 동결된다(읽기 전용).
#
# 시작 시각은 **가까운 미래 정시**로 잡는다 — 빌드·재기동 전에 지나가면 아무도 플레이하지
# 않은 과거가 이미 흘러간 상태로 열린다(현실 1시간 = 게임 1일). 이 시각 전까지는
# `tick_at`이 0을 돌려주므로 게임은 0틱에 머문다. **배포가 늦어지면 이 값을 다시 민다.**
GAME_EPOCH_START_UTC = datetime(2026, 8, 4, 0, 0, 0, tzinfo=timezone.utc)

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
