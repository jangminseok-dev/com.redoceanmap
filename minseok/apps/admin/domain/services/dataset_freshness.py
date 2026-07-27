"""데이터셋 신선도 판정 — 순수 도메인 서비스(외부 의존 없음).

"언제부터 지연이고 언제부터 정지인가"는 운영 콘솔의 정책이므로 admin이 소유한다.
데이터를 가진 스포크(market·stock)는 원시 적재 시각만 주고 판정하지 않는다.

배경: 2026-07-25~27 백엔드 PC가 2일 6시간 꺼져 수집 cron 7종이 전부 멈췄는데
아무도 몰랐다. 어드민 화면이 `row_count > 0`만 보고 계속 "적재됨"을 띄웠기 때문이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class FreshnessState(Enum):
    FRESH = "fresh"  # 기대 주기 안 — 정상
    LATE = "late"  # 기대 주기를 넘김 — 지연
    STALE = "stale"  # 한참 넘김 — 정지로 본다
    UNKNOWN = "unknown"  # 주기가 있는데 적재 이력이 없음
    UNSCHEDULED = "unscheduled"  # 주기가 없는 데이터셋 — 판정 대상 아님


@dataclass(frozen=True)
class DatasetSchedule:
    expected: str  # 사람이 읽는 기대 주기
    late_after: timedelta
    stale_after: timedelta


# 실제 crontab(백엔드 PC) 기준. cron은 호스트에만 있어 이 표가 유일한 문서화 지점이다.
#
# 휴장·주말이 있는 데이터셋(price_bars·forecast_snapshots)은 임계값을 일부러 둔감하게 잡았다.
# 거래일 캘린더 기반 정밀 판정은 과설계다 — 30분 주기인 news_articles가 정지를 가장
# 먼저 잡아주므로, 나머지는 오탐을 줄이는 쪽이 낫다.
SCHEDULES: dict[str, DatasetSchedule] = {
    # */30 * * * *  collect_news.py
    "news_articles": DatasetSchedule("30분마다", timedelta(hours=3), timedelta(hours=12)),
    # 5 * * * *  collect_prices.py — 봉은 장중에만 늘어난다. 미국 종목은 금요일 종가
    # (토 06:00 KST) 이후 화요일 06:00 KST까지 신규 봉이 없어 3일 공백이 정상이다.
    "price_bars": DatasetSchedule("매시간", timedelta(days=4), timedelta(days=7)),
    # 30 1 * * *  collect_market_news.py
    "market_news": DatasetSchedule("매일", timedelta(days=2), timedelta(days=4)),
    # 30 2 * * *  label_news.py
    "news_labels": DatasetSchedule("매일", timedelta(days=2), timedelta(days=4)),
    # 0 14 * * *  snapshot_forecasts.py — as_of가 '마지막 봉 시각'이라 주말엔 값이 같고
    # (ticker, horizon, as_of) 유니크 충돌로 신규 행이 안 생긴다. 주말 3일 공백이 정상.
    "forecast_snapshots": DatasetSchedule("매일(거래일)", timedelta(days=4), timedelta(days=8)),
    # 0 3 * * 1  collect_fundamentals.py
    "fundamental_snapshots": DatasetSchedule("주 1회", timedelta(days=10), timedelta(days=21)),
}


@dataclass(frozen=True)
class FreshnessVerdict:
    state: FreshnessState
    expected: str | None  # 주기 없는 데이터셋은 None
    age_seconds: int | None  # 적재 이력이 없거나 주기가 없으면 None


def evaluate(key: str, latest_at: datetime | None, now: datetime) -> FreshnessVerdict:
    """데이터셋 하나의 신선도를 판정한다. `now`는 주입한다(순수성 + 테스트 결정성)."""
    schedule = SCHEDULES.get(key)
    if schedule is None:
        return FreshnessVerdict(FreshnessState.UNSCHEDULED, None, None)
    if latest_at is None:
        return FreshnessVerdict(FreshnessState.UNKNOWN, schedule.expected, None)

    # 시계 스큐·타임존 차이로 미래가 나올 수 있다 — 음수 나이는 0으로 본다.
    age = max(now - latest_at, timedelta(0))
    if age <= schedule.late_after:
        state = FreshnessState.FRESH
    elif age <= schedule.stale_after:
        state = FreshnessState.LATE
    else:
        state = FreshnessState.STALE
    return FreshnessVerdict(state, schedule.expected, int(age.total_seconds()))
