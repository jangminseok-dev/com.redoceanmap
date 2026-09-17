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



def _snap(ticker, day, ret, direction="UP", atr=0.01, cfg="refit-20260901"):
    return (ticker, datetime(2026, 9, day, tzinfo=UTC), direction, ret, atr, cfg)


def test_신호_성적이_기준선_아래면_사유를_낸다():
    # 20종목 각 1군집 — 반등 신호 뒤 전부 하락, 이력상 기준선은 50%
    recent = [_snap(f"T{i}", 8, -0.02) for i in range(20)]
    history = recent + [_snap(f"T{i}", 1, 0.02, direction="NEUTRAL") for i in range(20)]
    reason = _mod.signal_decay_verdict(recent, history)
    assert "refit-20260901 반등 신호 적중 0.0% ≤ 종목 기준선 50.0% (실효 표본 20군집)" in reason
    assert "신호 성적이 기준선 아래" in _mod.build_body([], None, None, reason)


def test_옛_조합의_좋은_성적이_새_조합의_부진을_가리지_않는다():
    # 9/17 실측 모양 — 옛 조합 20군집 전부 적중 + 새 조합 20군집 전부 실패. 합치면 50%로 기준선과 같아 보인다
    old = [_snap(f"O{i}", 1, 0.02, cfg="refit-20260822") for i in range(20)]
    new = [_snap(f"T{i}", 8, -0.02) for i in range(20)]
    history = old + new + [_snap(f"O{i}", 2, -0.02, direction="NEUTRAL") for i in range(20)] \
        + [_snap(f"T{i}", 2, 0.02, direction="NEUTRAL") for i in range(20)]
    reason = _mod.signal_decay_verdict(old + new, history)
    assert reason is not None and "refit-20260901" in reason and "refit-20260822" not in reason


def test_신호_성적_표본이_적거나_기준선_위면_알리지_않는다():
    few = [_snap(f"T{i}", 8, -0.02) for i in range(14)]
    assert _mod.signal_decay_verdict(few, few) is None
    good = [_snap(f"T{i}", 8, 0.02) for i in range(20)]
    history = good + [_snap(f"T{i}", 1, -0.02, direction="NEUTRAL") for i in range(20)]
    assert _mod.signal_decay_verdict(good, history) is None


def test_같은_종목_같은_주_반복_신호는_한_군집이다():
    # 2026-09-07(월)~11(금) COST 5건은 한 군집 — 다른 13종목과 합쳐 14군집이라 판단 보류(원표본은 18건)
    repeats = [_snap("COST", d, -0.02) for d in (7, 8, 9, 10, 11)] + [_snap(f"T{i}", 8, -0.02) for i in range(13)]
    assert _mod.signal_decay_verdict(repeats, repeats) is None
