"""수집 신선도 감시 — 모의투자 step 누락 세션 판정(순수)."""
import importlib.util
import pathlib
from datetime import UTC, date, datetime

_spec = importlib.util.spec_from_file_location(
    "check_freshness", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "check_freshness.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# 2026-09 미국 세션: 목 9/10 · 금 9/11 · 월 9/14
SESSIONS = [date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 14)]


def _kst_9am(day: int) -> datetime:
    return datetime(2026, 9, day, 0, 0, tzinfo=UTC)  # check-freshness CronJob 09:00 KST


def test_PC가_꺼져_금요일_세션을_놓치면_월요일_아침에_잡는다():
    # 2026-09-12~14 사고: 마지막 판단 기준일 9/10, 월 09:00(부팅 뒤) 점검
    assert _mod.overdue_paper_sessions(SESSIONS[:2], date(2026, 9, 10), _kst_9am(14)) == [date(2026, 9, 11)]


def test_주말은_누락이_아니다():
    # 토 14:00에 금요일 세션 판단 완료 → 월 09:00엔 새 세션이 없다
    assert _mod.overdue_paper_sessions(SESSIONS[:2], date(2026, 9, 11), _kst_9am(14)) == []


def test_step_예정_시각_전인_어제_세션은_누락이_아니다():
    # 화 09:00 — 월요일 세션 step은 화 14:00에 돈다
    assert _mod.overdue_paper_sessions(SESSIONS, date(2026, 9, 11), _kst_9am(15)) == []


def test_step_예정_시각이_지나면_누락이다():
    # 수 09:00 — 월요일 세션 판단이 여전히 없다
    assert _mod.overdue_paper_sessions(SESSIONS, date(2026, 9, 11), _kst_9am(16)) == [date(2026, 9, 14)]


def test_본문에_모의투자_사유와_조치를_싣는다():
    body = _mod.build_body([], None, "AI 모의투자 판단 누락 1세션")
    assert "AI 모의투자 판단 누락 1세션" in body and "snapshot_forecasts.py" in body
