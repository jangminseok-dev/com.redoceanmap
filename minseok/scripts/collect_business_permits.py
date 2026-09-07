"""지방행정 인허가 업소 수집 — 업소 단위 개업·폐업 이력을 상권에 붙인다.

기존 상권 팩트 `store`는 분기별 **점포 수**라 "지난달 어떤 가게가 새로 열었나"를 못 답한다.
이 스크립트는 업소 한 곳을 한 행으로 적재하고, 인허가일·폐업일을 그대로 들고 있어
임의 기간의 개업·폐업을 셀 수 있게 한다.

**출처가 localdata.go.kr이 아니다.** 그 호스트는 이 PC에서 TCP 443이 닿지 않는다(2026-07-30 확인).
같은 원본을 서울 열린데이터광장이 LOCALDATA_* 서비스로 제공하고, 기존 상권 수집이 쓰는
창구·키(SEOUL_OPENDATA_API_KEY)를 그대로 재사용한다. 서울 전용 서비스라 스코프도 맞다.

**상권 매칭**: 원본 X/Y가 trade_area.x_coord/y_coord와 같은 EPSG:5174라 투영 변환 없이
거리로 붙인다. 상권 폴리곤이 없어 면적에서 원으로 근사하므로(반경 = sqrt(area/pi))
경계 근처는 오차가 있다 — 2026-07-30 표본 2만건 게이트에서 매칭률 54.5%,
상위 상권이 가산디지털단지·강남역·학동사거리로 나와 유의미함을 확인했다.
반경 밖·좌표 없음은 trdar_code NULL로 남긴다(서울 전역 업소 중 상권 밖은 정상적으로 존재).

실행 (백엔드 이미지 파드 — 호스트 cron venv에는 sqlalchemy가 없다). 스케줄은 infra/k8s/overlays/prod/cronjobs/collect-business-permits.yaml(화 05:00):
    kubectl -n redocean create job --from=cronjob/collect-business-permits collect-business-permits-manual-$(date +%s)
    ... python scripts/collect_business_permits.py --dry-run          # 적재 없이 집계만
    ... python scripts/collect_business_permits.py --max-pages 5      # 부분 수집(점검용)
"""

import sys
from datetime import date, datetime
from json import loads
from math import hypot, pi, sqrt
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

# (개방서비스ID, 표시명). 제과점·노래연습장 등 다른 후보는 서비스ID가 달라 404를 냈다 —
# 늘릴 때는 반드시 1건 조회로 존재를 먼저 확인할 것.
SERVICES = [
    ("LOCALDATA_072404", "일반음식점"),
    ("LOCALDATA_072405", "휴게음식점"),  # 카페·패스트푸드 — "성수동 카페 상권"의 근거
]
PAGE_SIZE = 1000  # 서울 열린데이터광장 요청당 상한
UPSERT_CHUNK = 2000
GRID = 1000  # 매칭 격자 한 칸(m). 상권 최대 반경 885m < GRID 라 3x3 이웃이면 충분하다.

# 서울 좌표 범위(EPSG:5174) — 원본에 0이나 결측이 섞여 들어와 그대로 쓰면 엉뚱한 상권에 붙는다.
X_RANGE, Y_RANGE = (180000, 220000), (430000, 470000)


def market_url() -> str:
    url = _secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL")
    # 접두사가 빠지면 psycopg2를 찾다가 죽는다(다른 배치와 동일 규칙, 2026-07-27 회귀)
    return url.replace("postgresql://", "postgresql+psycopg://")


def fetch_page(service_id: str, page: int) -> tuple[list[dict], int]:
    key = _secrets.require("SEOUL_OPENDATA_API_KEY")
    start = (page - 1) * PAGE_SIZE + 1
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/{service_id}/{start}/{start + PAGE_SIZE - 1}/"
    with urlopen(url, timeout=120) as res:
        body = loads(res.read().decode("utf-8"))
    if service_id not in body:  # RESULT만 온 경우(쿼터 초과·서비스 오류)
        raise RuntimeError(body.get("RESULT", {}).get("MESSAGE", "알 수 없는 응답"))
    payload = body[service_id]
    return payload.get("row", []), int(payload.get("list_total_count", 0))


