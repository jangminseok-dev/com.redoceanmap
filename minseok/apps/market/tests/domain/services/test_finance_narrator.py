from market.domain.services import finance_engine as fe
from market.domain.services import finance_narrator as fn
from market.domain.value_objects.finance_vo import FinanceInputs, Source, Sourced


def _plan(sales=15_000_000, equity=100_000_000):
    return fe.plan(FinanceInputs(
        equity=Sourced(equity, Source.INPUT),
        deposit=Sourced(30_000_000, Source.ASSUMED, "월세 10개월분 가정"),
        monthly_rent=Sourced(3_000_000, Source.AREA_AVG, "동북권 소규모 상가 평균, 33㎡ 가정"),
        key_money=Sourced(0, Source.ASSUMED, "권리금 0 가정"),
        startup_cost=Sourced(80_000_000, Source.FRANCHISE, "공정위 커피(2025) 중앙값, 임대료·권리금 제외"),
        monthly_payroll=Sourced(0, Source.ASSUMED, "1인 운영 가정"),
        cost_ratio=Sourced(0.30, Source.ASSUMED, "카페·음료 원가율 30%(잠정)"),
        loan_rate=Sourced(4.5, Source.ECOS, "한국은행 2026-08 대출평균"),
        desired_loan=Sourced(0, Source.ASSUMED),
        expected_monthly_sales=Sourced(sales, Source.AREA_AVG, "점포당 월매출") if sales else None,
    ), assumptions=("이자만 반영(원리금 상환 제외)",))


def test_원_표기():
    assert fn.won(120_000_000) == "1억 2,000만원"
    assert fn.won(80_360_000) == "8,036만원"
    assert fn.won(71_250) == "7만원"
    assert fn.won(0) == "0원"


def test_입력_줄에_값과_출처가_전부_붙는다():
    line = fn.input_line(_plan())
    assert "자기자본 1억원(입력)" in line
    assert "월세 300만원(동북권 소규모 상가 평균, 33㎡ 가정)" in line
    assert "창업비용 8,000만원(공정위 커피(2025) 중앙값, 임대료·권리금 제외)" in line


def test_헤드라인은_손익분기_달성률_부족자금을_말하고_흑자면_버틸_기간을_말하지_않는다():
    text = fn.headline(_plan(), "성수동카페거리", "커피-음료")
    assert "손익분기 월매출" in text and "달성률" in text and "부족 자금" in text
    assert "버틸" not in text
    assert "금리가 1%p 오르면" in text


def test_적자면_남은_현금으로_버틸_개월을_말한다():
    text = fn.headline(_plan(sales=3_000_000), "성수동카페거리", "커피-음료")
    assert "개월 버틸" in text


def test_매출_없으면_달성률_대신_표본_부족을_말한다():
    text = fn.headline(_plan(sales=None), "성수동카페거리", "커피-음료")
    assert "표본이 적어" in text and "손익분기 월매출" in text


def test_가정_문장은_가정치_출처만_모은다():
    note = fn.assumption_note(_plan())
    assert "월세 10개월분 가정" in note and "1인 운영 가정" in note and "이자만 반영" in note
    assert "공정위" not in note  # FRANCHISE는 가정이 아니라 데이터


def test_금리_스트레스는_점마다_부호를_따로_붙인다():
    # +1%p는 이익, +2%p는 적자로 갈리는 교차 케이스 — 한 문장의 라벨이 뒤 점의 부호에 끌려가면 안 된다
    from market.domain.value_objects.finance_vo import StressPoint
    from dataclasses import replace
    p = _plan()
    crossed = replace(p, stress=(
        StressPoint(rate_delta_pp=1.0, loan_rate=5.5, monthly_profit=2_500_000, runway_months=None),
        StressPoint(rate_delta_pp=2.0, loan_rate=6.5, monthly_profit=-300_000, runway_months=12.0),
    ))
    text = fn.headline(crossed, "성수동카페거리", "커피-음료")
    assert "1%p 오르면 월 이익 250만원" in text
    assert "2%p 오르면 월 적자 30만원" in text


def test_스트레스_점이_하나여도_헤드라인이_깨지지_않는다():
    from dataclasses import replace
    p = _plan()
    one = replace(p, stress=p.stress[:1])
    text = fn.headline(one, "성수동카페거리", "커피-음료")
    assert "금리가 1%p 오르면" in text and "2%p" not in text



def test_계산_이익률이_업종_평균보다_크게_높으면_경고하고_평균_이익률_기준_이익을_병기한다():
    from dataclasses import replace
    # 월매출 1,500만원, 이익 = 1,050만 − 300만 − 이자 ≈ 745만 → 이익률 약 50% vs 카페 평균 14%
    p = replace(_plan(), benchmark_margin=0.14, benchmark_label="카페·음료")
    text = fn.headline(p, "성수동카페거리", "커피-음료")
    assert "이 계산의 영업이익률 50%는 카페·음료 업종 평균 14%보다 크게 높아요" in text
    assert "업종 평균 이익률로 보면 월 이익은 약 210만원이에요" in text
    # 벤치마크 없거나 이익률이 평균 1.5배 이내면 경고 없음
    assert "업종 평균" not in fn.headline(_plan(), "성수동카페거리", "커피-음료")
    modest = replace(_plan(sales=4_800_000), benchmark_margin=0.14, benchmark_label="카페·음료")
    assert "업종 평균" not in fn.headline(modest, "성수동카페거리", "커피-음료")
