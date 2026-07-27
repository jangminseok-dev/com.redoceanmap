"""이벤트 사후 수익률 집계 — 기준선 대비와 표본 경고가 핵심이다."""
from stock.domain.services.event_study import EventSample, aggregate


def _s(event="실적", sentiment=0.5, ret=1.0, week="2026-07-13"):
    return EventSample(event_type=event, sentiment=sentiment, return_pct=ret, week=week)


def test_표본이_없으면_경고와_함께_빈_리포트():
    r = aggregate([], horizon_days=5)
    assert r.total == 0 and r.by_event == [] and r.warnings


def test_기준선은_전체_평균이고_초과분이_본체다():
    # 시장 전체가 -2%인 구간에서 실적 뉴스가 -1%면 '악재'가 아니라 +1%p 선방이다.
    samples = [_s(event="실적", ret=-1.0) for _ in range(10)] + [
        _s(event="규제·소송", ret=-3.0) for _ in range(10)
    ]
    r = aggregate(samples, horizon_days=5)

    assert r.baseline_pct == -2.0
    by = {b.key: b for b in r.by_event}
    assert by["실적"].avg_return_pct == -1.0
    assert by["실적"].excess_pct == 1.0      # 절대는 음수인데 초과는 양수
    assert by["규제·소송"].excess_pct == -1.0


def test_초과수익_내림차순으로_정렬한다():
    samples = (
        [_s(event="A", ret=5.0) for _ in range(3)]
        + [_s(event="B", ret=1.0) for _ in range(3)]
        + [_s(event="C", ret=3.0) for _ in range(3)]
    )
    assert [b.key for b in aggregate(samples, 5).by_event] == ["A", "C", "B"]


def test_표본이_한_주에_몰리면_경고한다():
    # 2주에 97%가 몰린 실제 상황 — 관측 수가 커도 사실상 시장 방향 하나를 나눠 본 것이다
    samples = [_s(week="2026-07-13") for _ in range(90)] + [
        _s(week="2026-06-01") for _ in range(10)
    ]
    r = aggregate(samples, 5)
    assert r.top_week_share == 0.9
    assert any("몰려 있습니다" in w for w in r.warnings)


def test_표본이_고르면_집중도_경고가_없다():
    samples = [_s(week=f"2026-0{i % 9 + 1}-01") for i in range(90)]
    r = aggregate(samples, 5)
    assert not any("몰려" in w for w in r.warnings)


def test_버킷_표본이_적으면_신뢰하지_않는다고_표시한다():
    r = aggregate([_s() for _ in range(99)], 5)
    assert r.by_event[0].n == 99 and r.by_event[0].reliable is False
    assert any("100건 미만" in w for w in r.warnings)


def test_버킷_표본이_충분하면_신뢰_표시():
    r = aggregate([_s(week=f"w{i % 20}") for i in range(100)], 5)
    assert r.by_event[0].reliable is True


def test_감성대별로도_집계한다():
    samples = [_s(sentiment=0.8, ret=2.0) for _ in range(5)] + [
        _s(sentiment=-0.8, ret=-2.0) for _ in range(5)
    ]
    bands = {b.key: b for b in aggregate(samples, 5).by_sentiment}
    assert bands["강한 긍정"].excess_pct == 2.0
    assert bands["강한 부정"].excess_pct == -2.0


def test_양의_수익률_비율을_센다():
    samples = [_s(ret=1.0), _s(ret=-1.0), _s(ret=2.0), _s(ret=-2.0)]
    assert aggregate(samples, 5).by_event[0].positive_rate == 0.5
