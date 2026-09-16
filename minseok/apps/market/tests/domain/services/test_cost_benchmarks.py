from market.domain.services import cost_benchmarks as cb


def test_업종명은_업종군으로_떨어지고_모르면_other():
    assert cb.benchmark_for("커피-음료").group == "cafe"
    assert cb.benchmark_for("한식음식점").group == "food"
    assert cb.benchmark_for("호프-간이주점").group == "pub"
    assert cb.benchmark_for("편의점").group == "retail"
    assert cb.benchmark_for("미용실").group == "service"
    assert cb.benchmark_for("일반교습학원").group == "education"
    assert cb.benchmark_for("의약품").group == "other"


def test_모든_원가율은_0과_1_사이고_출처가_있다():
    for b in cb.COST_BENCHMARKS.values():
        assert 0.0 < b.cost_ratio < 1.0
        assert 0.0 < b.margin_ratio < 1.0
        assert b.source


def test_인건비는_최저임금_209시간_인원():
    assert cb.monthly_payroll(0) == 0
    assert cb.monthly_payroll(2) == cb.MIN_WAGE_HOURLY_2026 * cb.MONTHLY_HOURS * 2
