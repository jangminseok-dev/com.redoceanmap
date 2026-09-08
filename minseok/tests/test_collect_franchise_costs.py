"""공정위 창업비용 수집기 — 브랜드 행 → 업종별 집계(순수)."""
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "collect_franchise_costs", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "collect_franchise_costs.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _brand(name, total, fee=1000, sector="외식"):
    return {"indutyLclasNm": sector, "indutyMlsfcNm": name, "smtnAmt": total, "jngBzmnJngAmt": fee,
            "jngBzmnEduAmt": 100, "jngBzmnAssrncAmt": 100, "jngBzmnEtcAmt": total - fee - 200}


def test_업종별_중앙값과_브랜드수로_집계하고_천원을_원으로():
    rows = [_brand("치킨", t) for t in (40_000, 50_000, 60_000, 70_000, 900_000)] + [_brand("소수", 10_000)] * 2
    out = _mod.aggregate(rows, 2025)
    assert [o["industryName"] for o in out] == ["치킨"]  # 브랜드 5개 미만 업종은 제외
    chicken = out[0]
    assert chicken["totalAmount"] == 60_000 * 1_000 and chicken["brandCount"] == 5  # 중앙값(이상치 90만천원 무시)
    assert chicken["franchiseFee"] == 1_000 * 1_000 and chicken["raw"]["stat"] == "brand_median"
