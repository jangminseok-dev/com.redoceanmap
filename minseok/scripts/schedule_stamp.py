"""주간·월간 배치의 따라잡기 도장 — PC가 꺼져 있어 지정 시각을 놓치면 그 주를 통째로 건너뛰던 문제(2026-09-18 실측).

백엔드 PC는 매일 00:10 재부팅하고 밤새 꺼져 있는 날도 있다. 9/14(월) 03:00 펀더멘털 수집은 PC가 꺼져 있어
실행되지 않았고, 다음 월요일까지 11일간 데이터가 멈췄다. 해결은 **매일 시도 + 최근에 성공했으면 건너뛰기**다
(anacron과 같은 발상). 도장 파일은 사용자 홈 캐시에 남긴다 — 실행 성공 시각만 적는 한 줄짜리다.

    from schedule_stamp import done_recently, mark_done
    if done_recently("fundamentals", days=6):
        return 0
    ...
    mark_done("fundamentals")
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

STAMP_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "redoceanmap"


def _path(name: str) -> Path:
    return STAMP_DIR / f"{name}.last"


def done_recently(name: str, days: float) -> bool:
    """최근 days 안에 성공 도장이 찍혔으면 True(=이번 실행은 건너뛴다). 도장이 없으면 False."""
    stamp = _path(name)
    if not stamp.exists():
        return False
    age_days = (datetime.now(UTC).timestamp() - stamp.stat().st_mtime) / 86400
    if age_days < days:
        print(f"[schedule] {name}: {age_days:.1f}일 전에 실행됨(주기 {days}일) — 건너뜁니다", flush=True)
        return True
    return False


def mark_done(name: str) -> None:
    STAMP_DIR.mkdir(parents=True, exist_ok=True)
    _path(name).write_text(datetime.now(UTC).isoformat(), encoding="utf-8")
