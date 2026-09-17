from market.domain.services.area_scorer import AreaScorer, prev_quarter
from market.domain.value_objects.area_score_vo import (
    MetricComparison,
    QuarterValue,
)

scorer = AreaScorer()


def _qv(yq, value):
    return QuarterValue(year_quarter=yq, value=value)


# --- prev_quarter / qoq_series ---


def test_직전_분기_코드를_계산한다():
    assert prev_quarter(20252) == 20251
    assert prev_quarter(20251) == 20244  # 연도 경계


def test_연속_분기의_QoQ_변화율을_계산한다():
    points = scorer.qoq_series([_qv(20251, 100), _qv(20252, 110), _qv(20253, 99)])
    assert [p.qoq_rate for p in points] == [None, 10.0, -10.0]
    assert [p.year_quarter for p in points] == [20251, 20252, 20253]


def test_연도_경계를_넘는_분기도_연속으로_본다():
    points = scorer.qoq_series([_qv(20244, 200), _qv(20251, 220)])
    assert points[1].qoq_rate == 10.0


def test_비연속_분기는_변화율이_None이다():
    points = scorer.qoq_series([_qv(20251, 100), _qv(20253, 120)])  # 20252 결측
    assert points[1].qoq_rate is None


def test_직전_분기_값이_0이면_변화율이_None이다():
    points = scorer.qoq_series([_qv(20251, 0), _qv(20252, 100)])
    assert points[1].qoq_rate is None


def test_입력_순서와_무관하게_오름차순으로_정렬한다():
    points = scorer.qoq_series([_qv(20252, 110), _qv(20251, 100)])
    assert [p.year_quarter for p in points] == [20251, 20252]
    assert points[1].qoq_rate == 10.0


# --- score v2 ---


def _score(closure=None, persistence=None, sales=None):
    return scorer.score(closure_stability=closure, persistence=persistence, sales_level=sales)


def test_중앙값과_같으면_컴포넌트_점수는_50이다():
    result = _score(closure=MetricComparison(value=3.0, benchmark=3.0))
    assert result.components[0].score == 50.0
    assert result.total == 50.0
    assert result.grade == "보통"


def test_폐업률은_낮을수록_점수가_높다():
    # 중앙값 3% 대비 1.5% → -1.5%p, 낮은 쪽이 좋으므로 50 + 50*(1.5/3) = 75
    assert _score(closure=MetricComparison(value=1.5, benchmark=3.0)).components[0].score == 75.0
    assert _score(closure=MetricComparison(value=4.5, benchmark=3.0)).components[0].score == 25.0
    assert _score(closure=MetricComparison(value=9.0, benchmark=3.0)).components[0].score == 0.0  # 캡 클램프


def test_영업_지속성은_중앙값_대비_상대비로_채점한다():
    # 100 대비 125 → 상대비 +25% → 50 + 50*(0.25/0.5) = 75
    assert _score(persistence=MetricComparison(value=125.0, benchmark=100.0)).components[0].score == 75.0


def test_지속성_벤치마크가_0이하면_컴포넌트를_제외한다():
    assert _score(persistence=MetricComparison(value=100.0, benchmark=0.0)) is None


def test_점포당_매출은_로그_비로_채점한다():
    # 중앙값의 2배 = 100, 절반 = 0, 같으면 50
    assert _score(sales=MetricComparison(value=2000.0, benchmark=1000.0)).components[0].score == 100.0
    assert _score(sales=MetricComparison(value=500.0, benchmark=1000.0)).components[0].score == 0.0
    assert _score(sales=MetricComparison(value=0.0, benchmark=1000.0)) is None  # log 불가 → 제외


def test_총점은_가용_컴포넌트의_가중_평균이다():
    # 폐업 안정성 100(가중 0.45) + 점포당 매출 50(가중 0.22) → (45 + 11) / 0.67 = 83.6
    result = _score(
        closure=MetricComparison(value=0.0, benchmark=3.0),
        sales=MetricComparison(value=1000.0, benchmark=1000.0),
    )
    assert result.total == 83.6
    assert [c.key for c in result.components] == ["closure_stability", "sales_level"]


def test_컴포넌트가_전부_결측이면_None을_반환한다():
    assert _score() is None


def test_등급_경계():
    def grade_of(closure_value):  # 폐업률 중앙값 3% 기준 — 단일 컴포넌트라 총점 = 컴포넌트 점수
        return _score(closure=MetricComparison(value=closure_value, benchmark=3.0)).grade

    assert grade_of(0.0) == "우수"  # 100
    assert grade_of(1.2) == "우수"  # 80
    assert grade_of(2.1) == "양호"  # 65
    assert grade_of(3.0) == "보통"  # 50
    assert grade_of(3.9) == "주의"  # 35
    assert grade_of(4.5) == "위험"  # 25


# --- YoY (전년 동분기 대비) ---

def _series(pairs):
    return [_qv(yq, v) for yq, v in pairs]


def test_전년_동분기_코드는_10을_뺀다():
    from market.domain.services.area_scorer import prev_year_quarter
    # 코드 형식이 연도×10+분기라 1년 전은 -10이다(-10000이 아니다)
    assert prev_year_quarter(20254) == 20244
    assert prev_year_quarter(20211) == 20201


def test_yoy는_같은_분기끼리_비교한다():
    scorer = AreaScorer()
    series = _series([(20234, 100.0), (20241, 50.0), (20242, 60.0), (20243, 70.0), (20244, 110.0)])
    got = {p.year_quarter: p.qoq_rate for p in scorer.yoy_series(series)}
    assert got[20244] == 10.0  # 110 vs 전년 4분기 100
    assert got[20241] is None  # 20231이 창에 없다


def test_yoy는_계절성을_걷어낸다():
    """4분기는 3분기 대비 늘 뛴다 — QoQ만 보면 실제로 줄어든 해도 성장으로 보인다."""
    scorer = AreaScorer()
    series = _series([(20233, 70.0), (20234, 120.0), (20243, 70.0), (20244, 110.0)])
    qoq = {p.year_quarter: p.qoq_rate for p in scorer.qoq_series(series)}
    yoy = {p.year_quarter: p.qoq_rate for p in scorer.yoy_series(series)}
    assert qoq[20244] > 0        # 3분기 대비로는 +57%
    assert yoy[20244] < 0        # 전년 동분기 대비로는 -8.3%


def test_기준_분기가_0이면_yoy를_만들지_않는다():  # 0 나눗셈 방어
    scorer = AreaScorer()
    got = {p.year_quarter: p.qoq_rate for p in scorer.yoy_series(_series([(20234, 0.0), (20244, 50.0)]))}
    assert got[20244] is None
