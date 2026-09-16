# 창업 재무 엔진 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "성수동 카페, 내 돈 1억이면 몇 달 버티고 얼마가 모자라나"를 채팅이 결정론 계산으로 답한다 — R-ONE 임대료·ECOS 금리 적재 + market 재무 엔진 + chat 재무 경로.

**Architecture:** market 스포크가 임대료·금리 팩트와 순수 도메인 엔진(`finance_engine`)·슬라이스 `area_finance`를 소유하고, 허브 포트 `AreaFinancePort`로 chat에 노출한다. chat은 결정론 금액 파서로 입력을 뽑고 이력·프로파일·상권 평균·공정위·가정 순으로 빈 값을 채운 뒤 첫 줄을 코드로 쓰고 LLM에는 해석만 맡긴다.

**Tech Stack:** Python 3.13 · FastAPI · SQLAlchemy 2 async · Alembic(market 체인) · pytest-asyncio(auto) · 도커 경유 테스트(호스트에 파이썬 없음).

**Spec:** `minseok/_docs/FINANCE_ENGINE_2026-09-16.md`

## Global Constraints

- 스포크끼리 직접 import 금지(chat↔market). 교차는 `hub` 포트만. `hub`는 스포크를 import하지 않는다.
- `market.domain`·`chat.domain`은 pydantic·sqlalchemy·fastapi를 import하지 않는다(import-linter 계약 5종).
- 슬라이스 1:1: 라우터·스키마·DTO·입력포트·출력포트·인터랙터·프로바이더·테스트 각 1개. market에 `/myself`를 추가하지 않는다(`tests/test_public_routes.py`가 "market 자기소개 1개" 고정).
- 새 라우터는 `main.py`에서 `dependencies=_authenticated`로 등록한다(빠뜨리면 공개 라우트가 되어 `test_화이트리스트_밖의_경로는_모두_인증을_요구한다`가 실패).
- 금액은 전부 원(int). 매출은 분기 원본을 월로 환산한 `sales_per_store`(이미 ÷3 적용됨)를 쓴다.
- `load_dotenv`·`os.getenv` 신규 사용 금지 — 스크립트는 `core.key.secret_manager.get_secret_manager()`, 런타임은 `core/config.py`.
- 주석·문서·커밋 메시지는 한국어. 커밋 형식 `type(scope): 요약`. **커밋은 사용자가 요청할 때만** — 아래 "커밋 경계"는 메시지를 준비해 두는 지점이다.
- 테스트 실행(맥, 도커 경유). 두 방법 중 하나:
  - MCP 도구 `mcp__redoceanmap-tools__run_backend_tests` — `target`에 `minseok/...` 경로, `skip_integration=true`.
  - 셸: `docker run --rm -v /Users/jangminseok/Project/com.redoceanmap:/work -w /work -e PYTHONPATH=/work/minseok:/work/minseok/apps minseok97/redoceanmap-backend:latest python -m pytest <target> -q -p no:cacheprovider -m "not ollama and not network"`
- 구조 검사: MCP `mcp__redoceanmap-tools__run_import_linter` (또는 `docker run ... -w /work/minseok -e PYTHONPATH=apps minseok97/redoceanmap-backend:latest lint-imports --config .importlinter`). 계약 5종 KEPT가 통과 기준.
- market 전용 DB는 `MARKET_DATABASE_URL`(호스트 :5434). **market 체인은 파드 기동 시 자동 적용되지 않는다**(파드는 기본 `alembic.ini` 공유 DB 체인만 돌린다) — 배포 시 `alembic -c apps/market/alembic.ini upgrade head`를 수동 실행. 맥 로컬 검증은 같은 명령을 도커 `--network host`로 돌린다.

---

## 파일 구조

| 구분 | 파일 | 책임 |
|---|---|---|
| ORM | `minseok/apps/market/adapter/outbound/orm/rent_benchmark_orm.py` | `rent_benchmarks` 테이블 |
| ORM | `minseok/apps/market/adapter/outbound/orm/interest_rate_orm.py` | `interest_rates` 테이블 |
| 마이그레이션 | `minseok/apps/market/alembic/versions/f5a6b7c8d9e0_add_rent_benchmarks_interest_rates.py` | 두 테이블 생성 |
| 스크립트 | `minseok/scripts/collect_rone_rent.py` · `minseok/scripts/collect_ecos_rates.py` | 적재 (순수 파싱 함수 + main) |
| cron | `infra/k8s/overlays/prod/cronjobs/collect-rone-rent.yaml` · `collect-ecos-rates.yaml` | 분기 1회 · 월 1회 |
| 도메인 VO | `minseok/apps/market/domain/value_objects/finance_vo.py` | Source·Sourced·FinanceInputs·FinancePlan·RentBenchmark |
| 도메인 | `minseok/apps/market/domain/services/cost_benchmarks.py` | 원가율 상수·업종군 매핑·최저임금 |
| 도메인 | `minseok/apps/market/domain/services/finance_engine.py` | 산식 |
| 도메인 | `minseok/apps/market/domain/services/rent_matcher.py` | 상권명→R-ONE 상권, 자치구→권역 |
| 도메인 | `minseok/apps/market/domain/services/finance_narrator.py` | 첫 줄 문장·가정 문장 |
| 슬라이스 | `minseok/apps/market/app/dtos/area_finance_dto.py` · `app/ports/input/area_finance_use_case.py` · `app/ports/output/area_finance_repository.py` · `app/use_cases/area_finance_interactor.py` · `adapter/outbound/pg/area_finance_pg_repository.py` · `adapter/inbound/api/schemas/area_finance_schema.py` · `adapter/inbound/api/v1/area_finance_router.py` · `dependencies/area_finance_provider.py` | `GET /market/trdar/{code}/finance` |
| 허브 | `minseok/apps/hub/app/dtos/area_finance_dto.py` · `hub/app/ports/output/area_finance_port.py` · `hub/dependencies/area_finance_provider.py` | 계약 |
| 게이트웨이 | `minseok/apps/market/adapter/outbound/gateways/area_finance_gateway.py` | 허브 포트 구현 |
| chat | `minseok/apps/chat/domain/services/amount_parser.py` | 금액·라벨 파서(기존 `parse_budget_krw`·`fmt_won` 이관) |
| chat | `minseok/apps/chat/app/use_cases/chat_interactor.py` · `app/dtos/chat_dto.py` · `dependencies/chat_provider.py` | 재무 경로·카드 |
| 평가 | `minseok/apps/chat/tests/eval/golden_set.jsonl` · `snapshot_stubs.py` · `test_eval_runner.py` · `domain/services/eval_scorer.py` · `tests/eval/test_quality_gate.py` | 골든셋 10문항·지표 |
| 문서 | market/chat/hub CLAUDE · ROADMAP · 스펙 상태 | |

---

### Task 1: 테이블 2종 — ORM + 마이그레이션

**Files:**
- Create: `minseok/apps/market/adapter/outbound/orm/rent_benchmark_orm.py`
- Create: `minseok/apps/market/adapter/outbound/orm/interest_rate_orm.py`
- Create: `minseok/apps/market/alembic/versions/f5a6b7c8d9e0_add_rent_benchmarks_interest_rates.py`
- Modify: `minseok/apps/market/alembic/env.py:55` (ORM import 등록 2줄 추가)

**Interfaces:**
- Produces: `RentBenchmarkOrm(building_type, year_quarter, cls_id, cls_fullnm, level, region_name, rent_per_sqm_krw, vacancy_rate)`, `InterestRateOrm(stat_code, item_name, year_month, rate)`.

- [ ] **Step 1: ORM 2개 작성**

