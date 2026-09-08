"""공정위 가맹정보 브랜드별 창업금액 → 업종별 창업비용 집계 — data.go.kr(1130000/FftcBrandFntnStatsService) → 허브 /automation/franchise-costs.

브랜드 1만 1천여 건(정보공개서, 단위 천원)을 받아 업종 중분류별 **중앙값**(total_amount)·평균·브랜드 수로 집계한다.
업종별 API(FftcSclasIndutyFntnStatsService)는 값의 정의·단위가 불명확해(2026-09-08 실측: 치킨 1,207 — 브랜드 평균
58,929천원과 배율이 업종마다 다름) 쓰지 않는다. 가맹금·교육비·보증금·기타(인테리어 등)의 합계이고 점포 임대료는 없다.
키는 DATA_GO_KR_API_KEY(개인 발급) + 포털 활용신청(15110265).

실행:
    python scripts/collect_franchise_costs.py            # 올해(없으면 작년)
    python scripts/collect_franchise_costs.py 2024       # 연도 지정
    python scripts/collect_franchise_costs.py --dry-run  # 집계 결과만 출력

k3s CronJob collect-franchise-costs(매월 1일 03:30). 정보공개서는 연 1회 갱신이라 월 1회면 충분하다.
"""
from __future__ import annotations

import statistics
import sys
from collections import defaultdict
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

BRAND_URL = "https://apis.data.go.kr/1130000/FftcBrandFntnStatsService/getBrandFntnStats"
UNIT = 1_000  # 정보공개서 금액 단위: 천원
PAGE = 500
MIN_BRANDS = 5  # 이보다 적은 업종은 대표성이 없어 적재하지 않는다


def _num(v) -> float | None:
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def aggregate(rows: list[dict], year: int) -> list[dict]:
    """브랜드 행 → 업종(대분류·중분류)별 집계. total_amount는 중앙값(이상치에 강함), 평균·표본은 raw에."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        total = _num(r.get("smtnAmt"))
        name = str(r.get("indutyMlsfcNm", "") or "").strip()
        sector = str(r.get("indutyLclasNm", "") or "").strip()[:8]
        if total is None or not name or not sector:
            continue
        groups[(sector, name)].append(r)
    out = []
    for (sector, name), items in groups.items():
        if len(items) < MIN_BRANDS:
            continue
        totals = [_num(i["smtnAmt"]) for i in items]

        def mean_of(key: str) -> int:
            vals = [v for v in (_num(i.get(key)) for i in items) if v is not None]
            return int(round(statistics.mean(vals) * UNIT)) if vals else 0

        out.append({
            "year": year, "sector": sector, "industryName": name,
            "franchiseFee": mean_of("jngBzmnJngAmt"), "educationFee": mean_of("jngBzmnEduAmt"),
            "deposit": mean_of("jngBzmnAssrncAmt"), "otherFee": mean_of("jngBzmnEtcAmt"),
            "totalAmount": int(round(statistics.median(totals) * UNIT)),
            "brandCount": len(items),
            "raw": {"mean_total": int(round(statistics.mean(totals) * UNIT)), "unit": "천원→원",
                    "stat": "brand_median", "source": "FftcBrandFntnStatsService.getBrandFntnStats"},
        })
    out.sort(key=lambda x: x["totalAmount"])
    return out


def fetch_brands(year: int) -> list[dict]:
    items, page = [], 1
    while True:
        res = requests.get(BRAND_URL, params={
            "serviceKey": API_KEY, "pageNo": page, "numOfRows": PAGE, "resultType": "json", "yr": year,
        }, headers={"User-Agent": "Mozilla/5.0 (redoceanmap collector)"}, timeout=60)
        if res.status_code != 200:
            # URL에 serviceKey가 들어 있다 — 예외 메시지(URL 포함)를 그대로 찍지 않는다(비밀값 로그 금지)
            try:
                reason = res.json()["OpenAPI_ServiceResponse"]["cmmMsgHeader"].get("returnAuthMsg", "")
            except Exception:
                reason = ""
            raise RuntimeError(f"HTTP {res.status_code} {reason}".strip())
        body = res.json()
        rows = body.get("items", []) or []
        if isinstance(rows, dict):
            rows = rows.get("item", []) or []
        items.extend(rows)
        total = int(body.get("totalCount", 0) or 0)
        if page * PAGE >= total or not rows:
            break
        page += 1
    return items


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    years = [int(a) for a in args] or [date.today().year, date.today().year - 1]
    for year in years:
        try:
            brands = fetch_brands(year)
        except Exception as e:
            print(f"  [경고] {year} 브랜드 목록 실패: {e}")
            continue
        payload = aggregate(brands, year)
        print(f"{year}: 브랜드 {len(brands)}건 → 업종 {len(payload)}개")
        if not payload:
            continue
        if dry:
            for row in payload[:12]:
                print(f"  {row['sector']} {row['industryName']}: 중앙 {row['totalAmount'] // 10_000:,}만원 · 브랜드 {row['brandCount']}")
            return 0
        res = requests.post(f"{HUB_URL}/automation/franchise-costs", json={"items": payload}, headers=HEADERS, timeout=120)
        res.raise_for_status()
        print(f"허브 적재: {res.json()}")
        return 0  # 첫 성공 연도만 적재(올해 자료가 있으면 작년은 건너뛴다)
    return 1


if __name__ == "__main__":
    sys.exit(main())
