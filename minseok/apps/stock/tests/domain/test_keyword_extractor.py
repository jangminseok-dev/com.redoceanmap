"""keyword_extractor(B2) — 결정론 키워드 추출 규칙을 고정한다."""
from __future__ import annotations

from datetime import datetime, timezone

from stock.domain.services.keyword_extractor import (
    HeadlineSample,
    extract_keywords,
)

_D1 = datetime(2026, 8, 20, tzinfo=timezone.utc)
_D2 = datetime(2026, 8, 22, tzinfo=timezone.utc)


def _sample(title, sentiment=None, published_at=_D1):
    return HeadlineSample(title=title, sentiment=sentiment, published_at=published_at)


def test_표본_미달이면_빈_리스트():  # 두세 건짜리 빈도는 잡음
    assert extract_keywords([_sample("HBM 수주 확대")] * 4) == []


def test_빈도_상위_키워드가_뽑히고_불용어는_제외된다():
    samples = [
        _sample("HBM 수주 확대 발표"),
        _sample("HBM 공급 계약 체결"),
        _sample("HBM 증설 검토"),
        _sample("배당 확대 검토"),
        _sample("신제품 공개 행사"),
    ]
    got = extract_keywords(samples)
    keywords = [k.keyword for k in got]
    assert keywords[0] == "HBM".lower() or keywords[0] == "hbm"
    assert got[0].count == 3
    assert "발표" not in keywords  # 불용어


def test_과빈도_토큰은_회사명_상용구로_보고_제외한다():
    samples = [_sample(f"삼성전자 소식 {i}번") for i in range(4)] + [
        _sample("삼성전자 수주 확대"), _sample("수주 물량 검토"),
    ]
    keywords = [k.keyword for k in extract_keywords(samples)]
    assert "삼성전자" not in keywords  # 5/6 = 83% > 70% 컷 — 회사명은 변별력 0
    assert "수주" in keywords          # 2/6 — 유지


def test_과빈도_경계는_70퍼센트다():
    # 10건 중 7건 초과(8건) 등장 → 제외, 7건 등장 → 유지
    samples = [_sample(f"수주 확대 {i}") for i in range(7)] + [
        _sample("무관한 제목 하나"), _sample("무관한 제목 둘"), _sample("무관한 제목 셋"),
    ]
    keywords = [k.keyword for k in extract_keywords(samples)]
    assert "수주" in keywords  # 7/10 = 정확히 0.7 — 컷 아님(초과만 컷)


def test_동반_감성_평균과_최신_근거_헤드라인이_붙는다():
    samples = [
        _sample("리콜 조사 착수", sentiment=-0.6, published_at=_D1),
        _sample("리콜 규모 확대", sentiment=-0.4, published_at=_D2),
        _sample("무관한 소식 하나"),
        _sample("무관한 소식 둘"),
        _sample("무관한 소식 셋"),
    ]
    got = {k.keyword: k for k in extract_keywords(samples)}
    assert got["리콜"].sentiment_avg == -0.5
    assert got["리콜"].sample_title == "리콜 규모 확대"  # 최신 발행분이 근거


def test_조사_1자_컷으로_변형이_합산된다():
    samples = [
        _sample("실적이 눈길"), _sample("실적은 사상 최대"), _sample("실적 개선 지속"),
        _sample("무관한 제목 하나"), _sample("무관한 제목 둘"),
    ]
    got = {k.keyword: k for k in extract_keywords(samples)}
    assert got["실적"].count == 3