```python
# minseok/apps/market/adapter/outbound/orm/rent_benchmark_orm.py
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class RentBenchmarkOrm(Base):
    """한국부동산원 R-ONE 상가 임대동향 — 서울 상권·권역·시 단위 임대료(원/㎡·월)와 공실률(%).

    R-ONE 상권은 서울에 59곳뿐이라 우리 trade_area 1,650곳 대부분은 권역(level 1) 평균으로
    폴백한다(rent_matcher). 적재는 scripts/collect_rone_rent.py — (building_type, year_quarter, cls_id) upsert.
    """

    __tablename__ = "rent_benchmarks"
    __table_args__ = (
        UniqueConstraint("building_type", "year_quarter", "cls_id", name="uq_rent_benchmarks_type_quarter_cls"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    building_type: Mapped[str] = mapped_column(String(16))  # small | medium_large | aggregate
    year_quarter: Mapped[int] = mapped_column(Integer, index=True)  # 20243 형식
    cls_id: Mapped[str] = mapped_column(String(16))  # R-ONE CLS_ID
    cls_fullnm: Mapped[str] = mapped_column(String(80))  # "서울>기타>혜화동"
    level: Mapped[int] = mapped_column(Integer)  # 0 시 · 1 권역 · 2 상권
    region_name: Mapped[str] = mapped_column(String(40), index=True)  # 마지막 계층명
    rent_per_sqm_krw: Mapped[int] = mapped_column(Integer)
    vacancy_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

```python
# minseok/apps/market/adapter/outbound/orm/interest_rate_orm.py
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class InterestRateOrm(Base):
    """한국은행 ECOS 금리 — 기준금리(722Y001)·예금은행 대출금리(121Y006), 월 단위(연 %).

    전국 값이라 상권 매칭이 없다. 유일 소비처가 market 재무 엔진이라 market 전용 DB에 둔다.
    적재는 scripts/collect_ecos_rates.py — (stat_code, item_name, year_month) upsert.
    """

    __tablename__ = "interest_rates"
    __table_args__ = (
        UniqueConstraint("stat_code", "item_name", "year_month", name="uq_interest_rates_stat_item_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stat_code: Mapped[str] = mapped_column(String(16))
    item_name: Mapped[str] = mapped_column(String(60))  # "한국은행 기준금리" · "대출평균" · "기업대출"
    year_month: Mapped[int] = mapped_column(Integer, index=True)  # 202508
    rate: Mapped[float] = mapped_column(Float)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: 마이그레이션 작성**

```python
# minseok/apps/market/alembic/versions/f5a6b7c8d9e0_add_rent_benchmarks_interest_rates.py
"""add rent_benchmarks + interest_rates (창업 재무 엔진 — 비용·손익 축)

R-ONE 상가 임대료·공실률(서울 64 CLS × 분기)과 ECOS 금리(월)를 market 전용 DB에 둔다.
임대료는 상권 59곳뿐이라 권역 평균 폴백이 기본이다(FINANCE_ENGINE_2026-09-16).

Revision ID: f5a6b7c8d9e0
Revises: e9a1b2c3d4e5
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e9a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rent_benchmarks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("building_type", sa.String(16), nullable=False),
        sa.Column("year_quarter", sa.Integer(), nullable=False),
        sa.Column("cls_id", sa.String(16), nullable=False),
        sa.Column("cls_fullnm", sa.String(80), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("region_name", sa.String(40), nullable=False),
        sa.Column("rent_per_sqm_krw", sa.Integer(), nullable=False),
        sa.Column("vacancy_rate", sa.Float(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("building_type", "year_quarter", "cls_id", name="uq_rent_benchmarks_type_quarter_cls"),
    )
    op.create_index("ix_rent_benchmarks_year_quarter", "rent_benchmarks", ["year_quarter"])
    op.create_index("ix_rent_benchmarks_region_name", "rent_benchmarks", ["region_name"])
    op.create_table(
        "interest_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stat_code", sa.String(16), nullable=False),
        sa.Column("item_name", sa.String(60), nullable=False),
        sa.Column("year_month", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("stat_code", "item_name", "year_month", name="uq_interest_rates_stat_item_month"),
    )
    op.create_index("ix_interest_rates_year_month", "interest_rates", ["year_month"])


def downgrade() -> None:
    op.drop_index("ix_interest_rates_year_month", table_name="interest_rates")
    op.drop_table("interest_rates")
    op.drop_index("ix_rent_benchmarks_region_name", table_name="rent_benchmarks")
    op.drop_index("ix_rent_benchmarks_year_quarter", table_name="rent_benchmarks")
    op.drop_table("rent_benchmarks")
```

- [ ] **Step 3: env.py에 ORM 등록** — `minseok/apps/market/alembic/env.py` 55행(`franchise_industry_cost_orm` import) 아래에 두 줄 추가:

```python
import market.adapter.outbound.orm.rent_benchmark_orm  # noqa: F401
import market.adapter.outbound.orm.interest_rate_orm  # noqa: F401
```

- [ ] **Step 4: import 검증(DB 불요)**

Run:
```bash
docker run --rm -v /Users/jangminseok/Project/com.redoceanmap:/work -w /work/minseok -e PYTHONPATH=/work/minseok:/work/minseok/apps minseok97/redoceanmap-backend:latest python -c "import market.adapter.outbound.orm.rent_benchmark_orm, market.adapter.outbound.orm.interest_rate_orm; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: 마이그레이션 실적용(market DB가 떠 있을 때)**

Run:
```bash
docker run --rm --network host -v /Users/jangminseok/Project/com.redoceanmap:/work -w /work/minseok -e PYTHONPATH=/work/minseok:/work/minseok/apps minseok97/redoceanmap-backend:latest alembic -c apps/market/alembic.ini upgrade head
docker exec market-pgvector psql -U market -d market -c "\d rent_benchmarks" | head -5
```
Expected: `Running upgrade e9a1b2c3d4e5 -> f5a6b7c8d9e0` · 테이블 컬럼 출력. DB가 없으면 이 단계는 백엔드 PC 배포 시 자동 적용된다고 기록하고 넘어간다.

- [ ] **커밋 경계**: `feat(market): rent_benchmarks·interest_rates 테이블 — R-ONE 임대료·ECOS 금리 팩트`

---

### Task 2: 수집 스크립트 2종 + 설정 키 + cron

**Files:**
- Create: `minseok/scripts/collect_rone_rent.py`, `minseok/scripts/collect_ecos_rates.py`
- Create: `minseok/tests/test_collect_rone_rent.py`, `minseok/tests/test_collect_ecos_rates.py`
- Create: `infra/k8s/overlays/prod/cronjobs/collect-rone-rent.yaml`, `infra/k8s/overlays/prod/cronjobs/collect-ecos-rates.yaml`
- Modify: `infra/k8s/overlays/prod/cronjobs/kustomization.yaml` (resources 2줄), `.env.example:30` 아래, `minseok/core/config.py:110` 아래

**Interfaces:**
- Produces: `rent_benchmarks`·`interest_rates` 실데이터. 순수 함수 `parse_quarter(str)->int`, `merge_rows(building_type, rent_rows, vacancy_rows)->list[dict]`, `normalize_item(str)->str`.

- [ ] **Step 1: 설정 키** — `.env.example` 30행(`DATA_GO_KR_API_KEY=`) 아래에 추가:

```bash

# 한국부동산원 R-ONE (www.reb.or.kr/r-one) — 상가 임대료·공실률(scripts/collect_rone_rent.py)
RONE_API_KEY=
# 한국은행 ECOS (ecos.bok.or.kr) — 기준금리·대출금리(scripts/collect_ecos_rates.py)
ECOS_API_KEY=
```

`minseok/core/config.py` 110행(`GEMINI_MODEL = ...`) 아래에 추가:

```python
# 창업 재무 엔진 외부 데이터(적재 스크립트가 secret_manager로 직접 읽는다 — 런타임 참조용 상수).
RONE_API_KEY = _secrets.get("RONE_API_KEY")
ECOS_API_KEY = _secrets.get("ECOS_API_KEY")
```

- [ ] **Step 2: 실패 테스트 — R-ONE 파싱**

```python
# minseok/tests/test_collect_rone_rent.py
"""collect_rone_rent 순수 함수 — 분기 코드 변환·임대료/공실률 병합(네트워크·DB 없음)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "collect_rone_rent", Path(__file__).resolve().parents[1] / "scripts" / "collect_rone_rent.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_분기_코드는_연도와_분기를_붙인다():
    assert _mod.parse_quarter("202403") == 20243
    assert _mod.parse_quarter("202601") == 20261


def _row(cls_id, fullnm, val, quarter="202602"):
    return {"WRTTIME_IDTFR_ID": quarter, "CLS_ID": cls_id, "CLS_FULLNM": fullnm, "DTA_VAL": val}


def test_임대료와_공실률을_같은_키로_병합하고_서울만_남긴다():
    rent = [_row("520059", "서울>기타>혜화동", "60.03"), _row("510003", "서울>도심", "74.11"),
            _row("500002", "서울", "52.8"), _row("600001", "부산>기타>서면", "30.0")]
    vacancy = [_row("520059", "서울>기타>혜화동", "2.13")]
    rows = _mod.merge_rows("small", rent, vacancy)
    by_cls = {r["cls_id"]: r for r in rows}
    assert set(by_cls) == {"520059", "510003", "500002"}
    assert by_cls["520059"]["rent_per_sqm_krw"] == 60_030  # 천원/㎡ → 원/㎡
    assert by_cls["520059"]["vacancy_rate"] == 2.13
    assert by_cls["520059"]["level"] == 2 and by_cls["520059"]["region_name"] == "혜화동"
    assert by_cls["510003"]["level"] == 1 and by_cls["510003"]["vacancy_rate"] is None
    assert by_cls["500002"]["level"] == 0 and by_cls["500002"]["region_name"] == "서울"
    assert all(r["year_quarter"] == 20262 and r["building_type"] == "small" for r in rows)
```

- [ ] **Step 3: 실패 확인**

Run: `mcp run_backend_tests target=minseok/tests/test_collect_rone_rent.py` (또는 도커 셸 명령)
Expected: FAIL — `FileNotFoundError`(스크립트 없음)

- [ ] **Step 4: R-ONE 스크립트 작성**

```python
# minseok/scripts/collect_rone_rent.py
"""한국부동산원 R-ONE 상가 임대동향 수집 — 서울 상권·권역·시 임대료(원/㎡·월)·공실률(%) → rent_benchmarks.

창업 재무 엔진(FINANCE_ENGINE_2026-09-16)의 월세 기본값 원천. 표는 2024년 3분기~ 빈티지만 쓴다
(옛 빈티지는 불연속이라 지수화 소비처가 생길 때까지 미적재). 서울 64 CLS(시 1·권역 4·상권 59) × 분기.

멱등 규칙: (building_type, year_quarter, cls_id) upsert — 재실행 안전.

실행 (백엔드 이미지 파드 — 호스트 cron venv에는 sqlalchemy가 없다):
    kubectl -n redocean exec deploy/backend -- python scripts/collect_rone_rent.py            # 전 분기
    ... python scripts/collect_rone_rent.py --dry-run                                         # 적재 없이 집계만

스케줄(분기 첫 달 10일 05:00 — R-ONE 공표는 분기 종료 후 약 1개월):
    infra/k8s/overlays/prod/cronjobs/collect-rone-rent.yaml
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

API_URL = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
PAGE_SIZE = 1000
# 건물유형 → (임대료 표, 공실률 표) — 2024년 3분기~ 빈티지(2026-09-16 SttsApiTbl 실측)
TABLES = {
    "small": ("T248223134698125", "T241833134686576"),
    "medium_large": ("T244363134858603", "T249633134845544"),
    "aggregate": ("T244913134948657", "T243283134931290"),
}


def market_url() -> str:
    url = _secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL")
    return url.replace("postgresql://", "postgresql+psycopg://")


def parse_quarter(wrttime: str) -> int:
    """R-ONE `WRTTIME_IDTFR_ID` "202403"(연+0+분기) → 20243."""
    return int(wrttime[:4]) * 10 + int(wrttime[5])


def fetch_table(statbl_id: str) -> list[dict]:
    key = _secrets.require("RONE_API_KEY")
    rows: list[dict] = []
    page = 1
    while True:
        url = (f"{API_URL}?STATBL_ID={statbl_id}&DTACYCLE_CD=QY&KEY={key}&Type=json"
               f"&pIndex={page}&pSize={PAGE_SIZE}")
        with urlopen(url, timeout=60) as res:
            body = json.loads(res.read().decode("utf-8"))
        blocks = body.get("SttsApiTblData", [])
        head = next((b["head"] for b in blocks if "head" in b), [])
        result = next((h["RESULT"] for h in head if "RESULT" in h), {})
        if result.get("CODE") not in ("INFO-000", None):
            raise RuntimeError(f"{statbl_id}: {result}")
        page_rows = next((b["row"] for b in blocks if "row" in b), [])
        rows.extend(page_rows)
        total = next((h["list_total_count"] for h in head if "list_total_count" in h), 0)
        if page * PAGE_SIZE >= total or not page_rows:
            return rows
        page += 1


def merge_rows(building_type: str, rent_rows: list[dict], vacancy_rows: list[dict]) -> list[dict]:
    """서울 행만 남기고 임대료·공실률을 (분기, CLS)로 병합. 임대료 천원/㎡ → 원/㎡."""
    merged: dict[tuple[int, str], dict] = {}
    for r in rent_rows:
        fullnm = str(r.get("CLS_FULLNM", ""))
        if not fullnm.startswith("서울"):
            continue
        parts = fullnm.split(">")
        key = (parse_quarter(r["WRTTIME_IDTFR_ID"]), str(r["CLS_ID"]))
        merged[key] = {
            "building_type": building_type,
            "year_quarter": key[0],
            "cls_id": key[1],
            "cls_fullnm": fullnm,
            "level": len(parts) - 1,
            "region_name": parts[-1],
            "rent_per_sqm_krw": int(round(float(r["DTA_VAL"]) * 1000)),
            "vacancy_rate": None,
        }
    for r in vacancy_rows:
        key = (parse_quarter(r["WRTTIME_IDTFR_ID"]), str(r["CLS_ID"]))
        if key in merged:
            merged[key]["vacancy_rate"] = round(float(r["DTA_VAL"]), 2)
    return list(merged.values())


def upsert(conn, rows: list[dict]) -> None:
    conn.execute(text(
        "INSERT INTO rent_benchmarks (building_type, year_quarter, cls_id, cls_fullnm, level, "
        "region_name, rent_per_sqm_krw, vacancy_rate) "
        "VALUES (:building_type, :year_quarter, :cls_id, :cls_fullnm, :level, :region_name, "
        ":rent_per_sqm_krw, :vacancy_rate) "
        "ON CONFLICT (building_type, year_quarter, cls_id) DO UPDATE SET "
        "cls_fullnm = EXCLUDED.cls_fullnm, level = EXCLUDED.level, region_name = EXCLUDED.region_name, "
        "rent_per_sqm_krw = EXCLUDED.rent_per_sqm_krw, "
        "vacancy_rate = COALESCE(EXCLUDED.vacancy_rate, rent_benchmarks.vacancy_rate), "
        "collected_at = now()"
    ), rows)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] R-ONE 수집 시작 — 건물유형 {len(TABLES)}종", flush=True)
    engine = None if dry_run else create_engine(market_url())
    total = failures = 0
    for building_type, (rent_id, vacancy_id) in TABLES.items():
        try:
            rows = merge_rows(building_type, fetch_table(rent_id), fetch_table(vacancy_id))
        except Exception as e:
            print(f"  [경고] {building_type} 실패({e}) — 계속", flush=True)
            failures += 1
            continue
        quarters = sorted({r["year_quarter"] for r in rows})
        print(f"{building_type}: {len(rows)}행 (분기 {quarters[:1]}~{quarters[-1:]})", flush=True)
        total += len(rows)
        if not dry_run and rows:
            with engine.begin() as conn:
                upsert(conn, rows)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 합계 {total}행"
          + (" (dry-run — 적재 생략)" if dry_run else "")
          + (f" / 실패 {failures}종" if failures else ""), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 통과 확인**

Run: `mcp run_backend_tests target=minseok/tests/test_collect_rone_rent.py`
Expected: 2 passed

- [ ] **Step 6: 실패 테스트 — ECOS 파싱**

```python
# minseok/tests/test_collect_ecos_rates.py
"""collect_ecos_rates 순수 함수 — 항목명 정규화·행 변환(네트워크·DB 없음)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "collect_ecos_rates", Path(__file__).resolve().parents[1] / "scripts" / "collect_ecos_rates.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_각주_번호를_뗀_항목명으로_정규화한다():
    assert _mod.normalize_item("대출평균 1)") == "대출평균"
    assert _mod.normalize_item("한국은행 기준금리") == "한국은행 기준금리"


def test_관심_항목만_행으로_바꾼다():
    raw = [
        {"STAT_CODE": "121Y006", "ITEM_NAME1": "대출평균 1)", "TIME": "202508", "DATA_VALUE": "4.53"},
        {"STAT_CODE": "121Y006", "ITEM_NAME1": "대기업대출", "TIME": "202508", "DATA_VALUE": "4.48"},
        {"STAT_CODE": "722Y001", "ITEM_NAME1": "한국은행 기준금리", "TIME": "202508", "DATA_VALUE": "2.5"},
        {"STAT_CODE": "722Y001", "ITEM_NAME1": "정부대출금금리", "TIME": "202508", "DATA_VALUE": "3.0"},
    ]
    rows = _mod.to_rows(raw)
    assert [(r["stat_code"], r["item_name"], r["year_month"], r["rate"]) for r in rows] == [
        ("121Y006", "대출평균", 202508, 4.53),
        ("722Y001", "한국은행 기준금리", 202508, 2.5),
    ]
```

- [ ] **Step 7: ECOS 스크립트 작성**

```python
# minseok/scripts/collect_ecos_rates.py
"""한국은행 ECOS 금리 수집 — 기준금리(722Y001)·예금은행 대출금리(121Y006) 월별 → interest_rates.

창업 재무 엔진의 이자 계산 원천(대출평균). 전국 값이라 상권 매칭이 없다.
멱등 규칙: (stat_code, item_name, year_month) upsert. 기본 실행은 최근 REFRESH_MONTHS(3)개월 재수집.

실행 (백엔드 이미지 파드):
    kubectl -n redocean exec deploy/backend -- python scripts/collect_ecos_rates.py            # 최근 3개월
    ... python scripts/collect_ecos_rates.py --from 202001                                    # 백필
    ... python scripts/collect_ecos_rates.py --dry-run

스케줄(매월 15일 04:00 — 한은 공표 뒤):
    infra/k8s/overlays/prod/cronjobs/collect-ecos-rates.yaml
"""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

API_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
REFRESH_MONTHS = 3
# 통계코드 → 남길 항목명(정규화 후). 기업대출은 소상공인 근사치 후보로 같이 둔다.
WANTED = {
    "722Y001": ("한국은행 기준금리",),
    "121Y006": ("대출평균", "기업대출"),
}
_FOOTNOTE = re.compile(r"\s*\d\)\s*$")


def market_url() -> str:
    url = _secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL")
    return url.replace("postgresql://", "postgresql+psycopg://")


def normalize_item(name: str) -> str:
    """"대출평균 1)" → "대출평균" (ECOS 각주 번호 제거)."""
    return _FOOTNOTE.sub("", name).strip()


def to_rows(raw: list[dict]) -> list[dict]:
    out = []
    for r in raw:
        code = r.get("STAT_CODE", "")
        item = normalize_item(r.get("ITEM_NAME1", ""))
        if item not in WANTED.get(code, ()):
            continue
        try:
            rate = float(r["DATA_VALUE"])
        except (KeyError, ValueError):
            continue
        out.append({"stat_code": code, "item_name": item, "year_month": int(r["TIME"]), "rate": rate})
    return out


def fetch(stat_code: str, start_ym: str, end_ym: str) -> list[dict]:
    key = _secrets.require("ECOS_API_KEY")
    url = f"{API_URL}/{key}/json/kr/1/1000/{stat_code}/M/{start_ym}/{end_ym}"
    with urlopen(url, timeout=60) as res:
        body = json.loads(res.read().decode("utf-8"))
    if "RESULT" in body:
        raise RuntimeError(f"{stat_code}: {body['RESULT']}")
    return body.get("StatisticSearch", {}).get("row", [])


def upsert(conn, rows: list[dict]) -> None:
    conn.execute(text(
        "INSERT INTO interest_rates (stat_code, item_name, year_month, rate) "
        "VALUES (:stat_code, :item_name, :year_month, :rate) "
        "ON CONFLICT (stat_code, item_name, year_month) DO UPDATE SET rate = EXCLUDED.rate, collected_at = now()"
    ), rows)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    today = date.today()
    end_ym = f"{today.year}{today.month:02d}"
    if "--from" in sys.argv:
        start_ym = sys.argv[sys.argv.index("--from") + 1]
    else:
        back = today.year * 12 + today.month - 1 - (REFRESH_MONTHS - 1)
        start_ym = f"{back // 12}{back % 12 + 1:02d}"
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ECOS 수집 시작 — {start_ym}~{end_ym}", flush=True)
    engine = None if dry_run else create_engine(market_url())
    total = failures = 0
    for code in WANTED:
        try:
            rows = to_rows(fetch(code, start_ym, end_ym))
        except Exception as e:
            print(f"  [경고] {code} 실패({e}) — 계속", flush=True)
            failures += 1
            continue
        print(f"{code}: {len(rows)}행", flush=True)
        total += len(rows)
        if not dry_run and rows:
            with engine.begin() as conn:
                upsert(conn, rows)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 합계 {total}행"
          + (" (dry-run — 적재 생략)" if dry_run else "")
          + (f" / 실패 {failures}건" if failures else ""), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: 통과 확인**

Run: `mcp run_backend_tests target=minseok/tests/test_collect_ecos_rates.py`
Expected: 2 passed

- [ ] **Step 9: cron 매니페스트 2종 + kustomization**

`infra/k8s/overlays/prod/cronjobs/collect-rone-rent.yaml` — `collect-commercial-trades.yaml`을 복사해 다음만 바꾼다: 첫 줄 주석 `# R-ONE 상가 임대료·공실률 — 분기 첫 달 10일(공표 지연 반영). 창업 재무 엔진 월세 원천.` · `name: collect-rone-rent` · `schedule: "0 5 10 1,4,7,10 *"` · `command: ["python", "scripts/collect_rone_rent.py"]`.

`infra/k8s/overlays/prod/cronjobs/collect-ecos-rates.yaml` — 같은 복사, `# ECOS 기준금리·대출금리 — 매월 15일(한은 공표 뒤). 창업 재무 엔진 이자 원천.` · `name: collect-ecos-rates` · `schedule: "0 4 15 * *"` · `command: ["python", "scripts/collect_ecos_rates.py"]`.

`kustomization.yaml` resources 끝에:
```yaml
  - collect-rone-rent.yaml
  - collect-ecos-rates.yaml
```

- [ ] **Step 10: 실호출 dry-run(맥, 키는 `.env`에 있음)**

Run:
```bash
docker run --rm -v /Users/jangminseok/Project/com.redoceanmap:/work -w /work/minseok -e PYTHONPATH=/work/minseok:/work/minseok/apps minseok97/redoceanmap-backend:latest python scripts/collect_rone_rent.py --dry-run
docker run --rm -v /Users/jangminseok/Project/com.redoceanmap:/work -w /work/minseok -e PYTHONPATH=/work/minseok:/work/minseok/apps minseok97/redoceanmap-backend:latest python scripts/collect_ecos_rates.py --dry-run --from 202401
```
Expected: R-ONE `small: 512행 (분기 [20243]~[20262])` 등 3종 합계 1,536행 · ECOS `722Y001: N행`, `121Y006: 2N행`, 실패 0.

- [ ] **Step 11: 실적재(market DB가 떠 있을 때, `--network host`)** — 위 두 명령에서 `--dry-run` 제거, `--network host` 추가. 확인:
```bash
docker exec market-pgvector psql -U market -d market -c "SELECT building_type, level, count(*) FROM rent_benchmarks GROUP BY 1,2 ORDER BY 1,2;"
docker exec market-pgvector psql -U market -d market -c "SELECT stat_code, item_name, max(year_month), count(*) FROM interest_rates GROUP BY 1,2;"
```
Expected: small/level2 = 59×8=472 · level1 32 · level0 8. 금리는 최신월이 실행월 또는 전월. 결과를 스펙 G5·G6 줄에 적는다.

- [ ] **커밋 경계**: `feat(scripts,infra): R-ONE 임대료·ECOS 금리 수집 스크립트 + cron 2종`

---

### Task 3: 도메인 — 값객체·원가율 상수·재무 엔진

**Files:**
- Create: `minseok/apps/market/domain/value_objects/finance_vo.py`
- Create: `minseok/apps/market/domain/services/cost_benchmarks.py`
- Create: `minseok/apps/market/domain/services/finance_engine.py`
- Test: `minseok/apps/market/tests/domain/services/test_finance_engine.py`, `test_cost_benchmarks.py`

**Interfaces:**
- Produces: `Source`(StrEnum) · `Sourced(value, source, note)` · `FinanceInputs(equity, deposit, monthly_rent, key_money, startup_cost, monthly_payroll, cost_ratio, loan_rate, desired_loan, expected_monthly_sales|None)` · `FinancePlan` · `RentBenchmark(year_quarter, rent_per_sqm_krw, vacancy_rate, region_name, level)` · `finance_engine.plan(inputs, assumptions=()) -> FinancePlan` · `cost_benchmarks.benchmark_for(service_name) -> CostBenchmark` · `cost_benchmarks.monthly_payroll(headcount) -> int` · 상수 `MIN_WAGE_HOURLY_2026=10_320`, `MONTHLY_HOURS=209`, `DEFAULT_SHOP_SQM=33.0`, `DEPOSIT_MONTHS=10`, `WORKING_CAPITAL_MONTHS=3`, `DEFAULT_LOAN_RATE=4.5`.

- [ ] **Step 1: 값객체 작성**

```python
# minseok/apps/market/domain/value_objects/finance_vo.py
"""창업 재무 엔진 값객체 — 모든 입력값에 출처 태그를 붙여 답변이 "무엇을 가정했는지"를 병기한다."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Source(StrEnum):
    INPUT = "input"          # 사용자 발화
    HISTORY = "history"      # 이전 턴 승계
    PROFILE = "profile"      # user_profiles 예산 밴드
    AREA_AVG = "area_avg"    # R-ONE 상권/권역/서울 평균 · 상권 점포당 매출
    FRANCHISE = "franchise"  # 공정위 창업비용 중앙값
    ASSUMED = "assumed"      # 코드 가정치
    ECOS = "ecos"            # 한국은행 금리


@dataclass(frozen=True)
class Sourced:
    value: float
    source: Source
    note: str = ""  # "성수 상권 평균, 33㎡ 가정" 등 병기용


@dataclass(frozen=True)
class FinanceInputs:
    equity: Sourced                 # 자기자본(원)
    deposit: Sourced                # 보증금(원)
    monthly_rent: Sourced           # 월세(원)
    key_money: Sourced              # 권리금(원)
    startup_cost: Sourced           # 인테리어·설비·가맹(원) — 공정위 중앙값은 임대료·권리금 제외
    monthly_payroll: Sourced        # 인건비(원/월)
    cost_ratio: Sourced             # 변동비율(0~1)
    loan_rate: Sourced              # 연 %(예 4.53)
    desired_loan: Sourced           # 희망 대출(원)
    expected_monthly_sales: Sourced | None  # 점포당 월매출 — 소표본이면 None


@dataclass(frozen=True)
class StressPoint:
    rate_delta_pp: float
    loan_rate: float
    monthly_profit: int | None
    runway_months: float | None


@dataclass(frozen=True)
class Scenario:
    key: str            # pessimistic | base | optimistic
    sales_factor: float
    monthly_sales: int
    monthly_profit: int
    runway_months: float | None


@dataclass(frozen=True)
class FinancePlan:
    inputs: FinanceInputs
    capex: int
    opex_base: int          # 이자 제외 월 고정비
    funding_gap: int
    loan: int
    loan_interest: int      # 월 이자
    fixed_monthly: int      # 이자 포함 월 고정비
    bep_monthly_sales: int
    attainment: float | None      # 점포당 월매출 ÷ BEP
    monthly_profit: int | None
    cash_after: int               # 대출까지 받고 CAPEX를 치른 뒤 남는 현금
    runway_months: float | None   # 적자일 때만, 흑자면 None
    stress: tuple[StressPoint, ...]
    scenarios: tuple[Scenario, ...]
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class RentBenchmark:
    year_quarter: int
    rent_per_sqm_krw: int
    vacancy_rate: float | None
    region_name: str
    level: str  # area | zone | city
```

- [ ] **Step 2: 실패 테스트 — 원가율 상수**

```python
# minseok/apps/market/tests/domain/services/test_cost_benchmarks.py
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
```

- [ ] **Step 3: 실패 확인** — Run: `mcp run_backend_tests target=minseok/apps/market/tests/domain/services/test_cost_benchmarks.py` → `ModuleNotFoundError`

- [ ] **Step 4: 원가율 상수 작성**

```python
# minseok/apps/market/domain/services/cost_benchmarks.py
"""업종군별 원가율·영업이익률 벤치마크 — 결정론 상수(KOSIS API 적재 안 함, FINANCE_ENGINE D3).

값은 소상공인실태조사 발표 표와 대조해 교체한다 — 대조 전까지 잠정치이며 source에 "잠정"을 남긴다.
B8 `PAYBACK_MARGIN`과 같은 방식: 가정치를 답변에 출처와 함께 병기한다.
"""
from __future__ import annotations

from dataclasses import dataclass

MIN_WAGE_HOURLY_2026 = 10_320   # 2026년 최저임금 시급(2025-07 고시)
MONTHLY_HOURS = 209             # 주 40시간 + 주휴 환산 월 근로시간
DEFAULT_SHOP_SQM = 33.0         # 면적 미입력 시 10평 가정
DEPOSIT_MONTHS = 10             # 보증금 미입력 시 월세 10개월분 가정
WORKING_CAPITAL_MONTHS = 3      # 개업 후 버틸 운전자금(고정비 N개월분)
DEFAULT_LOAN_RATE = 4.5         # ECOS 미적재 시 연 %

_SOURCE = "소상공인실태조사 2024(중기부·통계청) 대조 전 잠정치"


@dataclass(frozen=True)
class CostBenchmark:
    group: str
    label: str
    cost_ratio: float     # 매출 대비 재료비(변동비) 비율
    margin_ratio: float   # 영업이익률
    source: str


COST_BENCHMARKS: dict[str, CostBenchmark] = {
    "food": CostBenchmark("food", "음식점", 0.38, 0.12, _SOURCE),
    "cafe": CostBenchmark("cafe", "카페·음료", 0.30, 0.14, _SOURCE),
    "pub": CostBenchmark("pub", "주점", 0.35, 0.13, _SOURCE),
    "retail": CostBenchmark("retail", "소매", 0.72, 0.05, _SOURCE),
    "service": CostBenchmark("service", "미용·서비스", 0.15, 0.20, _SOURCE),
    "education": CostBenchmark("education", "교육", 0.05, 0.22, _SOURCE),
    "other": CostBenchmark("other", "기타", 0.30, 0.12, _SOURCE),
}

# 서울시 업종명 어간 → 업종군. 앞에서부터 처음 걸리는 것.
_GROUP_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cafe", ("커피", "음료", "카페")),
    ("pub", ("주점", "호프", "맥주")),
    ("food", ("음식점", "분식", "치킨", "패스트푸드", "제과", "반찬", "피자", "족발", "요리")),
    ("retail", ("편의점", "슈퍼", "마트", "의류", "화장품", "서적", "문구", "가구", "전자", "안경",
                "철물", "조명", "시계", "가방", "신발", "핸드폰", "중고", "꽃", "애완", "완구", "청과", "정육", "수산")),
    ("service", ("미용", "네일", "피부", "세탁", "목욕", "노래", "당구", "PC", "볼링", "골프", "헬스", "스포츠", "사진", "인테리어", "자동차")),
    ("education", ("학원", "교습")),
)


def benchmark_for(service_name: str) -> CostBenchmark:
    for group, words in _GROUP_KEYWORDS:
        if any(w in service_name for w in words):
            return COST_BENCHMARKS[group]
    return COST_BENCHMARKS["other"]


def monthly_payroll(headcount: int) -> int:
    return MIN_WAGE_HOURLY_2026 * MONTHLY_HOURS * max(headcount, 0)
```

- [ ] **Step 5: 통과 확인** — 3 passed

- [ ] **Step 6: 실패 테스트 — 엔진**

```python
# minseok/apps/market/tests/domain/services/test_finance_engine.py
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
```

- [ ] **Step 7: 실패 확인** — `ModuleNotFoundError: market.domain.services.finance_engine`

- [ ] **Step 8: 엔진 작성**

```python
# minseok/apps/market/domain/services/finance_engine.py
"""창업 재무 엔진 — BEP·부족 자금·버틸 기간·금리 스트레스. LLM 없이 전부 결정론(FINANCE_ENGINE_2026-09-16 §4).

부족 자금은 이자 제외 고정비로 먼저 확정한다(이자 ↔ 대출액 순환 방지). 이자는 원리금 상환이 아니라
월 이자만 반영한다 — 가정으로 병기.
"""
from __future__ import annotations

from market.domain.services.cost_benchmarks import WORKING_CAPITAL_MONTHS
from market.domain.value_objects.finance_vo import FinanceInputs, FinancePlan, Scenario, StressPoint

STRESS_DELTAS_PP = (1.0, 2.0)
SCENARIO_FACTORS = (("pessimistic", 0.8), ("base", 1.0), ("optimistic", 1.2))


def _runway(cash_after: int, monthly_profit: int | None) -> float | None:
    if monthly_profit is None or monthly_profit >= 0:
        return None
    return round(cash_after / abs(monthly_profit), 1)


def plan(inputs: FinanceInputs, assumptions: tuple[str, ...] = ()) -> FinancePlan:
    cost_ratio = float(inputs.cost_ratio.value)
    if not 0.0 <= cost_ratio < 1.0:
        raise ValueError(f"cost_ratio는 0 이상 1 미만이어야 합니다: {cost_ratio}")
    contribution = 1.0 - cost_ratio

    equity = int(inputs.equity.value)
    capex = int(round(inputs.startup_cost.value + inputs.deposit.value + inputs.key_money.value))
    opex_base = int(round(inputs.monthly_rent.value + inputs.monthly_payroll.value))
    funding_gap = max(0, capex + opex_base * WORKING_CAPITAL_MONTHS - equity)
    loan = max(int(inputs.desired_loan.value), funding_gap)
    cash_after = max(0, equity + loan - capex)
    sales = int(inputs.expected_monthly_sales.value) if inputs.expected_monthly_sales else None

    def _at(rate: float) -> tuple[int, int, int, int | None]:
        interest = int(round(loan * rate / 100 / 12))
        fixed = opex_base + interest
        bep = int(round(fixed / contribution))
        profit = int(round(sales * contribution - fixed)) if sales is not None else None
        return interest, fixed, bep, profit

    base_rate = float(inputs.loan_rate.value)
    interest, fixed, bep, profit = _at(base_rate)
    attainment = round(sales / bep, 2) if sales is not None and bep > 0 else None

    stress = tuple(
        StressPoint(rate_delta_pp=d, loan_rate=round(base_rate + d, 2),
                    monthly_profit=_at(base_rate + d)[3],
                    runway_months=_runway(cash_after, _at(base_rate + d)[3]))
        for d in STRESS_DELTAS_PP
    )
    scenarios: tuple[Scenario, ...] = ()
    if sales is not None:
        scenarios = tuple(
            Scenario(
                key=key, sales_factor=f, monthly_sales=int(round(sales * f)),
                monthly_profit=int(round(sales * f * contribution - fixed)),
                runway_months=_runway(cash_after, int(round(sales * f * contribution - fixed))),
            )
            for key, f in SCENARIO_FACTORS
        )

    return FinancePlan(
        inputs=inputs, capex=capex, opex_base=opex_base, funding_gap=funding_gap, loan=loan,
        loan_interest=interest, fixed_monthly=fixed, bep_monthly_sales=bep, attainment=attainment,
        monthly_profit=profit, cash_after=cash_after, runway_months=_runway(cash_after, profit),
        stress=stress, scenarios=scenarios, assumptions=tuple(assumptions),
    )
```

- [ ] **Step 9: 통과 확인** — Run 두 테스트 파일 → 12 passed

- [ ] **커밋 경계**: `feat(market): 창업 재무 엔진 순수 도메인 — BEP·부족 자금·runway·금리 스트레스 + 원가율 상수`

---

### Task 4: 도메인 — 임대료 상권 매칭

**Files:**
- Create: `minseok/apps/market/domain/services/rent_matcher.py`
- Test: `minseok/apps/market/tests/domain/services/test_rent_matcher.py`

**Interfaces:**
- Produces: `match_area(trdar_name) -> str | None`(R-ONE 상권명), `zone_for(district_name) -> str`(도심|강남|영등포신촉|기타), `RONE_AREA_ALIASES`, `DISTRICT_TO_ZONE`.

- [ ] **Step 1: 실패 테스트**

```python
# minseok/apps/market/tests/domain/services/test_rent_matcher.py
from market.domain.services import rent_matcher as rm


def test_상권명_어간으로_R_ONE_상권을_찾는다():
    assert rm.match_area("홍대입구역") == "홍대/합정"
    assert rm.match_area("성수동카페거리") == "뚝섬"
    assert rm.match_area("대학로") == "혜화동"
    assert rm.match_area("강남역") == "강남대로"
    assert rm.match_area("역삼역") == "테헤란로"


def test_긴_별칭이_먼저_이겨_잠실새내가_잠실로_빠지지_않는다():
    assert rm.match_area("잠실새내역") == "잠실새내역"
    assert rm.match_area("잠실역") == "잠실/송파"


def test_모르는_상권은_None():
    assert rm.match_area("길음시장") is None


def test_자치구는_권역으로_떨어지고_모르면_기타():
    assert rm.zone_for("종로구") == "도심" and rm.zone_for("중구") == "도심"
    assert rm.zone_for("강남구") == "강남" and rm.zone_for("서초구") == "강남"
    assert rm.zone_for("마포구") == "영등포신촌"
    assert rm.zone_for("성동구") == "기타" and rm.zone_for("") == "기타"


def test_별칭_사전은_R_ONE_상권_59개를_전부_덮는다():
    assert len(rm.RONE_AREA_ALIASES) == 59
```

- [ ] **Step 2: 실패 확인** — `ModuleNotFoundError`

- [ ] **Step 3: 매처 작성**

```python
# minseok/apps/market/domain/services/rent_matcher.py
"""trade_area(서울시 상권 1,650) → R-ONE 임대동향 상권(59)·권역(4) 매칭 — 순수.

R-ONE 상권 목록은 2026-09-16 `SttsApiTblData`(소규모 상가 임대료, 2026Q2) 실호출로 확정했다.
별칭은 우리 상권명에 들어 있을 어간이다. 긴 별칭이 먼저 이긴다("잠실새내" > "잠실").
"""
from __future__ import annotations

# (R-ONE 상권명, 우리 상권명 어간들)
RONE_AREA_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # 도심 11
    ("광화문", ("광화문",)), ("남대문", ("남대문",)), ("동대문", ("동대문",)), ("명동", ("명동",)),
    ("방산시장", ("방산",)), ("북촌", ("북촌",)), ("서촌", ("서촌",)), ("시청", ("시청",)),
    ("을지로", ("을지로",)), ("종로", ("종로",)), ("충무로", ("충무로",)),
    # 강남 9
    ("강남대로", ("강남대로", "강남역")), ("교대역", ("교대",)), ("남부터미널", ("남부터미널",)),
    ("논현역", ("논현",)), ("도산대로", ("도산",)), ("신사역", ("신사역", "가로수길")),
    ("압구정", ("압구정",)), ("청담", ("청담",)), ("테헤란로", ("테헤란", "역삼", "선릉")),
    # 영등포신촌 7
    ("공덕역", ("공덕",)), ("당산역", ("당산",)), ("동교/연남", ("연남", "동교")), ("망원역", ("망원",)),
    ("신촌/이대", ("신촌", "이대", "이화여대")), ("영등포역", ("영등포역", "영등포시장")),
    ("홍대/합정", ("홍대", "합정", "홍익대")),
    # 기타 32
    ("가락시장", ("가락",)), ("건대입구", ("건대", "건국대")), ("경희대", ("경희대", "회기")),
    ("군자", ("군자",)), ("까치산역", ("까치산",)), ("노량진", ("노량진",)), ("독산/시흥", ("독산", "시흥")),
    ("뚝섬", ("뚝섬", "성수")), ("목동", ("목동",)), ("미아사거리", ("미아",)), ("불광역", ("불광",)),
    ("사당", ("사당",)), ("상계역", ("상계",)), ("상봉역", ("상봉",)),
    ("서울대입구역", ("서울대입구", "샤로수길")), ("성신여대", ("성신여대", "돈암")), ("수유", ("수유",)),
    ("숙명여대", ("숙명여대", "숙대")), ("신림역", ("신림",)), ("약수역", ("약수",)), ("연신내", ("연신내",)),
    ("오류동역", ("오류동",)), ("왕십리", ("왕십리",)), ("용산역", ("용산역",)), ("이태원", ("이태원", "경리단")),
    ("잠실/송파", ("잠실", "송파")), ("잠실새내역", ("잠실새내",)), ("장안동", ("장안",)), ("천호", ("천호",)),
    ("청량리", ("청량리",)), ("혜화동", ("혜화", "대학로")), ("화곡", ("화곡",)),
)

# 자치구 → R-ONE 권역. 실데이터의 상권 소속으로 확정(도심=종로·중구, 강남=강남·서초, 영등포신촌=영등포·마포·서대문).
DISTRICT_TO_ZONE: dict[str, str] = {
    "종로구": "도심", "중구": "도심",
    "강남구": "강남", "서초구": "강남",
    "영등포구": "영등포신촌", "마포구": "영등포신촌", "서대문구": "영등포신촌",
}
DEFAULT_ZONE = "기타"

_ALIAS_INDEX: tuple[tuple[str, str], ...] = tuple(
    sorted(((alias, area) for area, aliases in RONE_AREA_ALIASES for alias in aliases),
           key=lambda pair: -len(pair[0]))
)


def match_area(trdar_name: str) -> str | None:
    """우리 상권명에 든 어간으로 R-ONE 상권명을 찾는다. 없으면 None(권역 폴백)."""
    for alias, area in _ALIAS_INDEX:
        if alias in trdar_name:
            return area
    return None


def zone_for(district_name: str) -> str:
    return DISTRICT_TO_ZONE.get(district_name, DEFAULT_ZONE)
```

- [ ] **Step 4: 통과 확인** — 5 passed

- [ ] **커밋 경계**: `feat(market): R-ONE 상권 59개 별칭 사전 + 자치구→권역 매처`

---

### Task 5: 도메인 — 첫 줄 문장(finance_narrator)

**Files:**
- Create: `minseok/apps/market/domain/services/finance_narrator.py`
- Test: `minseok/apps/market/tests/domain/services/test_finance_narrator.py`

**Interfaces:**
- Consumes: `FinancePlan`, `Sourced`.
- Produces: `headline(plan, trdar_name, service_name) -> str`, `input_line(plan) -> str`, `assumption_note(plan) -> str`, `won(amount) -> str`.

- [ ] **Step 1: 실패 테스트**

```python
# minseok/apps/market/tests/domain/services/test_finance_narrator.py
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
```

- [ ] **Step 2: 실패 확인** — `ModuleNotFoundError`

- [ ] **Step 3: 서술자 작성**

```python
# minseok/apps/market/domain/services/finance_narrator.py
"""재무 계산의 첫 줄 — 코드가 쓴다. LLM은 이 문장 뒤에 해석만 붙인다(FINANCE_ENGINE §5-4).

값마다 출처를 괄호로 병기해 사용자가 틀린 값을 한 마디로 고칠 수 있게 한다.
"""
from __future__ import annotations

from market.domain.value_objects.finance_vo import FinancePlan, Source, Sourced

_SOURCE_LABEL = {
    Source.INPUT: "입력", Source.HISTORY: "앞서 말씀하신 값", Source.PROFILE: "프로파일",
    Source.AREA_AVG: "상권 평균", Source.FRANCHISE: "공정위", Source.ASSUMED: "가정", Source.ECOS: "한국은행",
}


def won(amount: float) -> str:
    """1억 2,000만원 · 8,036만원 · 7만원 · 0원."""
    man = int(round(amount / 10_000))
    if man == 0:
        return "0원"
    if man >= 10_000:
        eok, rest = divmod(man, 10_000)
        return f"{eok}억원" if rest == 0 else f"{eok}억 {rest:,}만원"
    return f"{man:,}만원"


def _tag(s: Sourced) -> str:
    return s.note or _SOURCE_LABEL[s.source]


def input_line(plan: FinancePlan) -> str:
    i = plan.inputs
    parts = [
        f"자기자본 {won(i.equity.value)}({_tag(i.equity)})",
        f"월세 {won(i.monthly_rent.value)}({_tag(i.monthly_rent)})",
        f"창업비용 {won(i.startup_cost.value)}({_tag(i.startup_cost)})",
    ]
    if i.deposit.source != Source.ASSUMED:
        parts.append(f"보증금 {won(i.deposit.value)}({_tag(i.deposit)})")
    if i.monthly_payroll.value:
        parts.append(f"인건비 {won(i.monthly_payroll.value)}({_tag(i.monthly_payroll)})")
    return "·".join(parts)


def headline(plan: FinancePlan, trdar_name: str, service_name: str) -> str:
    out = [f"{input_line(plan)}으로 계산하면 손익분기 월매출은 {won(plan.bep_monthly_sales)}이에요."]
    sales = plan.inputs.expected_monthly_sales
    if sales is None or plan.attainment is None or plan.monthly_profit is None:
        out.append(f"{trdar_name} {service_name} 점포당 매출 표본이 적어 달성률·버틸 기간은 계산하지 않았어요.")
    else:
        out.append(
            f"{trdar_name} {service_name} 점포당 월매출 {won(sales.value)}이면 달성률 {plan.attainment:.0%}"
            f"(월 {'이익' if plan.monthly_profit >= 0 else '적자'} 약 {won(abs(plan.monthly_profit))})."
        )
    out.append(f"가게를 열고 3개월 버티려면 부족 자금 {won(plan.funding_gap)}이 필요해요."
               if plan.funding_gap else "자기자본으로 개업 비용과 3개월 운전자금이 충당돼요.")
    if plan.runway_months is not None:
        out.append(f"적자가 이어지면 남은 현금으로 약 {plan.runway_months:.0f}개월 버틸 수 있어요.")
    if plan.stress and plan.monthly_profit is not None:
        s1, s2 = plan.stress
        out.append(
            f"금리가 1%p 오르면 월 {won(abs(s1.monthly_profit))}, 2%p면 월 {won(abs(s2.monthly_profit))}"
            f"{'이익' if s2.monthly_profit >= 0 else '적자'}이에요."
        )
    return " ".join(out)


def assumption_note(plan: FinancePlan) -> str:
    i = plan.inputs
    notes = [s.note for s in (i.deposit, i.key_money, i.startup_cost, i.monthly_payroll, i.cost_ratio, i.loan_rate)
             if s.source == Source.ASSUMED and s.note]
    notes.extend(plan.assumptions)
    return "가정: " + " · ".join(notes) if notes else ""
```

- [ ] **Step 4: 통과 확인** — 6 passed. 실패하면 `won()`의 "7만원"(71,250 → 반올림 7) 케이스부터 본다.

- [ ] **커밋 경계**: `feat(market): 재무 계산 첫 줄 서술자 — 값·출처 병기`

---

### Task 6: market `area_finance` 슬라이스 (DTO·포트·리포지토리·인터랙터·라우터)

**Files:**
- Create: `minseok/apps/market/app/dtos/area_finance_dto.py`, `app/ports/input/area_finance_use_case.py`, `app/ports/output/area_finance_repository.py`, `app/use_cases/area_finance_interactor.py`, `adapter/outbound/pg/area_finance_pg_repository.py`, `adapter/inbound/api/schemas/area_finance_schema.py`, `adapter/inbound/api/v1/area_finance_router.py`, `dependencies/area_finance_provider.py`
- Test: `minseok/apps/market/tests/app/use_cases/test_area_finance_interactor.py`
- Modify: `minseok/main.py:122-123` 근처 import, `:266` 근처 include_router

**Interfaces:**
- Consumes: Task 3·4·5 산출물, `AreaDetailRepositoryPort.find_header/resolve_service/find_service_ranking/find_startup_cost`, `area_narrator.franchise_industry_for`, `PAYBACK_MIN_STORES`.
- Produces: `AreaFinanceQuery`, `AreaFinanceView`, `AreaFinanceUseCase.calculate(query) -> AreaFinanceView | None`, `AreaFinanceRepositoryPort.find_rent(trdar_code) -> RentBenchmark | None` · `find_loan_rate() -> tuple[int, float] | None`, `AreaFinanceInteractor(finance, detail)`, `get_area_finance_use_case`.

- [ ] **Step 1: DTO**

```python
# minseok/apps/market/app/dtos/area_finance_dto.py
from __future__ import annotations

from dataclasses import dataclass, field

from market.domain.value_objects.finance_vo import FinancePlan, RentBenchmark


@dataclass(frozen=True)
class AreaFinanceQuery:
    """재무 계산 입력. None은 '사용자가 말하지 않음' — 인터랙터가 상권 평균·공정위·가정으로 채운다.

    sources: 값을 준 쪽이 chat일 때 출처(input|history|profile)를 필드명별로 알려 준다. 없으면 input.
    """

    trdar_code: int
    service_code: str
    equity: int
    deposit: int | None = None
    monthly_rent: int | None = None
    key_money: int | None = None
    startup_cost: int | None = None
    area_sqm: float | None = None
    headcount: int | None = None
    desired_loan: int | None = None
    sources: dict[str, str] = field(default_factory=dict)
    equity_note: str = ""


@dataclass(frozen=True)
class AreaFinanceView:
    trdar_code: int
    trdar_name: str
    district_name: str
    service_code: str
    service_name: str
    plan: FinancePlan
    rent: RentBenchmark | None
    headline: str
    assumption_note: str
```

- [ ] **Step 2: 입력·출력 포트**

```python
# minseok/apps/market/app/ports/input/area_finance_use_case.py
from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_finance_dto import AreaFinanceQuery, AreaFinanceView


class AreaFinanceUseCase(ABC):
    """창업 재무 계산 — 상권·업종 + 사용자 입력 → BEP·부족 자금·runway."""

    @abstractmethod
    async def calculate(self, query: AreaFinanceQuery) -> AreaFinanceView | None:
        """상권·업종이 없거나 월세를 어디서도 못 구하면 None(HTTP 변환은 라우터 몫)."""
        ...
```

```python
# minseok/apps/market/app/ports/output/area_finance_repository.py
from __future__ import annotations

from abc import ABC, abstractmethod

from market.domain.value_objects.finance_vo import RentBenchmark


class AreaFinanceRepositoryPort(ABC):
    """재무 엔진 전용 조회 — 임대료(매칭 포함)·금리. 점포당 매출·창업비용은 AreaDetailRepositoryPort 재사용."""

    @abstractmethod
    async def find_rent(self, trdar_code: int) -> RentBenchmark | None:
        """소규모 상가 최신 분기 임대료 — 상권 직접 매칭 → 자치구 권역 → 서울 순. 미적재면 None."""
        ...

    @abstractmethod
    async def find_loan_rate(self) -> tuple[int, float] | None:
        """(연월, 연 %) — ECOS 121Y006 '대출평균' 최신월. 미적재면 None."""
        ...
```

- [ ] **Step 3: 실패 테스트 — 인터랙터(스텁 포트)**

```python
# minseok/apps/market/tests/app/use_cases/test_area_finance_interactor.py
from market.app.dtos.area_finance_dto import AreaFinanceQuery
from market.app.dtos.area_stats_dto import AreaHeader, ServiceRef
from market.app.use_cases.area_finance_interactor import AreaFinanceInteractor
from market.domain.value_objects.area_profile_vo import ServiceRank, StartupCost
from market.domain.value_objects.finance_vo import RentBenchmark, Source


class _StubDetail:
    def __init__(self, header=True, rank=None, cost=None):
        self._header = AreaHeader(1001, "성수동카페거리", "성동구") if header else None
        self._rank = rank
        self._cost = cost

    async def find_header(self, trdar_code):
        return self._header

    async def resolve_service(self, trdar_code, service_code):
        return ServiceRef("CS100010", "커피-음료") if service_code == "CS100010" else None

    async def find_service_ranking(self, trdar_code, limit=12):
        return [self._rank] if self._rank else []

    async def find_startup_cost(self, industry_name):
        return self._cost


class _StubFinance:
    def __init__(self, rent=None, rate=(202608, 4.5)):
        self.rent, self.rate = rent, rate

    async def find_rent(self, trdar_code):
        return self.rent

    async def find_loan_rate(self):
        return self.rate


RANK = ServiceRank(code="CS100010", name="커피-음료", monthly_sales=300_000_000, store_count=20,
                   sales_per_store=15_000_000, sales_qoq=None, closure_rate=None)
COST = StartupCost(industry_name="커피", year=2025, total_amount=80_000_000, brand_count=100)
RENT = RentBenchmark(year_quarter=20262, rent_per_sqm_krw=45_000, vacancy_rate=3.0, region_name="기타", level="zone")
Q = AreaFinanceQuery(trdar_code=1001, service_code="CS100010", equity=100_000_000)


async def test_상권_평균과_공정위_가정으로_빈_값을_채운다():
    view = await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(rank=RANK, cost=COST)).calculate(Q)
    i = view.plan.inputs
    assert i.monthly_rent.value == 45_000 * 33 and i.monthly_rent.source == Source.AREA_AVG
    assert "기타" in i.monthly_rent.note and "33㎡" in i.monthly_rent.note
    assert i.startup_cost.value == 80_000_000 and i.startup_cost.source == Source.FRANCHISE
    assert i.deposit.value == i.monthly_rent.value * 10 and i.deposit.source == Source.ASSUMED
    assert i.monthly_payroll.value == 0 and i.loan_rate.value == 4.5 and i.loan_rate.source == Source.ECOS
    assert i.expected_monthly_sales.value == 15_000_000
    assert "손익분기" in view.headline and view.rent is RENT


async def test_사용자_입력이_있으면_출처가_input이고_면적으로_월세를_환산하지_않는다():
    q = AreaFinanceQuery(trdar_code=1001, service_code="CS100010", equity=100_000_000,
                         monthly_rent=3_000_000, headcount=1, area_sqm=66.0, desired_loan=20_000_000,
                         sources={"equity": "history"}, equity_note="앞서 말씀하신 1억")
    view = await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(rank=RANK, cost=COST)).calculate(q)
    i = view.plan.inputs
    assert i.monthly_rent.value == 3_000_000 and i.monthly_rent.source == Source.INPUT
    assert i.equity.source == Source.HISTORY and i.equity.note == "앞서 말씀하신 1억"
    assert i.monthly_payroll.value == 10_320 * 209 and i.desired_loan.value == 20_000_000


async def test_임대료가_없어도_월세를_말했으면_계산하고_둘_다_없으면_None():
    ok = await AreaFinanceInteractor(_StubFinance(None), _StubDetail(rank=RANK, cost=COST)).calculate(
        AreaFinanceQuery(1001, "CS100010", 100_000_000, monthly_rent=2_000_000))
    assert ok is not None and ok.rent is None
    none = await AreaFinanceInteractor(_StubFinance(None), _StubDetail(rank=RANK, cost=COST)).calculate(Q)
    assert none is None


async def test_점포_5개_미만이면_매출을_넣지_않는다():
    small = ServiceRank(code="CS100010", name="커피-음료", monthly_sales=30_000_000, store_count=3,
                        sales_per_store=10_000_000, sales_qoq=None, closure_rate=None)
    view = await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(rank=small, cost=COST)).calculate(Q)
    assert view.plan.inputs.expected_monthly_sales is None and view.plan.attainment is None


async def test_창업비용_없고_금리_없으면_가정치로_간다():
    view = await AreaFinanceInteractor(_StubFinance(RENT, rate=None), _StubDetail(rank=RANK, cost=None)).calculate(Q)
    i = view.plan.inputs
    assert i.startup_cost.value == 0 and i.startup_cost.source == Source.ASSUMED
    assert i.loan_rate.value == 4.5 and i.loan_rate.source == Source.ASSUMED


async def test_상권이나_업종이_없으면_None():
    assert await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(header=False)).calculate(Q) is None
    assert await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(rank=RANK)).calculate(
        AreaFinanceQuery(1001, "CS999999", 100_000_000)) is None
```

- [ ] **Step 4: 실패 확인** — `ModuleNotFoundError: market.app.use_cases.area_finance_interactor`

- [ ] **Step 5: 인터랙터 작성**

```python
# minseok/apps/market/app/use_cases/area_finance_interactor.py
from __future__ import annotations

from market.app.dtos.area_finance_dto import AreaFinanceQuery, AreaFinanceView
from market.app.ports.input.area_finance_use_case import AreaFinanceUseCase
from market.app.ports.output.area_detail_repository import AreaDetailRepositoryPort
from market.app.ports.output.area_finance_repository import AreaFinanceRepositoryPort
from market.domain.services import cost_benchmarks as cb
from market.domain.services import finance_engine, finance_narrator
from market.domain.services.area_narrator import PAYBACK_MIN_STORES, franchise_industry_for
from market.domain.value_objects.finance_vo import FinanceInputs, Source, Sourced

_BUILDING_LABEL = "소규모 상가"


class AreaFinanceInteractor(AreaFinanceUseCase):
    """입력 → 폴백 순서(입력 > 상권 평균/공정위/한국은행 > 가정)로 FinanceInputs를 조립하고 엔진에 넘긴다.

    자기자본의 이력·프로파일 폴백은 chat이 채워서 넘긴다(sources 맵) — 여기서는 데이터 폴백만.
    """

    def __init__(self, finance: AreaFinanceRepositoryPort, detail: AreaDetailRepositoryPort) -> None:
        self._finance = finance
        self._detail = detail

    async def calculate(self, query: AreaFinanceQuery) -> AreaFinanceView | None:
        header = await self._detail.find_header(query.trdar_code)
        if header is None:
            return None
        service = await self._detail.resolve_service(query.trdar_code, query.service_code)
        if service is None:
            return None

        def given(field: str, value: float, note: str = "") -> Sourced:
            return Sourced(value, Source(query.sources.get(field, "input")), note)

        rent = await self._finance.find_rent(query.trdar_code)
        sqm = query.area_sqm or cb.DEFAULT_SHOP_SQM
        if query.monthly_rent is not None:
            monthly_rent = given("monthly_rent", query.monthly_rent)
        elif rent is not None:
            monthly_rent = Sourced(
                int(round(rent.rent_per_sqm_krw * sqm)), Source.AREA_AVG,
                f"{rent.region_name} {_BUILDING_LABEL} 평균, {sqm:.0f}㎡{' 가정' if query.area_sqm is None else ''}",
            )
        else:
            return None  # 임대료 미적재 + 월세 미입력 → chat이 되묻는다

        deposit = (given("deposit", query.deposit) if query.deposit is not None
                   else Sourced(monthly_rent.value * cb.DEPOSIT_MONTHS, Source.ASSUMED, f"보증금은 월세 {cb.DEPOSIT_MONTHS}개월분 가정"))
        key_money = (given("key_money", query.key_money) if query.key_money is not None
                     else Sourced(0, Source.ASSUMED, "권리금 0 가정"))

        if query.startup_cost is not None:
            startup_cost = given("startup_cost", query.startup_cost)
        else:
            industry = franchise_industry_for(service.name)
            cost = await self._detail.find_startup_cost(industry) if industry else None
            startup_cost = (Sourced(cost.total_amount, Source.FRANCHISE, f"공정위 {cost.industry_name}({cost.year}) 중앙값, 임대료·권리금 제외")
                            if cost else Sourced(0, Source.ASSUMED, "창업비용 자료 없음 — 0으로 가정"))

        payroll = (Sourced(cb.monthly_payroll(query.headcount), Source.ASSUMED, f"최저임금 기준 {query.headcount}명")
                   if query.headcount else Sourced(0, Source.ASSUMED, "1인 운영 가정"))
        bench = cb.benchmark_for(service.name)
        cost_ratio = Sourced(bench.cost_ratio, Source.ASSUMED, f"{bench.label} 원가율 {bench.cost_ratio:.0%}({bench.source})")
        rate = await self._finance.find_loan_rate()
        loan_rate = (Sourced(rate[1], Source.ECOS, f"한국은행 {rate[0] // 100}-{rate[0] % 100:02d} 대출평균")
                     if rate else Sourced(cb.DEFAULT_LOAN_RATE, Source.ASSUMED, f"금리 자료 없음 — {cb.DEFAULT_LOAN_RATE}% 가정"))
        desired_loan = (given("desired_loan", query.desired_loan) if query.desired_loan is not None
                        else Sourced(0, Source.ASSUMED))

        ranking = await self._detail.find_service_ranking(query.trdar_code, limit=60)
        rank = next((r for r in ranking if r.code == service.code), None)
        expected = None
        if rank and rank.sales_per_store and (rank.store_count or 0) >= PAYBACK_MIN_STORES:
            expected = Sourced(rank.sales_per_store, Source.AREA_AVG, f"{header.trdar_name} {service.name} 점포당 월매출")

        inputs = FinanceInputs(
            equity=given("equity", query.equity, query.equity_note), deposit=deposit, monthly_rent=monthly_rent,
            key_money=key_money, startup_cost=startup_cost, monthly_payroll=payroll, cost_ratio=cost_ratio,
            loan_rate=loan_rate, desired_loan=desired_loan, expected_monthly_sales=expected,
        )
        plan = finance_engine.plan(inputs, assumptions=(
            "이자만 반영(원리금 상환 제외)", f"운전자금 {cb.WORKING_CAPITAL_MONTHS}개월분 포함",
        ))
        return AreaFinanceView(
            trdar_code=header.trdar_code, trdar_name=header.trdar_name, district_name=header.district_name,
            service_code=service.code, service_name=service.name, plan=plan, rent=rent,
            headline=finance_narrator.headline(plan, header.trdar_name, service.name),
            assumption_note=finance_narrator.assumption_note(plan),
        )
```

- [ ] **Step 6: 통과 확인** — 6 passed

- [ ] **Step 7: PG 리포지토리**

```python
# minseok/apps/market/adapter/outbound/pg/area_finance_pg_repository.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from market.adapter.outbound.orm.interest_rate_orm import InterestRateOrm
from market.adapter.outbound.orm.region_orm import RegionOrm
from market.adapter.outbound.orm.rent_benchmark_orm import RentBenchmarkOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.app.ports.output.area_finance_repository import AreaFinanceRepositoryPort
from market.domain.services.rent_matcher import match_area, zone_for
from market.domain.value_objects.finance_vo import RentBenchmark

_BUILDING = "small"
_CITY = "서울"


class AreaFinancePgRepository(AreaFinanceRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _latest(self, level: int, region_name: str) -> RentBenchmarkOrm | None:
        return (await self._session.execute(
            select(RentBenchmarkOrm)
            .where(RentBenchmarkOrm.building_type == _BUILDING, RentBenchmarkOrm.level == level,
                   RentBenchmarkOrm.region_name == region_name)
            .order_by(RentBenchmarkOrm.year_quarter.desc()).limit(1)
        )).scalar_one_or_none()

    async def find_rent(self, trdar_code: int) -> RentBenchmark | None:
        dong, gu = aliased(RegionOrm), aliased(RegionOrm)
        row = (await self._session.execute(
            select(TradeAreaOrm.name, gu.name)
            .outerjoin(dong, TradeAreaOrm.region_code == dong.code)
            .outerjoin(gu, dong.parent_code == gu.code)
            .where(TradeAreaOrm.code == trdar_code)
        )).first()
        if row is None:
            return None
        name, district = row[0], row[1] or ""
        candidates = []
        area = match_area(name)
        if area:
            candidates.append((2, area, "area"))
        candidates.append((1, zone_for(district), "zone"))
        candidates.append((0, _CITY, "city"))
        for level, region, tag in candidates:
            r = await self._latest(level, region)
            if r is not None:
                return RentBenchmark(year_quarter=r.year_quarter, rent_per_sqm_krw=r.rent_per_sqm_krw,
                                     vacancy_rate=r.vacancy_rate, region_name=r.region_name, level=tag)
        return None

    async def find_loan_rate(self) -> tuple[int, float] | None:
        r = (await self._session.execute(
            select(InterestRateOrm.year_month, InterestRateOrm.rate)
            .where(InterestRateOrm.stat_code == "121Y006", InterestRateOrm.item_name == "대출평균")
            .order_by(InterestRateOrm.year_month.desc()).limit(1)
        )).first()
        return (int(r[0]), float(r[1])) if r else None
```

- [ ] **Step 8: 스키마·라우터·프로바이더**

```python
# minseok/apps/market/adapter/inbound/api/schemas/area_finance_schema.py
from pydantic import BaseModel, Field


class SourcedValueSchema(BaseModel):
    key: str
    value: float
    source: str = Field(description="input | history | profile | area_avg | franchise | assumed | ecos")
    note: str


class StressSchema(BaseModel):
    rateDeltaPp: float
    loanRate: float
    monthlyProfit: int | None
    runwayMonths: float | None


class ScenarioSchema(BaseModel):
    key: str
    monthlySales: int
    monthlyProfit: int
    runwayMonths: float | None


class AreaFinanceResponse(BaseModel):
    """결정론 재무 계산 — 값마다 출처를 병기한다. 은행 상품 추천은 없다."""

    trdarCode: int
    trdarName: str
    districtName: str
    serviceCode: str
    serviceName: str
    headline: str
    assumptionNote: str
    inputs: list[SourcedValueSchema]
    capex: int
    fundingGap: int
    loan: int
    fixedMonthly: int
    bepMonthlySales: int
    attainment: float | None
    monthlyProfit: int | None
    cashAfter: int
    runwayMonths: float | None
    stress: list[StressSchema]
    scenarios: list[ScenarioSchema]
    rentQuarter: int | None = Field(description="임대료 기준 분기(R-ONE) — 미적재면 None")
    rentLevel: str | None = Field(description="area | zone | city")
```

```python
# minseok/apps/market/adapter/inbound/api/v1/area_finance_router.py
from dataclasses import fields

from fastapi import APIRouter, Depends, HTTPException, Query

from market.adapter.inbound.api.schemas.area_finance_schema import (
    AreaFinanceResponse, ScenarioSchema, SourcedValueSchema, StressSchema,
)
from market.app.dtos.area_finance_dto import AreaFinanceQuery
from market.app.ports.input.area_finance_use_case import AreaFinanceUseCase
from market.dependencies.area_finance_provider import get_area_finance_use_case

area_finance_router = APIRouter(prefix="/market", tags=["market"])
# `/myself`를 두지 않는다 — market 조회 슬라이스 라우터는 전부 prefix="/market"이라 cartographer의 자기소개 하나뿐.


@area_finance_router.get("/trdar/{trdar_code}/finance", response_model=AreaFinanceResponse)
async def get_area_finance(
    trdar_code: int,
    service_code: str = Query(description="업종 코드 (예: CS100010)"),
    equity: int = Query(ge=0, description="자기자본(원)"),
    deposit: int | None = Query(default=None, ge=0),
    monthly_rent: int | None = Query(default=None, ge=0),
    key_money: int | None = Query(default=None, ge=0),
    startup_cost: int | None = Query(default=None, ge=0),
    area_sqm: float | None = Query(default=None, gt=0),
    headcount: int | None = Query(default=None, ge=0),
    desired_loan: int | None = Query(default=None, ge=0),
    use_case: AreaFinanceUseCase = Depends(get_area_finance_use_case),
) -> AreaFinanceResponse:
    view = await use_case.calculate(AreaFinanceQuery(
        trdar_code=trdar_code, service_code=service_code, equity=equity, deposit=deposit,
        monthly_rent=monthly_rent, key_money=key_money, startup_cost=startup_cost, area_sqm=area_sqm,
        headcount=headcount, desired_loan=desired_loan,
    ))
    if view is None:
        raise HTTPException(status_code=404, detail=f"상권 {trdar_code} · 업종 {service_code}의 재무 계산 자료가 없습니다")
    p = view.plan
    return AreaFinanceResponse(
        trdarCode=view.trdar_code, trdarName=view.trdar_name, districtName=view.district_name,
        serviceCode=view.service_code, serviceName=view.service_name,
        headline=view.headline, assumptionNote=view.assumption_note,
        inputs=[
            SourcedValueSchema(key=f.name, value=s.value, source=str(s.source), note=s.note)
            for f in fields(p.inputs) if (s := getattr(p.inputs, f.name)) is not None
        ],
        capex=p.capex, fundingGap=p.funding_gap, loan=p.loan, fixedMonthly=p.fixed_monthly,
        bepMonthlySales=p.bep_monthly_sales, attainment=p.attainment, monthlyProfit=p.monthly_profit,
        cashAfter=p.cash_after, runwayMonths=p.runway_months,
        stress=[StressSchema(rateDeltaPp=s.rate_delta_pp, loanRate=s.loan_rate, monthlyProfit=s.monthly_profit,
                             runwayMonths=s.runway_months) for s in p.stress],
        scenarios=[ScenarioSchema(key=s.key, monthlySales=s.monthly_sales, monthlyProfit=s.monthly_profit,
                                  runwayMonths=s.runway_months) for s in p.scenarios],
        rentQuarter=view.rent.year_quarter if view.rent else None,
        rentLevel=view.rent.level if view.rent else None,
    )
```

```python
# minseok/apps/market/dependencies/area_finance_provider.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_market_db
from market.adapter.outbound.pg.area_detail_pg_repository import AreaDetailPgRepository
from market.adapter.outbound.pg.area_finance_pg_repository import AreaFinancePgRepository
from market.app.ports.input.area_finance_use_case import AreaFinanceUseCase
from market.app.use_cases.area_finance_interactor import AreaFinanceInteractor


def get_area_finance_use_case(db: AsyncSession = Depends(get_market_db)) -> AreaFinanceUseCase:
    return AreaFinanceInteractor(
        finance=AreaFinancePgRepository(session=db), detail=AreaDetailPgRepository(session=db),
    )
```

- [ ] **Step 9: main.py 등록** — `minseok/main.py` 122행(`area_fitness_router` import 블록) 뒤에:

```python
from market.adapter.inbound.api.v1.area_finance_router import area_finance_router
```
266행(`app.include_router(market_area_fitness_router, dependencies=_authenticated)`) 뒤에:
```python
app.include_router(area_finance_router, dependencies=_authenticated)
```

- [ ] **Step 10: 구조·공개 경계 검증**

Run: `mcp run_backend_tests target=minseok/tests/test_public_routes.py` → 전부 passed(신규 경로가 인증 필수로 잡힘, myself 1개 유지).
Run: `mcp run_import_linter` → 계약 5종 KEPT.

- [ ] **Step 11: 실 DB 확인(Task 2 실적재가 끝났고 dev 파드가 떠 있을 때)**

```bash
TOKEN=$(...로그인 토큰...)   # 기존 방식대로 /auth/login으로 발급
curl -s -H "Authorization: Bearer $TOKEN" "http://192.168.64.2:18000/market/trdar/3110131/finance?service_code=CS100010&equity=100000000" | python3 -m json.tool | head -40
```
Expected: `headline`에 "손익분기 월매출"·출처 괄호, `rentLevel`이 `area|zone|city` 중 하나.

- [ ] **커밋 경계**: `feat(market): area_finance 슬라이스 — GET /market/trdar/{code}/finance 결정론 재무 계산`

---

### Task 7: 허브 포트 `AreaFinancePort` + market 게이트웨이 + 배선

**Files:**
- Create: `minseok/apps/hub/app/dtos/area_finance_dto.py`, `minseok/apps/hub/app/ports/output/area_finance_port.py`, `minseok/apps/hub/dependencies/area_finance_provider.py`
- Create: `minseok/apps/market/adapter/outbound/gateways/area_finance_gateway.py`
- Modify: `minseok/apps/market/dependencies/area_finance_provider.py`(게이트웨이 프로바이더 추가), `minseok/main.py`(override 1줄)
- Test: `minseok/apps/market/tests/adapter/test_area_finance_gateway.py`

**Interfaces:**
- Produces: `AreaFinanceRequest`, `AreaFinancePlanInfo`, `FinanceInputItem`, `AreaFinancePort.plan(request) -> AreaFinancePlanInfo | None`, `get_area_finance_port`(허브 스텁), `get_area_finance_gateway`(market).

- [ ] **Step 1: 허브 DTO·포트·프로바이더**

```python
# minseok/apps/hub/app/dtos/area_finance_dto.py
"""창업 재무 계산 계약 DTO — market 엔진 결과를 chat이 그대로 싣는 문장·수치.

문장(headline)은 market 도메인(finance_narrator)이 만든다 — AreaInsight와 같은 이유(소비자마다
임계값을 재구현하지 않는다). 금액은 원(int), 금리는 연 %.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AreaFinanceRequest:
    trdar_code: int
    service_code: str
    equity: int
    deposit: int | None = None
    monthly_rent: int | None = None
    key_money: int | None = None
    startup_cost: int | None = None
    area_sqm: float | None = None
    headcount: int | None = None
    desired_loan: int | None = None
    sources: dict[str, str] = field(default_factory=dict)  # 필드명 → input|history|profile
    equity_note: str = ""


@dataclass(frozen=True)
class FinanceInputItem:
    key: str
    value: float
    source: str
    note: str


@dataclass(frozen=True)
class AreaFinancePlanInfo:
    trdar_code: int
    trdar_name: str
    service_code: str
    service_name: str
    headline: str
    assumption_note: str
    inputs: tuple[FinanceInputItem, ...]
    capex: int
    funding_gap: int
    loan: int
    bep_monthly_sales: int
    attainment: float | None
    monthly_profit: int | None
    runway_months: float | None
    stress_runway: tuple[tuple[float, float | None], ...]  # (금리 +pp, runway)
    expected_monthly_sales: int | None
    rent_level: str | None  # area | zone | city
```

```python
# minseok/apps/hub/app/ports/output/area_finance_port.py
from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.area_finance_dto import AreaFinancePlanInfo, AreaFinanceRequest


class AreaFinancePort(ABC):
    """허브가 스포크에 위임하는 창업 재무 계산 추상 — 구현은 market 게이트웨이, 소비는 chat."""

    @abstractmethod
    async def plan(self, request: AreaFinanceRequest) -> AreaFinancePlanInfo | None:
        """상권·업종이 없거나 월세를 못 구하면 None(소비자가 되묻는다)."""
        ...
```

```python
# minseok/apps/hub/dependencies/area_finance_provider.py
from __future__ import annotations

from hub.app.ports.output.area_finance_port import AreaFinancePort


def get_area_finance_port() -> AreaFinancePort:
    """합성 루트(main.py)의 dependency_overrides로 스포크(market) 구현을 주입한다."""
    raise NotImplementedError(
        "get_area_finance_port는 main.py의 dependency_overrides로 market 구현을 주입해야 합니다."
    )
```

- [ ] **Step 2: 실패 테스트 — 게이트웨이 매핑**

```python
# minseok/apps/market/tests/adapter/test_area_finance_gateway.py
from hub.app.dtos.area_finance_dto import AreaFinanceRequest
from market.adapter.outbound.gateways.area_finance_gateway import AreaFinanceGateway
from market.app.dtos.area_finance_dto import AreaFinanceView
from market.domain.services import finance_engine as fe
from market.domain.value_objects.finance_vo import FinanceInputs, RentBenchmark, Source, Sourced


def _view() -> AreaFinanceView:
    plan = fe.plan(FinanceInputs(
        equity=Sourced(100_000_000, Source.INPUT), deposit=Sourced(30_000_000, Source.ASSUMED, "가정"),
        monthly_rent=Sourced(3_000_000, Source.AREA_AVG, "기타 평균"), key_money=Sourced(0, Source.ASSUMED),
        startup_cost=Sourced(80_000_000, Source.FRANCHISE, "공정위"), monthly_payroll=Sourced(0, Source.ASSUMED),
        cost_ratio=Sourced(0.3, Source.ASSUMED), loan_rate=Sourced(4.5, Source.ECOS),
        desired_loan=Sourced(0, Source.ASSUMED), expected_monthly_sales=Sourced(15_000_000, Source.AREA_AVG),
    ))
    return AreaFinanceView(1001, "성수동카페거리", "성동구", "CS100010", "커피-음료", plan,
                           RentBenchmark(20262, 45_000, 3.0, "기타", "zone"), "첫 줄", "가정: …")


class _StubUseCase:
    def __init__(self, view):
        self.view, self.queries = view, []

    async def calculate(self, query):
        self.queries.append(query)
        return self.view


async def test_뷰를_허브_DTO로_옮기고_요청_필드를_그대로_넘긴다():
    uc = _StubUseCase(_view())
    info = await AreaFinanceGateway(uc).plan(AreaFinanceRequest(
        1001, "CS100010", 100_000_000, monthly_rent=3_000_000, sources={"equity": "profile"}, equity_note="밴드 중앙"))
    q = uc.queries[0]
    assert q.monthly_rent == 3_000_000 and q.sources == {"equity": "profile"} and q.equity_note == "밴드 중앙"
    assert info.headline == "첫 줄" and info.rent_level == "zone" and info.expected_monthly_sales == 15_000_000
    assert [i.key for i in info.inputs][:3] == ["equity", "deposit", "monthly_rent"]
    assert info.stress_runway == ((1.0, None), (2.0, None))


async def test_None은_그대로_None():
    assert await AreaFinanceGateway(_StubUseCase(None)).plan(AreaFinanceRequest(1, "CS1", 1)) is None
```

- [ ] **Step 3: 실패 확인** — `ModuleNotFoundError`

- [ ] **Step 4: 게이트웨이 + 프로바이더 + main.py**

```python
# minseok/apps/market/adapter/outbound/gateways/area_finance_gateway.py
from __future__ import annotations

from dataclasses import fields

from hub.app.dtos.area_finance_dto import AreaFinancePlanInfo, AreaFinanceRequest, FinanceInputItem
from hub.app.ports.output.area_finance_port import AreaFinancePort
from market.app.dtos.area_finance_dto import AreaFinanceQuery
from market.app.ports.input.area_finance_use_case import AreaFinanceUseCase


class AreaFinanceGateway(AreaFinancePort):
    """허브 AreaFinancePort 구현 — area_finance 인터랙터에 위임하고 View를 계약 DTO로 옮긴다."""

    def __init__(self, use_case: AreaFinanceUseCase) -> None:
        self._use_case = use_case

    async def plan(self, request: AreaFinanceRequest) -> AreaFinancePlanInfo | None:
        view = await self._use_case.calculate(AreaFinanceQuery(
            trdar_code=request.trdar_code, service_code=request.service_code, equity=request.equity,
            deposit=request.deposit, monthly_rent=request.monthly_rent, key_money=request.key_money,
            startup_cost=request.startup_cost, area_sqm=request.area_sqm, headcount=request.headcount,
            desired_loan=request.desired_loan, sources=dict(request.sources), equity_note=request.equity_note,
        ))
        if view is None:
            return None
        p = view.plan
        return AreaFinancePlanInfo(
            trdar_code=view.trdar_code, trdar_name=view.trdar_name, service_code=view.service_code,
            service_name=view.service_name, headline=view.headline, assumption_note=view.assumption_note,
            inputs=tuple(
                FinanceInputItem(key=f.name, value=s.value, source=str(s.source), note=s.note)
                for f in fields(p.inputs) if (s := getattr(p.inputs, f.name)) is not None
            ),
            capex=p.capex, funding_gap=p.funding_gap, loan=p.loan, bep_monthly_sales=p.bep_monthly_sales,
            attainment=p.attainment, monthly_profit=p.monthly_profit, runway_months=p.runway_months,
            stress_runway=tuple((s.rate_delta_pp, s.runway_months) for s in p.stress),
            expected_monthly_sales=int(p.inputs.expected_monthly_sales.value) if p.inputs.expected_monthly_sales else None,
            rent_level=view.rent.level if view.rent else None,
        )
```

`minseok/apps/market/dependencies/area_finance_provider.py` 끝에 추가:
```python
from hub.app.ports.output.area_finance_port import AreaFinancePort  # noqa: E402
from market.adapter.outbound.gateways.area_finance_gateway import AreaFinanceGateway  # noqa: E402


def get_area_finance_gateway(db: AsyncSession = Depends(get_market_db)) -> AreaFinancePort:
    """허브 AreaFinancePort 구현 프로바이더 — main.py가 dependency_overrides로 주입."""
    return AreaFinanceGateway(use_case=get_area_finance_use_case(db))
```
(import는 파일 상단으로 올려 정리한다.)

`minseok/main.py`: 69행 근처 `from hub.dependencies.area_backtest_report_provider import ...` 아래에
```python
from hub.dependencies.area_finance_provider import get_area_finance_port
```
111행 근처 market 프로바이더 import 아래에
```python
from market.dependencies.area_finance_provider import get_area_finance_gateway
```
346행(`app.dependency_overrides[get_area_backtest_report_port] = ...`) 아래에
```python
app.dependency_overrides[get_area_finance_port] = get_area_finance_gateway
```

- [ ] **Step 5: 통과 확인** — 게이트웨이 테스트 2 passed · `mcp run_import_linter` 5 KEPT(허브가 market을 import하지 않고, market이 hub DTO를 import하는 방향만 있어야 한다).

- [ ] **커밋 경계**: `feat(hub,market): AreaFinancePort — 재무 계산을 허브 계약으로 노출`

---

### Task 8: chat — 라벨 금액 파서(`amount_parser`)

**Files:**
- Create: `minseok/apps/chat/domain/services/amount_parser.py`
- Modify: `minseok/apps/chat/app/use_cases/chat_interactor.py:556-596` (`_BUDGET_RE`·`fmt_won`·`parse_budget_krw` 정의를 삭제하고 import로 대체)
- Test: `minseok/apps/chat/tests/domain/test_amount_parser.py`

**Interfaces:**
- Produces: `parse_budget_krw(text) -> int | None`(기존 동작 그대로), `fmt_won(amount) -> str`(기존), `parse_won(text) -> int | None`(확장: "5천"·"3,000만원" 포함), `parse_labeled_amounts(text) -> dict[str, int | float]` — 키 `equity·deposit·monthly_rent·key_money·startup_cost·desired_loan·area_sqm·headcount`.

- [ ] **Step 1: 실패 테스트(표기 20종)**

```python
# minseok/apps/chat/tests/domain/test_amount_parser.py
import pytest

from chat.domain.services.amount_parser import fmt_won, parse_budget_krw, parse_labeled_amounts, parse_won


@pytest.mark.parametrize("text,won", [
    ("1억 2천으로 카페", 120_000_000), ("8천만원이면", 80_000_000), ("5000만원", 50_000_000),
    ("1.5억", 150_000_000), ("3,000만원", 30_000_000), ("5천", 50_000_000), ("2억", 200_000_000),
])
def test_금액_표기(text, won):
    assert parse_won(text) == won
    assert parse_budget_krw(text) == won or "5천" == text.strip() or "3,000" in text


def test_기존_예산_파서는_그대로다():
    assert parse_budget_krw("1억 2천으로 카페") == 120_000_000
    assert parse_budget_krw("예산은 얼마") is None


@pytest.mark.parametrize("text,expected", [
    ("자기자본 1억, 보증금 5천에 월세 300", {"equity": 100_000_000, "deposit": 50_000_000, "monthly_rent": 3_000_000}),
    ("내 돈 7천만원이고 월세는 250만원", {"equity": 70_000_000, "monthly_rent": 2_500_000}),
    ("임대료 180에 권리금 2천", {"monthly_rent": 1_800_000, "key_money": 20_000_000}),
    ("인테리어 3천만원 잡고 대출 5천 생각 중", {"startup_cost": 30_000_000, "desired_loan": 50_000_000}),
    ("20평 매장, 알바 2명", {"area_sqm": 66.1, "headcount": 2}),
    ("66㎡에 직원 1명", {"area_sqm": 66.0, "headcount": 1}),
    ("자본금 1.5억", {"equity": 150_000_000}),
    ("가진 돈 3억이야", {"equity": 300_000_000}),
    ("월세 300만 원", {"monthly_rent": 3_000_000}),
    ("보증금 1억 월세 500", {"deposit": 100_000_000, "monthly_rent": 5_000_000}),
    ("성수동 카페 어때?", {}),
    ("1억으로 치킨집", {}),  # 라벨 없는 단독 금액은 예산(기존 경로) — 라벨 파서는 비운다
])
def test_라벨_금액(text, expected):
    got = parse_labeled_amounts(text)
    assert {k: (round(v, 1) if isinstance(v, float) else v) for k, v in got.items()} == expected


def test_fmt_won():
    assert fmt_won(120_000_000) == "1억 2,000만원" and fmt_won(80_360_000) == "8,036만원"
```

- [ ] **Step 2: 실패 확인** — `ModuleNotFoundError`

- [ ] **Step 3: 파서 작성**

```python
# minseok/apps/chat/domain/services/amount_parser.py
"""한국어 금액·라벨 파서 — 결정론. LLM 추출을 쓰지 않는다(추출 오류 = 계산 오류).

parse_budget_krw·fmt_won은 chat_interactor에서 옮겨 왔다(동작 동일). parse_labeled_amounts는
"자기자본 1억, 보증금 5천에 월세 300"을 재무 엔진 입력으로 바꾼다. 월세·임대료의 단위 없는 숫자는
만원(관용)이다.
"""
from __future__ import annotations

import re

PYEONG_TO_SQM = 3.3058

_BUDGET_RE = re.compile(r"(\d+(?:\.\d+)?)\s*억(?:\s*(\d+)\s*천?\s*만?)?|(\d+(?:,\d{3})*)\s*(천만|만)\s*원?")
_CHEON_RE = re.compile(r"(\d+)\s*천(?!\s*만)")  # "5천" 단독 = 천만원 단위
_AMOUNT = r"(\d+(?:\.\d+)?)\s*억(?:\s*(\d+)\s*천?\s*만?)?|(\d+(?:,\d{3})*)\s*(천만|만)\s*원?|(\d+)\s*천(?!\s*만)|(\d{2,4})(?![\d,.]|\s*(?:억|천|만|평|㎡|명|%|개|년|월|일|시))"
_LABELS: tuple[tuple[str, str], ...] = (
    ("equity", r"자기\s*자본|자본금|내\s*돈|가진\s*돈|보유\s*자금|수중에"),
    ("deposit", r"보증금"),
    ("monthly_rent", r"월세|임대료|월\s*임대"),
    ("key_money", r"권리금"),
    ("startup_cost", r"인테리어|설비|시설비"),
    ("desired_loan", r"대출"),
)
_LABELED = {
    key: re.compile(rf"(?:{words})\s*(?:은|는|이|가|을|를|으로|로|도|:)?\s*(?:{_AMOUNT})")
    for key, words in _LABELS
}
_PYEONG_RE = re.compile(r"(\d+(?:\.\d+)?)\s*평")
_SQM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:㎡|m2|제곱미터)")
_HEADCOUNT_RE = re.compile(r"(?:직원|알바|아르바이트|종업원)\s*(\d+)\s*명|(\d+)\s*명\s*(?:직원|알바|고용|쓰)")


def fmt_won(amount: float) -> str:
    """1억 2,000만원 · 8,036만원 — 만원 단위, 억은 앞에 뗀다."""
    man = int(round(amount / 10_000))
    if man >= 10_000:
        eok, rest = divmod(man, 10_000)
        return f"{eok}억원" if rest == 0 else f"{eok}억 {rest:,}만원"
    return f"{man:,}만원"


def parse_budget_krw(text: str) -> int | None:
    """"1억 2천", "8천만원", "5000만원", "1.5억" → 원. 못 읽으면 None(기존 예산 경로와 동일)."""
    m = _BUDGET_RE.search(text)
    if not m:
        return None
    if m.group(1):
        won = float(m.group(1)) * 100_000_000
        if m.group(2):
            won += int(m.group(2)) * 10_000_000
        return int(won)
    n = int(m.group(3).replace(",", ""))
    return n * (10_000_000 if m.group(4) == "천만" else 10_000)


def parse_won(text: str) -> int | None:
    """parse_budget_krw + "5천"(천만원 단위) 표기."""
    won = parse_budget_krw(text)
    if won is not None:
        return won
    m = _CHEON_RE.search(text)
    return int(m.group(1)) * 10_000_000 if m else None


def _amount_from_match(m: re.Match, bare_unit: int) -> int | None:
    if m.group(1):
        return int(float(m.group(1)) * 100_000_000 + (int(m.group(2)) * 10_000_000 if m.group(2) else 0))
    if m.group(3):
        return int(m.group(3).replace(",", "")) * (10_000_000 if m.group(4) == "천만" else 10_000)
    if m.group(5):
        return int(m.group(5)) * 10_000_000
    if m.group(6):
        return int(m.group(6)) * bare_unit
    return None


def parse_labeled_amounts(text: str) -> dict[str, int | float]:
    """라벨이 붙은 금액·면적·인원만 뽑는다. 라벨 없는 단독 금액은 예산 경로(parse_budget_krw)가 맡는다."""
    out: dict[str, int | float] = {}
    for key, pattern in _LABELED.items():
        m = pattern.search(text)
        if not m:
            continue
        bare_unit = 10_000 if key in ("monthly_rent",) else 0
        amount = _amount_from_match(m, bare_unit)
        if amount:
            out[key] = amount
    if (m := _PYEONG_RE.search(text)):
        out["area_sqm"] = round(float(m.group(1)) * PYEONG_TO_SQM, 1)
    elif (m := _SQM_RE.search(text)):
        out["area_sqm"] = float(m.group(1))
    if (m := _HEADCOUNT_RE.search(text)):
        out["headcount"] = int(m.group(1) or m.group(2))
    return out
```

- [ ] **Step 4: chat_interactor에서 정의 제거 + import** — `chat_interactor.py` 556~596행의 `_BUDGET_RE`, `fmt_won`, `parse_budget_krw` 정의를 지우고, 상단 import(`from chat.domain.services import answer_guard` 아래)에:

```python
from chat.domain.services.amount_parser import fmt_won, parse_budget_krw, parse_labeled_amounts
```
(`SMALL_SAMPLE_STORES`·`GENERIC_SERVICE_CODE`·`BUDGET_RESERVE_RATIO`·`_INDUSTRY_ALIASES`는 그 자리에 남긴다. `test_chat_interactor.py:2293`은 `from chat.app.use_cases.chat_interactor import parse_budget_krw`를 쓰므로 재수출로 계속 통과한다.)

- [ ] **Step 5: 통과 확인** — `mcp run_backend_tests target=minseok/apps/chat/tests/domain/test_amount_parser.py` → 전부 passed; `target=minseok/apps/chat/tests/app/use_cases/test_chat_interactor.py` → 기존 전부 passed(무손상). 표기 케이스 중 `_AMOUNT`의 단위 없는 숫자 그룹이 "1억"의 "1"을 잡지 않는지(음의 lookahead에 `억` 포함) 실패가 나면 거기부터 본다.

- [ ] **커밋 경계**: `refactor(chat): 금액 파서를 도메인 서비스로 이관 + 라벨 금액(보증금·월세·대출·면적·인원) 파서`

---

### Task 9: chat — 재무 경로(트리거·폴백·첫 줄·카드·승계)

**Files:**
- Modify: `minseok/apps/chat/app/dtos/chat_dto.py`(`FinanceCard` + `AskResponse.finance`), `minseok/apps/chat/app/use_cases/chat_interactor.py`(생성자·트리거·`_finance_plan`·phase2 블록·payload·미지원 고지 가드), `minseok/apps/chat/dependencies/chat_provider.py`(포트 주입)
- Test: `minseok/apps/chat/tests/app/use_cases/test_chat_interactor.py`(신규 테스트 8종 추가)

**Interfaces:**
- Consumes: `AreaFinancePort`, `AreaFinanceRequest`, `AreaFinancePlanInfo`, `parse_labeled_amounts`, `parse_budget_krw`, `UserProfileSummary.budget_label`.
- Produces: `ChatInteractor(..., finance: AreaFinancePort | None = None)`, `FinanceCard`, payload `{"finance": {...}}`, 상수 `_FINANCE_RE`, `EQUITY_BY_BUDGET_LABEL`.

- [ ] **Step 1: DTO**

`minseok/apps/chat/app/dtos/chat_dto.py` — `NewsCardItem` 아래에 추가, `AskResponse`에 필드 추가:

```python
class FinanceInputCard(BaseModel):
    key: str
    value: float
    source: str
    note: str


class FinanceCard(BaseModel):
    """재무 계산 카드 — 첫 줄(코드 작성)·입력값과 출처·핵심 수치. 다음 턴 승계 키이기도 하다."""

    trdarCode: int
    trdarName: str
    serviceCode: str
    serviceName: str
    headline: str
    assumptionNote: str
    inputs: list[FinanceInputCard]
    capex: int
    fundingGap: int
    bepMonthlySales: int
    attainment: float | None
    monthlyProfit: int | None
    runwayMonths: float | None
    rentLevel: str | None


class AskResponse(BaseModel):
    text: str
    recommendations: list[AreaRecommendation]
    conversationId: int
    stock: StockCard | None = None
    news: list[NewsCardItem] = []
    finance: FinanceCard | None = None
```

- [ ] **Step 2: 실패 테스트(신규 8종)** — `test_chat_interactor.py` 끝에 추가. 상단 import에 `from hub.app.dtos.area_finance_dto import AreaFinancePlanInfo, AreaFinanceRequest, FinanceInputItem` 추가. `_build`에 `finance=None` 인자를 더하고 `ChatInteractor(...)` 호출에 `finance=finance` 전달, 반환 dict에도 `finance=finance` 추가.

```python
# --- 재무 경로(FINANCE_ENGINE_2026-09-16) ---

class _StubFinance:
    def __init__(self, info=None, none_for=()):
        self.info, self.none_for, self.requests = info, none_for, []

    async def plan(self, request: AreaFinanceRequest):
        self.requests.append(request)
        return None if request.trdar_code in self.none_for else self.info


def _finance_info(**over) -> AreaFinancePlanInfo:
    base = dict(
        trdar_code=1000001, trdar_name="테스트상권", service_code="CS100010", service_name="커피-음료",
        headline="자기자본 1억원(입력)·월세 300만원(기타 소규모 상가 평균, 33㎡ 가정)으로 계산하면 손익분기 월매출은 434만원이에요. 부족 자금 1,900만원이 필요해요.",
        assumption_note="가정: 보증금은 월세 10개월분 가정 · 1인 운영 가정",
        inputs=(FinanceInputItem("equity", 100_000_000, "input", ""), FinanceInputItem("monthly_rent", 3_000_000, "area_avg", "기타 평균")),
        capex=110_000_000, funding_gap=19_000_000, loan=19_000_000, bep_monthly_sales=4_340_000,
        attainment=3.46, monthly_profit=10_400_000, runway_months=None, stress_runway=((1.0, None), (2.0, None)),
        expected_monthly_sales=15_000_000, rent_level="zone",
    )
    base.update(over)
    return AreaFinancePlanInfo(**base)


async def test_재무_어휘가_있으면_첫_줄을_코드가_쓰고_카드를_동반한다(monkeypatch):
    finance = _StubFinance(_finance_info())
    interactor, llm, stubs = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], finance=finance)
    result = await interactor.ask("성수동 카페, 자기자본 1억이면 월세 300에 몇 달 버텨?")
    assert result.text.startswith("자기자본 1억원(입력)")
    assert result.finance is not None and result.finance.fundingGap == 19_000_000
    req = finance.requests[0]
    assert req.equity == 100_000_000 and req.monthly_rent == 3_000_000 and req.sources == {}
    assert "[재무 계산 — 코드가 정함]" in llm.calls[-1][0]  # phase2 컨텍스트에 블록 주입
    assert stubs["conversations"].payloads[-1]["finance"]["fundingGap"] == 19_000_000


async def test_재무_어휘가_없으면_기존_경로_그대로다(monkeypatch):  # 무손상
    finance = _StubFinance(_finance_info())
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], finance=finance)
    result = await interactor.ask("성수동 카페 어때?")
    assert result.finance is None and finance.requests == []


async def test_자기자본이_없으면_프로파일_예산_밴드_중앙값을_쓴다(monkeypatch):
    finance = _StubFinance(_finance_info())
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON],
                              finance=finance, profiles=_StubProfiles(_profile()))
    await interactor.ask("성수동 카페 월세 300이면 손익분기 얼마야?", user_id=7)
    req = finance.requests[0]
    assert req.equity == 75_000_000 and req.sources["equity"] == "profile"
    assert "5천만~1억원" in req.equity_note


async def test_자기자본이_어디에도_없으면_되묻고_엔진을_부르지_않는다(monkeypatch):
    finance = _StubFinance(_finance_info())
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], finance=finance)
    result = await interactor.ask("성수동 카페 월세 300이면 손익분기 얼마야?")
    assert finance.requests == [] and result.finance is None
    assert "자기자본" in result.text and "알려주시면" in result.text


async def test_후속_턴은_직전_카드_입력을_이어받고_바뀐_값만_교체한다(monkeypatch):
    prev = {"finance": {"trdarCode": 1000001, "trdarName": "테스트상권", "serviceCode": "CS100010",
                        "serviceName": "커피-음료", "headline": "h", "assumptionNote": "", "capex": 0,
                        "fundingGap": 0, "bepMonthlySales": 0, "attainment": None, "monthlyProfit": None,
                        "runwayMonths": None, "rentLevel": "zone",
                        "inputs": [{"key": "equity", "value": 100_000_000, "source": "input", "note": ""},
                                   {"key": "monthly_rent", "value": 3_000_000, "source": "input", "note": ""},
                                   {"key": "deposit", "value": 30_000_000, "source": "assumed", "note": "가정"}]},
            "recommendations": [{"id": "1000001", "name": "테스트상권", "serviceCode": "CS100010", "category": "커피-음료"}]}
    conversations = _StubConversations(history=[
        Message(id=1, conversation_id=100, role="user", content="성수동 카페 자기자본 1억 월세 300", created_at=_NOW),
        Message(id=2, conversation_id=100, role="assistant", content="h", created_at=_NOW, payload=prev),
    ])
    finance = _StubFinance(_finance_info())
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_EMPTY, PHASE2_JSON],
                              finance=finance, conversations=conversations)
    await interactor.ask("월세 250이면?", conversation_id=100)
    req = finance.requests[0]
    assert req.monthly_rent == 2_500_000 and req.sources.get("monthly_rent") is None
    assert req.equity == 100_000_000 and req.sources["equity"] == "history"
    assert req.deposit is None  # 가정치는 승계하지 않는다(다시 가정)


async def test_엔진이_None이면_월세를_되묻는다(monkeypatch):
    finance = _StubFinance(_finance_info(), none_for=(1000001,))
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], finance=finance)
    result = await interactor.ask("성수동 카페 자기자본 1억이면 몇 달 버텨?")
    assert result.finance is None and "월세" in result.text and "알려주시면" in result.text


async def test_재무_포트가_있으면_임대료_미지원_고지는_붙지_않는다(monkeypatch):
    finance = _StubFinance(_finance_info())
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], finance=finance)
    result = await interactor.ask("역삼동 카페 자기자본 1억 월세 400 어때?")
    assert "임대료·보증금·권리금 데이터는 제공하지 않아요" not in result.text


async def test_재무_블록에는_대출_권유_금지_규칙이_실린다(monkeypatch):
    finance = _StubFinance(_finance_info())
    interactor, llm, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], finance=finance)
    await interactor.ask("성수동 카페 자기자본 1억 월세 300")
    ctx = llm.calls[-1][0]
    assert "대출 상품이나 은행을 권하지 말 것" in ctx and "재계산하거나 다른 금액을 만들지 말 것" in ctx
```

- [ ] **Step 3: 실패 확인** — `TypeError: __init__() got an unexpected keyword argument 'finance'`

- [ ] **Step 4: 인터랙터 구현**

(a) import 추가:
```python
from chat.app.dtos.chat_dto import FinanceCard, FinanceInputCard  # 기존 chat_dto import 묶음에 합친다
from hub.app.dtos.area_finance_dto import AreaFinancePlanInfo, AreaFinanceRequest
from hub.app.ports.output.area_finance_port import AreaFinancePort
```

(b) 모듈 상수 — `_MARKET_UNSUPPORTED_NOTICES` 바로 아래:
```python
# 재무 질문 트리거(FINANCE_ENGINE §5-1) — 상권·업종이 정해진 뒤에만 탄다. 예산만 있는 질문은 _budget_notice(무손상).
_FINANCE_RE = re.compile(r"자기\s*자본|자본금|내\s*돈|가진\s*돈|보증금|월세|임대료|대출|버틸|버티|손익|적자|흑자|BEP|얼마나\s*남")
# 프로파일 예산 밴드 → 자기자본 대체값(밴드 중앙값, 상단 개방 밴드는 하한). 라벨 정의는 recommendation 도메인.
EQUITY_BY_BUDGET_LABEL = {
    "3천만원 미만": 20_000_000, "3천만~5천만원": 40_000_000, "5천만~1억원": 75_000_000,
    "1억~3억원": 200_000_000, "3억원 이상": 300_000_000,
}
_FINANCE_FIELDS = ("equity", "deposit", "monthly_rent", "key_money", "startup_cost", "area_sqm", "headcount", "desired_loan")
_FINANCE_RULES = (
    "[재무 계산 규칙] 위 재무 수치를 재계산하거나 다른 금액을 만들지 말 것. 병기된 값과 가정을 그대로 두고"
    " 리스크(달성률·부족 자금·금리)와 대안(면적 축소·인건비·업종 대안)만 서술할 것. 대출 상품이나 은행을 권하지 말 것."
)
```

(c) 생성자 — `paper: PaperDecisionPort | None = None,` 뒤에 `finance: AreaFinancePort | None = None,` 추가, 본문에 `self._finance = finance`.

(d) 미지원 고지 가드 — 2027행의 `_unsupported_notice(prompt, _MARKET_UNSUPPORTED_NOTICES)`를 `_unsupported_notice(prompt, self._market_unsupported_table())`로 바꾸고 메서드 추가:
```python
    def _market_unsupported_table(self):
        """재무 포트가 배선되면 임대료는 미지원 축이 아니다(권역 평균 폴백 포함)."""
        if self._finance is None:
            return _MARKET_UNSUPPORTED_NOTICES
        return tuple(row for row in _MARKET_UNSUPPORTED_NOTICES if "임대료" not in row[0].pattern)
```

(e) 헬퍼 3개(`_previous_service` 근처에 추가):
```python
    @staticmethod
    def _previous_finance_inputs(history: list[Message]) -> dict[str, float]:
        """직전 재무 카드의 입력값(가정치 제외) — 승계용."""
        for m in reversed(history):
            card = (m.payload or {}).get("finance")
            if card:
                return {i["key"]: i["value"] for i in card.get("inputs", []) if i.get("source") != "assumed"}
        return {}

    def _finance_request(
        self, prompt: str, history: list[Message], profile: UserProfileSummary | None,
        trdar_code: int, service_code: str,
    ) -> AreaFinanceRequest | None:
        """입력 → 이력 → 프로파일(자기자본만) 순으로 채운다. 자기자본이 끝내 없으면 None(되묻기)."""
        given = parse_labeled_amounts(prompt)
        if "equity" not in given and not any(k in given for k in _FINANCE_FIELDS):
            solo = parse_budget_krw(prompt)
            if solo is not None:
                given["equity"] = solo
        inherited = self._previous_finance_inputs(history)
        sources: dict[str, str] = {}
        values: dict[str, float] = {}
        for key in _FINANCE_FIELDS:
            if key in given:
                values[key] = given[key]
            elif key in inherited:
                values[key] = inherited[key]
                sources[key] = "history"
        equity_note = ""
        if "equity" not in values and profile is not None:
            equity = EQUITY_BY_BUDGET_LABEL.get(profile.budget_label)
            if equity:
                values["equity"], sources["equity"] = equity, "profile"
                equity_note = f"프로파일 예산 {profile.budget_label}의 중앙값"
        if "equity" not in values:
            return None
        return AreaFinanceRequest(
            trdar_code=trdar_code, service_code=service_code, equity=int(values["equity"]),
            deposit=int(values["deposit"]) if "deposit" in values else None,
            monthly_rent=int(values["monthly_rent"]) if "monthly_rent" in values else None,
            key_money=int(values["key_money"]) if "key_money" in values else None,
            startup_cost=int(values["startup_cost"]) if "startup_cost" in values else None,
            area_sqm=float(values["area_sqm"]) if "area_sqm" in values else None,
            headcount=int(values["headcount"]) if "headcount" in values else None,
            desired_loan=int(values["desired_loan"]) if "desired_loan" in values else None,
            sources=sources, equity_note=equity_note,
        )

    @staticmethod
    def _finance_card(info: AreaFinancePlanInfo) -> FinanceCard:
        return FinanceCard(
            trdarCode=info.trdar_code, trdarName=info.trdar_name, serviceCode=info.service_code,
            serviceName=info.service_name, headline=info.headline, assumptionNote=info.assumption_note,
            inputs=[FinanceInputCard(key=i.key, value=i.value, source=i.source, note=i.note) for i in info.inputs],
            capex=info.capex, fundingGap=info.funding_gap, bepMonthlySales=info.bep_monthly_sales,
            attainment=info.attainment, monthlyProfit=info.monthly_profit, runwayMonths=info.runway_months,
            rentLevel=info.rent_level,
        )
```

(f) market 경로 — `area_articles = await self._market_news.search(prompt, limit=4)` 바로 뒤에:
```python
        # 재무 경로(FINANCE_ENGINE) — 1순위 상권·확정 업종으로 결정론 계산. 첫 줄은 코드가 쓴다.
        finance_info: AreaFinancePlanInfo | None = None
        finance_note = ""
        wants_finance = self._finance is not None and (
            _FINANCE_RE.search(prompt) or len(parse_labeled_amounts(prompt)) >= 2
        )
        if wants_finance:
            request = self._finance_request(prompt, history, profile, valid_codes[0], service_code)
            if request is None:
                finance_note = "※ 자기자본(내 돈)을 알려주시면 손익분기·부족 자금·버틸 기간을 계산해 드려요.\n\n"
            else:
                try:
                    finance_info = await self._finance.plan(request)
                except Exception:
                    logger.warning("[chat] 재무 계산 실패", exc_info=True)
                if finance_info is None and request is not None:
                    finance_note = "※ 이 상권은 임대료 자료가 없어요 — 월세를 알려주시면 계산해 드려요.\n\n"
```
phase2 컨텍스트 — `if profile is not None: stats_context_lines.append(self._profile_market_block(profile))` 앞에:
```python
        if finance_info is not None:
            stats_context_lines.append(
                f"[재무 계산 — 코드가 정함] {finance_info.headline} {finance_info.assumption_note}\n{_FINANCE_RULES}"
            )
```
텍스트 조립 — `text = (await self._budget_notice(...)) + ...` 줄을 다음으로:
```python
        if finance_info is not None:
            text = f"{finance_info.headline}\n{finance_info.assumption_note}\n\n{text}" if text else finance_info.headline
        text = (await self._budget_notice(prompt, profile, history)) + _unsupported_notice(prompt, self._market_unsupported_table()) + radius_note + finance_note + text
```
payload — `payload={"recommendations": [...]}`를:
```python
        payload: dict = {"recommendations": [r.model_dump() for r in recommendations]}
        finance_card = self._finance_card(finance_info) if finance_info is not None else None
        if finance_card is not None:
            payload["finance"] = finance_card.model_dump()
        await self._conversations.add_message(conversation_id, "assistant", text, payload=payload)
```
반환 — `return AskResponse(text=text, recommendations=recommendations, conversationId=conversation_id, finance=finance_card)`.

(g) `chat_provider.py` — import `from hub.app.ports.output.area_finance_port import AreaFinancePort`, `from hub.dependencies.area_finance_provider import get_area_finance_port`; 시그니처에 `finance: AreaFinancePort = Depends(get_area_finance_port),`; `ChatInteractor(..., finance=finance)`.

- [ ] **Step 5: 통과 확인** — `mcp run_backend_tests target=minseok/apps/chat/tests` → 신규 8 + 기존 전부 passed. `test_임대료_질문은_미지원_고지가_문두에_붙는다`는 `finance=None`이라 계속 통과해야 한다.

- [ ] **Step 6: 구조 검사** — `mcp run_import_linter` 5 KEPT(chat은 hub만 import).

- [ ] **커밋 경계**: `feat(chat): 재무 질문 경로 — 라벨 파서·이력/프로파일 폴백·코드 첫 줄·finance 카드·승계`

---

### Task 10: 평가 — 골든셋 10문항 + 채점 지표 + 러너 스텁

**Files:**
- Modify: `minseok/apps/chat/tests/eval/golden_set.jsonl`(끝에 10줄), `minseok/apps/chat/domain/value_objects/eval_trace.py`(category 주석), `minseok/apps/chat/domain/services/eval_scorer.py`(`finance_answer_rate` + `loan_solicitation` 절대 규칙), `minseok/apps/chat/tests/eval/test_quality_gate.py`(current·출력), `minseok/apps/chat/tests/eval/snapshot_stubs.py`(`SnapshotFinance`), `minseok/apps/chat/tests/eval/test_eval_runner.py`(`finance=SnapshotFinance()`)
- Test: `minseok/apps/chat/tests/domain/test_eval_scorer.py`(2종 추가)

**Interfaces:**
- Produces: `EvalReport.finance_answer_rate: float | None`, 위반 규칙 `loan_solicitation`, 카테고리 `market_finance`.

- [ ] **Step 1: 골든셋 10줄 추가**

```jsonl
{"case_id": "MF01", "category": "market_finance", "prompt": "성수동에 카페, 자기자본 1억이고 월세 300이면 몇 달 버텨?", "expected_intent": "market", "region": "성수동"}
{"case_id": "MF02", "category": "market_finance", "prompt": "홍대 술집 차리려는데 내 돈 5천, 보증금 3천 월세 250이면 손익분기 얼마야?", "expected_intent": "market", "region": "홍대"}
{"case_id": "MF03", "category": "market_finance", "prompt": "강남역 근처 미용실, 자본금 2억에 직원 2명 쓰면 적자 안 나?", "expected_intent": "market", "region": "강남역"}
{"case_id": "MF04", "category": "market_finance", "prompt": "연남동 분식집 자기자본 7천만원 월세 180 부족한 돈 얼마나 돼?", "expected_intent": "market", "region": "연남동"}
{"case_id": "MF05", "category": "market_finance", "prompt": "잠실 치킨집 가진 돈 1.5억, 대출 5천 받으면 이자 부담 어때?", "expected_intent": "market", "region": "잠실"}
{"case_id": "MF06", "category": "market_finance", "prompt": "신촌 편의점 자기자본 1억 20평 월세 400이면 손익분기 넘어?", "expected_intent": "market", "region": "신촌"}
{"case_id": "MF07", "category": "market_finance", "prompt": "건대입구 한식집 내 돈 8천 월세 300 권리금 2천 계산해줘", "expected_intent": "market", "region": "건대입구"}
{"case_id": "MF08", "category": "market_finance", "prompt": "망원동 카페 자기자본 6천만원이면 얼마나 버틸 수 있어?", "expected_intent": "market", "region": "망원동"}
{"case_id": "MF09", "category": "market_finance", "prompt": "혜화동 카페 월세 200이면 손익분기 얼마야?", "expected_intent": "market", "region": "혜화동"}
{"case_id": "MF10", "category": "market_finance", "prompt": "노원역 헬스장 자본금 3억 인테리어 1억 월세 500 흑자 가능해?", "expected_intent": "market", "region": "노원역"}
```
(MF09는 자기자본 없음 → 되묻기가 정답.)

`eval_trace.py`의 category 주석에 `| market_finance` 추가.

- [ ] **Step 2: 실패 테스트 — 채점기**

```python
# test_eval_scorer.py 끝에 추가

# --- 재무 답변(FINANCE_ENGINE) ---

def test_재무_케이스는_손익분기와_부족자금_또는_되묻기를_답으로_친다():
    cases = [_case("F1", category="market_finance", prompt="성수동 카페 자기자본 1억 월세 300"),
             _case("F2", category="market_finance", prompt="혜화동 카페 월세 200"),
             _case("F3", category="market_finance", prompt="홍대 술집 내 돈 5천")]
    traces = [_trace("F1", answer_text="…손익분기 월매출은 434만원이에요. 부족 자금 1,900만원이 필요해요."),
              _trace("F2", answer_text="※ 자기자본(내 돈)을 알려주시면 손익분기·부족 자금·버틸 기간을 계산해 드려요."),
              _trace("F3", answer_text="이 상권은 유동인구가 많아요.")]
    report = score(cases, traces)
    assert report.finance_answer_rate == 2 / 3


def test_재무_답변의_대출_권유는_절대_규칙_위반():
    cases = [_case("F1", category="market_finance", prompt="성수동 카페 자기자본 1억")]
    traces = [_trace("F1", answer_text="손익분기… 부족 자금 2천만원은 A은행 대출을 추천해요.")]
    report = score(cases, traces)
    assert any(v.rule == "loan_solicitation" for v in report.violations)
```

- [ ] **Step 3: 실패 확인** — `AttributeError: 'EvalReport' object has no attribute 'finance_answer_rate'`

- [ ] **Step 4: 채점기 구현** — `eval_scorer.py`:
  - 상단 지표 docstring에 `- finance_answer_rate : 재무 케이스 중 손익분기+부족 자금(또는 자기자본 되묻기)이 답에 있는 비율` 추가.
  - 모듈 상수 추가:
    ```python
    _FINANCE_ANSWERED = re.compile(r"손익분기.*부족 자금|자기자본\(내 돈\)을 알려주시면", re.S)
    _LOAN_SOLICIT = re.compile(r"(?:대출|상품)\s*(?:을|를)?\s*(?:추천|권해|받으세요|받아\s*보세요)|은행\s*(?:을|를)?\s*추천")
    ```
  - `EvalReport` 데이터클래스에 `finance_answer_rate: float | None` 필드 추가(기존 필드 순서 뒤).
  - `score()` 안 risk_mention 계산 뒤:
    ```python
    finance_cases = [(c, t) for c, t in scored if c.category == "market_finance"]
    finance_ok = sum(1 for _, t in finance_cases if _FINANCE_ANSWERED.search(t.answer_text))
    finance_answer_rate = _rate(finance_ok, len(finance_cases))
    ```
  - 절대 규칙 루프(`for c, t in scored:`) 안, `if t.final_intent == "market" and t.recommendation_codes:` 블록 앞에:
    ```python
        if c.category == "market_finance" and t.answer_text:
            m = _LOAN_SOLICIT.search(t.answer_text)
            if m:
                violations.append(RuleViolation(c.case_id, "loan_solicitation", m.group()))
    ```
  - `EvalReport(...)` 생성부에 `finance_answer_rate=finance_answer_rate` 전달.
  - `test_quality_gate.py`: `current`에 `"finance_answer_rate": report.finance_answer_rate,` 추가, `_REGRESSION_KEYS`에 `"finance_answer_rate"` 추가, print 줄에 `finance={report.finance_answer_rate}` 덧붙임.

- [ ] **Step 5: 통과 확인** — `mcp run_backend_tests target=minseok/apps/chat/tests/domain/test_eval_scorer.py` → 전부 passed. `target=minseok/apps/chat/tests/eval/test_quality_gate.py` → 기존 trace로 passed(새 케이스는 trace 없음 → errored로 집계되지만 baseline `total`은 회귀 키가 아니다. `errored`가 절대 규칙에 걸리는지 확인: 걸리면 러너 실행 전까지 새 케이스를 별도 파일 `golden_finance.jsonl`에 두었다가 러너 실행 시 합친다 — 이 경우 `golden.py`의 `load_cases`가 두 파일을 읽게 바꾼다).

- [ ] **Step 6: 러너 스텁** — `snapshot_stubs.py` 끝에:

```python
class SnapshotFinance:
    """AreaFinancePort 고정 스텁 — 시드 결정론 산술(엔진 정본은 market, 여기서는 계약 DTO만 만든다)."""

    RENT_PER_SQM = 45_000
    COST_RATIO = 0.35
    LOAN_RATE = 4.5

    def __init__(self) -> None:
        self.requests: list = []

    async def plan(self, request):
        from hub.app.dtos.area_finance_dto import AreaFinancePlanInfo, FinanceInputItem

        self.requests.append(request)
        rent = request.monthly_rent or int(self.RENT_PER_SQM * (request.area_sqm or 33))
        deposit = request.deposit if request.deposit is not None else rent * 10
        startup = request.startup_cost if request.startup_cost is not None else 80_000_000
        payroll = 10_320 * 209 * (request.headcount or 0)
        capex = startup + deposit + (request.key_money or 0)
        opex = rent + payroll
        gap = max(0, capex + opex * 3 - request.equity)
        loan = max(request.desired_loan or 0, gap)
        fixed = opex + round(loan * self.LOAN_RATE / 100 / 12)
        bep = round(fixed / (1 - self.COST_RATIO))
        sales = 12_000_000 + (_seed(request.trdar_code) % 9) * 1_000_000
        profit = round(sales * (1 - self.COST_RATIO) - fixed)
        cash = max(0, request.equity + loan - capex)
        runway = None if profit >= 0 else round(cash / abs(profit), 1)
        headline = (f"자기자본 {request.equity // 10_000:,}만원(입력)·월세 {rent // 10_000:,}만원"
                    f"({'입력' if request.monthly_rent else '권역 평균, 33㎡ 가정'})·창업비용 {startup // 10_000:,}만원(공정위 중앙값)"
                    f"으로 계산하면 손익분기 월매출은 {bep // 10_000:,}만원이에요. 점포당 월매출 {sales // 10_000:,}만원이면"
                    f" 달성률 {sales / bep:.0%}. 부족 자금 {gap // 10_000:,}만원이 필요해요."
                    + (f" 적자가 이어지면 약 {runway:.0f}개월 버틸 수 있어요." if runway else ""))
        return AreaFinancePlanInfo(
            trdar_code=request.trdar_code, trdar_name="", service_code=request.service_code, service_name="",
            headline=headline, assumption_note="가정: 보증금은 월세 10개월분 가정 · 1인 운영 가정 · 이자만 반영",
            inputs=(FinanceInputItem("equity", request.equity, "input", ""), FinanceInputItem("monthly_rent", rent, "input" if request.monthly_rent else "area_avg", "")),
            capex=capex, funding_gap=gap, loan=loan, bep_monthly_sales=bep, attainment=round(sales / bep, 2),
            monthly_profit=profit, runway_months=runway, stress_runway=((1.0, runway), (2.0, runway)),
            expected_monthly_sales=sales, rent_level="zone",
        )
```
`test_eval_runner.py`의 `ChatInteractor(...)` 호출에 `finance=SnapshotFinance(),` 추가(import 포함).

- [ ] **Step 7: 러너 실행(백엔드 PC, ollama 필요 — 맥에서는 skip)** — 사용자와 합의된 시점에:
```bash
ssh host 'cd ~/projects/com.redoceanmap && kubectl -n redocean exec deploy/backend -- python -m pytest apps/chat/tests/eval/test_eval_runner.py -m ollama -q -p no:cacheprovider'
```
그 뒤 PC에서 갱신된 `trace.jsonl`을 커밋·push(`window`), 맥에서 pull → `test_quality_gate.py` 실행 → `finance_answer_rate` 값을 스펙 G4에 기록. 회귀(-3%p)나 절대 규칙 위반이 나오면 프롬프트 블록 `_FINANCE_RULES` 문구를 조정하고 재실행한다.

- [ ] **커밋 경계**: `test(chat): 재무 골든셋 10문항 + finance_answer_rate·대출 권유 절대 규칙`

---

### Task 11: 문서 갱신

**Files:**
- Modify: `minseok/apps/market/_docs/CLAUDE.md`(조회 표 행 + "임대료·금리" 절), `minseok/apps/chat/_docs/CLAUDE.md`(포트 표 행 + market 의도 문단), `minseok/apps/hub/_docs/CLAUDE.md`(소유 계약 절), `minseok/_docs/ROADMAP.md:184`(B4), `minseok/_docs/FINANCE_ENGINE_2026-09-16.md`(상태·G5·G6 실측)

- [ ] **Step 1: market CLAUDE** — 조회 표에 행 추가:

```
| 프론트 `/market/trdar/{code}/finance?service_code=&equity=…` | `area_finance` 조회 슬라이스(2026-09, FINANCE_ENGINE) — 사용자 입력(자기자본·보증금·월세·면적·인원·희망대출) + 상권 점포당 월매출·R-ONE 임대료·공정위 창업비용·ECOS 금리 → 순수 `domain/services/finance_engine.py`(BEP·부족 자금·runway·금리 +1/+2%p·3시나리오). 값마다 출처 태그, 첫 줄은 `finance_narrator`. 허브 `AreaFinancePort`로 chat에도 공급. 임대료 미적재 + 월세 미입력은 404 |
```
"## 창업비용 회수기간 (B8)" 절 뒤에 절 추가:
```
## 임대료·금리 (창업 재무 엔진, 2026-09)

- `rent_benchmarks` — R-ONE 상가 임대동향(소규모·중대형·집합) 서울 64 CLS × 분기(2024Q3~), 임대료 원/㎡·공실률.
  수집 `scripts/collect_rone_rent.py`(분기 첫 달 10일 cron). 상권 매칭은 `domain/services/rent_matcher.py`
  (R-ONE 상권 59개 별칭 → 자치구 권역 → 서울). **대부분 권역 평균**이라 서술이 "동북권 평균"임을 병기한다.
- `interest_rates` — ECOS 기준금리·대출평균·기업대출 월별. 수집 `scripts/collect_ecos_rates.py`(매월 15일).
- 원가율·최저임금·기본 면적·보증금 개월·운전자금 개월은 `domain/services/cost_benchmarks.py` 상수(잠정, 출처 병기).
```

- [ ] **Step 2: chat CLAUDE** — 포트 표에 `| `AreaFinancePort` | market (`AreaFinanceGateway`) | 창업 재무 계산(BEP·부족 자금·runway) — 첫 줄은 코드 |` 추가. `market` 의도 문단 끝에:
```
  **재무 질문**(자기자본·보증금·월세·대출·버틸·손익 어휘 또는 라벨 금액 2개 이상)이면 1순위 상권·확정 업종으로
  허브 `AreaFinancePort`를 불러 **첫 줄을 코드가 쓴다**(값·출처 병기). 입력은 결정론 파서
  (`domain/services/amount_parser.py`) → 직전 finance 카드 승계 → 프로파일 예산 밴드(자기자본만) 순으로 채우고,
  자기자본이 끝내 없을 때만 되묻는다. phase2 컨텍스트에 `[재무 계산 — 코드가 정함]` 블록 + 재계산·대출 권유 금지 규칙.
  카드 payload `finance`가 다음 턴 승계 키다. 포트가 배선되면 임대료 미지원 고지(I-12)는 붙지 않는다.
```

- [ ] **Step 3: hub CLAUDE** — MemberDirectoryPort 절 서식으로 절 추가:
```
## 소유 계약 — AreaFinancePort

창업 재무 계산 협력. chat(소비)과 market(구현: area_finance 슬라이스)을 잇는다.

apps/hub/app/
├── ports/output/area_finance_port.py   # AreaFinancePort (ABC) — plan(request) → AreaFinancePlanInfo | None
└── dtos/area_finance_dto.py            # AreaFinanceRequest · AreaFinancePlanInfo · FinanceInputItem
apps/hub/dependencies/area_finance_provider.py  # get_area_finance_port (NotImplementedError 스텁)
배선: main.py `app.dependency_overrides[get_area_finance_port] = get_area_finance_gateway`.
```

- [ ] **Step 4: ROADMAP B4** — 184행을:
```
| B4 | ~~**창업비용·손익분기 서술**~~ — **완료(2026-09, FINANCE_ENGINE_2026-09-16)**. R-ONE 임대료·ECOS 금리 적재 + market `finance_engine`(BEP·부족 자금·runway·금리 스트레스) + chat 재무 경로(결정론 파서·이력/프로파일 폴백·코드 첫 줄). 은행 상품 추천은 범위 밖 | 오픈업 계산기·서울시 챗봇 예시 | 정본 [[minseok/_docs/FINANCE_ENGINE_2026-09-16\|FINANCE_ENGINE]] | M |
```

- [ ] **Step 5: 스펙 상태** — `FINANCE_ENGINE_2026-09-16.md` 4행 "설계 승인 대기"를 "구현 완료(날짜)"로, G5·G6 줄에 실측치(매칭률 등) 기록.

- [ ] **Step 6: 최종 검증** — `mcp run_backend_tests skip_integration=true`(전체) + `mcp run_import_linter` → 전부 passed·5 KEPT. 결과 요약을 스펙 §검증 표 옆에 적는다.

- [ ] **커밋 경계**: `docs(market,chat,hub): 창업 재무 엔진 문서 + ROADMAP B4 완료`

---

## Self-Review 결과

- 스펙 §새 기능 1~6 ↔ Task 1·2(데이터), 3(원가율·엔진), 4(매칭), 5(첫 줄), 6·7(슬라이스·허브), 8·9(chat). 개선 6항목 ↔ Task 8(예산 파서 확장), 9(프로파일 계산 입력·승계·임대료 고지 가드), 6(상권 비용 축 팩트 — 서술 노출은 비범위). 게이트 G1~G7 ↔ Task 3·4·5(G1), 8(G2), 6(G3), 10(G4), 2(G5·G6), 6·7·9·11(G7).
- 타입 일관성: `Sourced.value: float`이고 인터랙터가 `int` 금액을 넣는다(엔진이 `int(...)`로 정규화). `AreaFinancePlanInfo.stress_runway`는 게이트웨이·chat 스텁·테스트에서 같은 `((1.0, x), (2.0, y))` 모양. `sources`는 market DTO·허브 DTO 모두 `dict[str, str]`.
- 라우터 스키마의 `inputs`는 `dataclasses.fields(FinanceInputs)` 순서(equity, deposit, monthly_rent, …)를 그대로 쓴다 — 게이트웨이 테스트 `[:3] == ["equity", "deposit", "monthly_rent"]`와 일치.
- 알려진 열린 값: 원가율 잠정치(Task 3 Step 4의 `_SOURCE`에 "잠정" 명시). 실적재 수치(Task 2 Step 11)는 실행 후 기록.
