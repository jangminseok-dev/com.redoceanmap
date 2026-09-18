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


ACTIVE = "refit-20260901"   # 테스트 스냅샷의 기본 조합 = 활성 조합


def test_활성_조합_성적이_통계적으로_기준선_아래면_사유를_낸다():
    # 40종목 각 1군집 — 반등 신호 뒤 전부 하락, 이력상 기준선은 50%. 95% 상한(0.0% → 9.0%)이 기준선 아래
    recent = [_snap(f"T{i}", 8, -0.02) for i in range(40)]
    history = recent + [_snap(f"T{i}", 1, 0.02, direction="NEUTRAL") for i in range(40)]
    reason = _mod.signal_decay_verdict(recent, history, ACTIVE)
    assert "refit-20260901 반등 신호 적중 0.0%" in reason and "종목 기준선 50.0%" in reason and "40군집" in reason
    assert "신호 성적이 기준선 아래" in _mod.build_body([], None, None, reason)


def test_내린_조합의_성적은_경보하지_않는다():
    # 2026-09-18 헛경보 — 9/17에 내린 refit-20260901을 활성 조합(rollback)이 아닌데도 매일 알렸다
    recent = [_snap(f"T{i}", 8, -0.02) for i in range(40)]
    history = recent + [_snap(f"T{i}", 1, 0.02, direction="NEUTRAL") for i in range(40)]
    assert _mod.signal_decay_verdict(recent, history, "rollback-20260917") is None
    assert _mod.signal_decay_verdict(recent, history, None) is None


def test_표본이_작아_기준선과_구별되지_않으면_알리지_않는다():
    # 9/18 실측 모양 — 19군집 중 1건 적중(5.3%)이지만 95% 상한 26%로 기준선 25.6%와 구별되지 않는다
    recent = [_snap("H0", 8, 0.05)] + [_snap(f"T{i}", 8, -0.02) for i in range(18)]
    history = recent + [_snap(f"T{i}", 1, 0.02, direction="NEUTRAL") for i in range(6)] \
        + [_snap(f"T{i}", 2, -0.02, direction="NEUTRAL") for i in range(18)]
    assert _mod.signal_decay_verdict(recent, history, ACTIVE) is None


def test_옛_조합의_좋은_성적이_새_조합의_부진을_가리지_않는다():
    # 9/17 실측 모양 — 옛 조합 40군집 전부 적중 + 활성 조합 40군집 전부 실패. 합치면 50%로 기준선과 같아 보인다
    old = [_snap(f"O{i}", 1, 0.02, cfg="refit-20260822") for i in range(40)]
    new = [_snap(f"T{i}", 8, -0.02) for i in range(40)]
    history = old + new + [_snap(f"O{i}", 2, -0.02, direction="NEUTRAL") for i in range(40)] \
        + [_snap(f"T{i}", 2, 0.02, direction="NEUTRAL") for i in range(40)]
    reason = _mod.signal_decay_verdict(old + new, history, ACTIVE)
    assert reason is not None and "refit-20260901" in reason and "refit-20260822" not in reason


def test_신호_성적_표본이_적거나_기준선_위면_알리지_않는다():
    few = [_snap(f"T{i}", 8, -0.02) for i in range(14)]
    assert _mod.signal_decay_verdict(few, few, ACTIVE) is None
    good = [_snap(f"T{i}", 8, 0.02) for i in range(40)]
    history = good + [_snap(f"T{i}", 1, -0.02, direction="NEUTRAL") for i in range(40)]
    assert _mod.signal_decay_verdict(good, history, ACTIVE) is None


def test_같은_종목_같은_주_반복_신호는_한_군집이다():
    # 2026-09-07(월)~11(금) COST 5건은 한 군집 — 다른 13종목과 합쳐 14군집이라 판단 보류(원표본은 18건)
    repeats = [_snap("COST", d, -0.02) for d in (7, 8, 9, 10, 11)] + [_snap(f"T{i}", 8, -0.02) for i in range(13)]
    assert _mod.signal_decay_verdict(repeats, repeats, ACTIVE) is None


# --- 위험 신호 검증 감시(2026-09-18 신설) ---

def _risk_payload(**validated):
    return {"signals": [
        {"key": k, "label": f"신호 {k}", "validated": v, "test": {"rate": 0.3, "base": 0.29, "n_eff": 600.0}}
        for k, v in validated.items()
    ]}


def test_검증되던_위험_신호가_떨어지면_알린다():
    now = datetime(2026, 9, 18, tzinfo=UTC)
    latest = (datetime(2026, 9, 17, tzinfo=UTC), _risk_payload(vol_high=True, drop_high=False))
    reason = _mod.risk_signal_verdict(latest, _risk_payload(vol_high=True, drop_high=True), now)
    assert reason is not None and "신호 drop_high" in reason and "vol_high" not in reason
    assert "위험 신호 보드의 검증 상태" in _mod.build_body([], None, None, None, reason)


def test_처음부터_검증_미달이던_신호는_알리지_않는다():
    now = datetime(2026, 9, 18, tzinfo=UTC)
    latest = (datetime(2026, 9, 17, tzinfo=UTC), _risk_payload(vol_high=True, drop_high=False))
    assert _mod.risk_signal_verdict(latest, _risk_payload(vol_high=True, drop_high=False), now) is None


def test_리포트가_낡거나_없으면_알린다():
    now = datetime(2026, 9, 18, tzinfo=UTC)
    old = (datetime(2026, 9, 1, tzinfo=UTC), _risk_payload(vol_high=True))
    assert "17일 지났습니다" in _mod.risk_signal_verdict(old, None, now)
    assert "리포트가 없습니다" in _mod.risk_signal_verdict(None, None, now)
