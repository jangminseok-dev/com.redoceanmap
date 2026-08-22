"""bookmark_alert_composer 테스트 — 결정론 템플릿과 어휘 경계(권유 금지·고지)를 고정한다."""
from __future__ import annotations

from hub.domain.alert.bookmark_alert_composer import DISCLAIMER, AlertLine, compose_alert

_LINES = [
    AlertLine(label="삼성전자", ticker="005930.KS", direction="UP",
              change_pct=0.012, signal_date="8/22", reference=True),
    AlertLine(label="테슬라", ticker="TSLA", direction="DOWN",
              change_pct=None, signal_date="8/22", reference=False),
]


def test_제목은_건수와_방향_요약을_담는다():
    subject, _ = compose_alert(_LINES)
    assert subject == "[redoceanmap] 관심 종목 신호 2건 (상승 1 · 하락 1)"


def test_본문은_종목_줄과_고지를_담고_변동_미상은_그대로_말한다():
    _, body = compose_alert(_LINES)
    assert "- 삼성전자(005930.KS): 상승 신호 · 전일 대비 +1.2% · 신호 8/22 기준 · 검증 참고 신호" in body
    assert "- 테슬라(TSLA): 하락 신호 · 전일 대비 변동 미상 · 신호 8/22 기준" in body
    assert DISCLAIMER in body
    assert "일일 수집 기준" in body  # 준실시간 오해 방지 문구


def test_권유_어휘를_쓰지_않는다():
    subject, body = compose_alert(_LINES)
    text = subject + body
    for banned in ("매수하세요", "매도하세요", "추천", "확률"):
        assert banned not in text


def test_결정론_같은_입력이면_같은_메일():
    assert compose_alert(list(_LINES)) == compose_alert(list(_LINES))
