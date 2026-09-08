"""공정위 가맹정보 업종별 창업비용 수집 — data.go.kr(1130000/FftcSclasIndutyFntnStatsService) → 허브 /automation/franchise-costs.

외식·도소매·서비스 3개 오퍼레이션을 연도별로 전부 받아 (연도·부문·업종) 단위로 교체 적재한다.
정보공개서 평균이라 가맹금·교육비·보증금·기타의 합계이고 점포 임대료·인테리어는 없다.
키는 DATA_GO_KR_API_KEY(개인 발급) — 단, 이 서비스는 포털에서 **활용신청**이 돼 있어야 한다
(미신청이면 SERVICE_KEY_IS_NOT_REGISTERED_ERROR — 서류 없이 클릭 승인).

실행:
    python scripts/collect_franchise_costs.py            # 작년·올해
    python scripts/collect_franchise_costs.py 2023 2024  # 연도 지정
    python scripts/collect_franchise_costs.py --dry-run  # 호출 결과만 출력

k3s CronJob collect-franchise-costs(매월 1일 03:30). 정보공개서는 연 1회 갱신이라 월 1회면 충분하다.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()
HUB_URL = _secrets.get("HUB_URL", "http://localhost:8000")
HEADERS = {"X-Webhook-Token": _secrets.get("N8N_INBOUND_TOKEN")}
API_KEY = _secrets.get("DATA_GO_KR_API_KEY")

BASE = "https://apis.data.go.kr/1130000/FftcSclasIndutyFntnStatsService"
OPERATIONS = (("외식", "getSclaIndutyFntnOutStats"), ("도소매", "getSclaIndutyFntnWhrtStats"), ("서비스", "getSclaIndutyFntnSrvcStats"))
UNIT_MULTIPLIER = {"원": 1, "천원": 1_000, "만원": 10_000, "백만원": 1_000_000}
PAGE = 100


def _amount(raw: dict, key: str, unit: int) -> int:
    try:
        return int(round(float(str(raw.get(key, "0") or "0").replace(",", "")) * unit))
    except ValueError:
        return 0


def to_item(sector: str, raw: dict) -> dict | None:
    """API 항목 1건 → 허브 적재 항목. 합계가 없으면 None.

    필드 설명이 문서와 어긋나는 사례가 있어(스웨거의 frcsCnt='평균가맹금액' 등) 합계(smtnAmt)를
    정본으로 삼고 원본은 raw로 함께 보낸다 — 나중에 화면이 세부 항목을 검산할 수 있게.
    """
    unit = UNIT_MULTIPLIER.get(str(raw.get("crrncyUnitCdNm", "") or "").strip(), 1)
    total = _amount(raw, "smtnAmt", unit)
    name = str(raw.get("indutyMlsfcNm", "") or "").strip()
    year = str(raw.get("yr", "") or "").strip()
    if total <= 0 or not name or not year.isdigit():
        return None
    return {
        "year": int(year), "sector": sector, "industryName": name,
        "franchiseFee": _amount(raw, "frcsCnt", unit), "educationFee": _amount(raw, "avrgFrcsAmt", unit),
        "deposit": _amount(raw, "avrgFntnAmt", unit), "otherFee": _amount(raw, "avrgJngEtcAmt", unit),
        "totalAmount": total, "brandCount": None, "raw": raw,
    }


def fetch(sector: str, op: str, year: int) -> list[dict]:
    items, page = [], 1
    while True:
        res = requests.get(f"{BASE}/{op}", params={
            "serviceKey": API_KEY, "pageNo": page, "numOfRows": PAGE, "resultType": "json", "yr": year,
        }, timeout=30)
        res.raise_for_status()
        body = res.json()
        if "OpenAPI_ServiceResponse" in body:  # 포털 게이트웨이 오류(키 미등록 등)
            raise RuntimeError(body["OpenAPI_ServiceResponse"]["cmmMsgHeader"].get("returnAuthMsg", "포털 오류"))
        rows = body.get("items", []) or []
        if isinstance(rows, dict):
            rows = rows.get("item", []) or []
        items.extend(rows)
        total = int(body.get("totalCount", 0) or 0)
        if page * PAGE >= total or not rows:
            break
        page += 1
    return [i for i in (to_item(sector, r) for r in items) if i]


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    years = [int(a) for a in args] or [date.today().year - 1, date.today().year]
    payload, failures = [], 0
    for year in years:
        for sector, op in OPERATIONS:
            try:
                rows = fetch(sector, op, year)
                print(f"{year} {sector}: {len(rows)}건")
                payload.extend(rows)
            except Exception as e:
                print(f"  [경고] {year} {sector} 실패: {e}")
                failures += 1
    if dry or not payload:
        print(f"적재 대상 {len(payload)}건 (dry-run={dry})")
        return 1 if failures and not payload else 0
    res = requests.post(f"{HUB_URL}/automation/franchise-costs", json={"items": payload}, headers=HEADERS, timeout=120)
    res.raise_for_status()
    print(f"허브 적재: {res.json()}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
