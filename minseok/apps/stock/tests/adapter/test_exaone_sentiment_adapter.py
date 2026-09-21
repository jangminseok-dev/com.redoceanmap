"""감성 LLM 폴백 — 응답 파싱과 결정론(2026-09-21: 1분 사이 부호가 바뀌고, 첫 헤드라인 점수만 읽던 문제)."""
import pytest

from stock.adapter.outbound import exaone_sentiment_adapter as mod
from stock.adapter.outbound.exaone_sentiment_adapter import ExaoneSentimentAdapter, _parse_score


def test_숫자_하나면_그_값():
    assert _parse_score("0.3") == 0.3 and _parse_score("감성: -0.45") == -0.45


def test_헤드라인마다_한_줄씩_오면_첫_줄이_아니라_전체_평균():
    raw = "-0.1\n-0.4\n0.3\n0.4\n0.4\n0.2\n0.5\n0.3"   # 실제 로그 형태 — 예전 파서는 -0.1만 읽었다
    assert _parse_score(raw) == pytest.approx(0.2)


def test_범위_밖_숫자와_빈_응답은_무시():
    assert _parse_score("10점 만점에 7, 점수 0.4") == 0.4
    assert _parse_score("판단 불가") == 0.0


async def test_LLM은_온도_0으로_부른다(monkeypatch):
    seen = {}

    async def fake(prompt, **kwargs):
        seen.update(kwargs)
        return "0.2"

    monkeypatch.setattr(mod.llm_orchestrator, "orchestrate", fake)
    score = await ExaoneSentimentAdapter().analyze(["헤드라인"])
    assert score.value == 0.2 and seen["options"] == {"temperature": 0}
