"""공정위 창업비용 수집기 — API 항목 → 적재 항목 매핑(순수)."""
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "collect_franchise_costs", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "collect_franchise_costs.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_합계와_단위를_읽고_합계_없는_행은_버린다():
    row = {"yr": "2024", "indutyMlsfcNm": "커피", "smtnAmt": "5,200", "avrgFntnAmt": "1,000", "crrncyUnitCdNm": "만원"}
    item = _mod.to_item("외식", row)
    assert item["year"] == 2024 and item["industryName"] == "커피" and item["totalAmount"] == 52_000_000
    assert item["deposit"] == 10_000_000 and item["raw"] is row
    assert _mod.to_item("외식", {"yr": "2024", "indutyMlsfcNm": "빈", "smtnAmt": "0"}) is None