def parse_date(raw: str | None) -> date | None:
    """원본은 'YYYY-MM-DD' 뒤에 공백을 붙여 보내고, 없으면 빈 문자열이다."""
    text_value = (raw or "").strip()
    if not text_value:
        return None
    try:
        return datetime.strptime(text_value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_coord(raw: str | None) -> float | None:
    try:
        return float((raw or "").strip())
    except ValueError:
        return None


class AreaIndex:
    """상권 중심 좌표의 격자 인덱스 — 68만 건 × 1,650 상권 전수 비교(11억 회)를 피한다."""

    def __init__(self, rows):
        sizes = sorted(r[4] for r in rows if r[4])
        fallback = sqrt(sizes[len(sizes) // 2] / pi) if sizes else 150.0
        self._buckets: dict[tuple[int, int], list] = {}
        for code, _name, x, y, area in rows:
            radius = sqrt(area / pi) if area else fallback
            self._buckets.setdefault((x // GRID, y // GRID), []).append((code, x, y, radius))

    def match(self, x: float, y: float) -> int | None:
        """반경 안에 들어오는 상권 중 가장 가까운 것. 없으면 None."""
        bx, by = int(x // GRID), int(y // GRID)
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for code, ax, ay, radius in self._buckets.get((bx + dx, by + dy), ()):
                    distance = hypot(x - ax, y - ay)
                    if distance <= radius and (best is None or distance < best[1]):
                        best = (code, distance)
        return best[0] if best else None


def load_area_index(engine) -> AreaIndex:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT code, name, x_coord, y_coord, area_size FROM trade_area")).all()
    return AreaIndex(rows)


UPSERT = text("""
    INSERT INTO business_permits
        (service_id, mgt_no, name, category, state, permit_date, close_date,
         x_coord, y_coord, trdar_code, address, site_area)
    VALUES
        (:service_id, :mgt_no, :name, :category, :state, :permit_date, :close_date,
         :x_coord, :y_coord, :trdar_code, :address, :site_area)
    ON CONFLICT (service_id, mgt_no) DO UPDATE SET
        state = EXCLUDED.state,
        close_date = EXCLUDED.close_date,
        category = EXCLUDED.category,
        trdar_code = EXCLUDED.trdar_code
""")


def flush(engine, buffer: list[dict]) -> int:
    """청크 upsert. **같은 배치 안의 중복 키를 먼저 제거한다** — 한 INSERT에 같은
    (service_id, mgt_no)가 두 번 들어가면 PostgreSQL이
    "ON CONFLICT DO UPDATE command cannot affect row a second time"로 죽는다.
    원본에 실제로 중복이 있다(6,000건 표본에 1건). 뒤에 온 행을 남긴다."""
    deduped = {(r["service_id"], r["mgt_no"]): r for r in buffer}
    rows = list(deduped.values())
    with engine.begin() as conn:
        conn.execute(UPSERT, rows)
    return len(rows)


def to_row(service_id: str, raw: dict, index: AreaIndex) -> dict | None:
    name = (raw.get("BPLCNM") or "").strip()
    mgt_no = (raw.get("MGTNO") or "").strip()
    if not name or not mgt_no:
        return None
    x, y = parse_coord(raw.get("X")), parse_coord(raw.get("Y"))
    in_seoul = (
        x is not None and y is not None
        and X_RANGE[0] < x < X_RANGE[1] and Y_RANGE[0] < y < Y_RANGE[1]
    )
    return {
        "service_id": service_id,
        "mgt_no": mgt_no,
        "name": name[:200],
        "category": ((raw.get("UPTAENM") or "").strip() or None),
        "state": (raw.get("TRDSTATENM") or "").strip()[:20],
        "permit_date": parse_date(raw.get("APVPERMYMD")),
        "close_date": parse_date(raw.get("DCBYMD")),
        "x_coord": x if in_seoul else None,
        "y_coord": y if in_seoul else None,
        "trdar_code": index.match(x, y) if in_seoul else None,
        "address": ((raw.get("SITEWHLADDR") or "").strip()[:300] or None),
        "site_area": parse_coord(raw.get("SITEAREA")),
    }


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    max_pages = (
        int(sys.argv[sys.argv.index("--max-pages") + 1]) if "--max-pages" in sys.argv else None
    )
    stamp = f"[{datetime.now():%Y-%m-%d %H:%M:%S}]"
    print(f"{stamp} 인허가 수집 시작" + (" (dry-run)" if dry_run else ""), flush=True)

    engine = create_engine(market_url(), pool_pre_ping=True)
    index = load_area_index(engine)
    failures = fetched = saved = matched = 0

    try:
        for service_id, label in SERVICES:
            buffer: list[dict] = []
            page, total = 1, None
            while True:
                if max_pages and page > max_pages:
                    break
                try:
                    raw_rows, total = fetch_page(service_id, page)
                except Exception as e:  # 페이지 단위 실패는 건너뛰고 계속 — cron 무인 실행 전제
                    print(f"  [경고] {label} p{page} 실패({e})", flush=True)
                    failures += 1
                    page += 1
                    if total and (page - 1) * PAGE_SIZE >= total:
                        break
                    continue
                if not raw_rows:
                    break
                for raw in raw_rows:
                    row = to_row(service_id, raw, index)
                    if row is None:
                        continue
                    fetched += 1
                    if row["trdar_code"] is not None:
                        matched += 1
                    buffer.append(row)
                if not dry_run and len(buffer) >= UPSERT_CHUNK:
                    saved += flush(engine, buffer)
                    buffer = []
                if page % 50 == 0:
                    print(f"  {label} p{page} — 누적 수집 {fetched:,} / 매칭 {matched:,}", flush=True)
                if total and page * PAGE_SIZE >= total:
                    break
                page += 1
            if buffer and not dry_run:
                saved += flush(engine, buffer)
            print(f"  {label}({service_id}) 완료 — 총 {total:,}건 중 수집 {fetched:,}", flush=True)
    finally:
        engine.dispose()

    rate = matched / fetched * 100 if fetched else 0
    print(
        f"{stamp} 합계: 수집 {fetched:,} / 상권 매칭 {matched:,} ({rate:.1f}%)"
        + ("" if dry_run else f" / upsert {saved:,}")
        + (f" / 실패 {failures}건" if failures else ""),
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    # 부분 실패도 종료코드 1 — cron·감시가 실패를 관측할 수 있어야 한다.
    sys.exit(main())
