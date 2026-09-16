"""finance_engine — 산식·경계·출처 보존. 숫자는 손으로 검산 가능한 값으로 둔다."""
from market.domain.services import finance_engine as fe
from market.domain.value_objects.finance_vo import FinanceInputs, Source, Sourced


def _inputs(**over) -> FinanceInputs:
    base = dict(
        equity=Sourced(100_000_000, Source.INPUT),
        deposit=Sourced(30_000_000, Source.ASSUMED, "월세 10개월분 가정"),
        monthly_rent=Sourced(3_000_000, Source.INPUT),
        key_money=Sourced(0, Source.ASSUMED, "권리금 0 가정"),
        startup_cost=Sourced(80_000_000, Source.FRANCHISE, "공정위 커피 중앙값"),
        monthly_payroll=Sourced(0, Source.ASSUMED, "1인 운영 가정"),
        cost_ratio=Sourced(0.30, Source.ASSUMED, "카페 원가율"),
        loan_rate=Sourced(4.5, Source.ECOS),
        desired_loan=Sourced(0, Source.ASSUMED),
        expected_monthly_sales=Sourced(15_000_000, Source.AREA_AVG, "점포당 월매출"),
    )
    base.update(over)
    return FinanceInputs(**base)


def test_기본_산식():
    p = fe.plan(_inputs())
    assert p.capex == 110_000_000                      # 8천만 + 3천만 + 0
    assert p.opex_base == 3_000_000
    assert p.funding_gap == 110_000_000 + 9_000_000 - 100_000_000  # 1,900만
    assert p.loan == 19_000_000
    assert p.loan_interest == round(19_000_000 * 4.5 / 100 / 12)  # 71,250
    assert p.fixed_monthly == 3_000_000 + p.loan_interest
    assert p.bep_monthly_sales == round(p.fixed_monthly / 0.7)
    assert p.attainment == round(15_000_000 / p.bep_monthly_sales, 2)
    assert p.monthly_profit == round(15_000_000 * 0.7 - p.fixed_monthly)
    assert p.cash_after == 100_000_000 + 19_000_000 - 110_000_000


def test_부족자금은_0_아래로_내려가지_않고_대출은_희망액을_우선한다():
    p = fe.plan(_inputs(equity=Sourced(500_000_000, Source.INPUT)))
    assert p.funding_gap == 0 and p.loan == 0 and p.loan_interest == 0
    q = fe.plan(_inputs(desired_loan=Sourced(50_000_000, Source.INPUT)))
    assert q.loan == 50_000_000


def test_흑자면_runway가_없고_적자면_남은_현금을_월_적자로_나눈다():
    assert fe.plan(_inputs()).runway_months is None
    p = fe.plan(_inputs(expected_monthly_sales=Sourced(3_000_000, Source.AREA_AVG)))
    assert p.monthly_profit < 0
    assert p.runway_months == round(p.cash_after / abs(p.monthly_profit), 1)


def test_매출이_없으면_달성률_이익_runway_시나리오를_내지_않는다():
    p = fe.plan(_inputs(expected_monthly_sales=None))
    assert p.attainment is None and p.monthly_profit is None and p.runway_months is None
    assert p.scenarios == ()
    assert p.bep_monthly_sales > 0 and p.funding_gap > 0   # 매출 무관 값은 낸다


def test_금리_스트레스는_1p_2p_두_점이고_이익이_단조_감소한다():
    p = fe.plan(_inputs())
    assert [s.rate_delta_pp for s in p.stress] == [1.0, 2.0]
    assert p.stress[0].loan_rate == 5.5 and p.stress[1].loan_rate == 6.5
    assert p.monthly_profit >= p.stress[0].monthly_profit >= p.stress[1].monthly_profit


def test_시나리오는_비관_기준_낙관_순이고_기준은_본값과_같다():
    p = fe.plan(_inputs())
    assert [s.key for s in p.scenarios] == ["pessimistic", "base", "optimistic"]
    assert p.scenarios[1].monthly_profit == p.monthly_profit
    assert p.scenarios[0].monthly_profit < p.scenarios[2].monthly_profit


def test_출처_태그와_가정_목록이_보존된다():
    p = fe.plan(_inputs(), assumptions=("이자만 반영",))
    assert p.inputs.startup_cost.source == Source.FRANCHISE
    assert p.assumptions == ("이자만 반영",)


def test_원가율이_1_이상이면_거부한다():
    import pytest
    with pytest.raises(ValueError):
        fe.plan(_inputs(cost_ratio=Sourced(1.0, Source.ASSUMED)))


def test_금액이_전부_정수로_나온다():
    p = fe.plan(_inputs(loan_rate=Sourced(4.53, Source.ECOS)))
    for v in (p.capex, p.opex_base, p.funding_gap, p.loan, p.loan_interest, p.fixed_monthly,
              p.bep_monthly_sales, p.monthly_profit, p.cash_after):
        assert isinstance(v, int)
