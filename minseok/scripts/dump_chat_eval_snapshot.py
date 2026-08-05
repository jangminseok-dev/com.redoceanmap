"""chat 평가 스냅샷 덤프 — 실 market DB의 상권 요약·업종 코드를 JSON으로 고정한다.

상권 DB는 분기마다 갱신되므로, DB를 직접 쓰면 골든셋 정답이 시간에 따라 흔들린다.
한 번 떠서 커밋해두면 평가가 데이터 갱신과 독립이 되고, DB 없는 기기(맥)에서도
러너를 돌릴 수 있다. 팩트 통계는 덤프하지 않는다(snapshot_stubs가 시드 합성 —
전 상권 × 전 업종을 뜨면 수십 MB).

실행(백엔드 PC — market DB :5434 필요):
  docker run --rm --network host \
    -v /home/host/projects/com.redoceanmap:/work -w /work \
    -e PYTHONPATH=/work/minseok:/work/minseok/apps \
    minseok97/redoceanmap-backend:latest \
    python minseok/scripts/dump_chat_eval_snapshot.py

출력: minseok/apps/chat/tests/eval/snapshot/market_snapshot.json (git 커밋 대상)
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))

from core.key.secret_manager import get_secret_manager  # noqa: E402

OUT = ROOT / "apps" / "chat" / "tests" / "eval" / "snapshot" / "market_snapshot.json"


async def main() -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from market.adapter.outbound.gateways.commercial_data_gateway import (
        CommercialDataGateway,
    )

    sm = get_secret_manager()
    # 괄호 주의: .replace가 폴백 분기에만 묶이면 MARKET_DATABASE_URL을 쓸 때
    # 드라이버가 안 바뀌어 psycopg2를 찾다 죽는다(ingest_seoul_3nf와 같은 함정).
    url = (sm.get("MARKET_DATABASE_URL", None) or sm.require("DATABASE_URL")).replace(
        "postgresql://", "postgresql+psycopg://"
    )
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            gateway = CommercialDataGateway(session=session)
            summary = await gateway.get_area_summary()
            service_codes = await gateway.get_service_codes()
    finally:
        await engine.dispose()

    # 게이트웨이가 DB의 Decimal을 그대로 흘린다(DTO 선언은 int/float). 프로덕션은
    # 문자열 포맷팅만 해서 드러나지 않지만 JSON 직렬화는 죽는다 — 선언 타입대로 캐스팅한다.
    def _num(v, cast):
        return None if v is None else cast(v)

    payload = {
        "latest_quarter": summary.latest_quarter,
        "areas": [
            {
                "trdar_code": a.trdar_code, "trdar_name": a.trdar_name,
                "district_name": a.district_name, "adm_dong_name": a.adm_dong_name,
                "lat": _num(a.lat, float), "lng": _num(a.lng, float),
                "sales": _num(summary.sales_by_code.get(a.trdar_code), int),
            }
            for a in summary.areas
        ],
        "service_codes": [{"code": c.code, "name": c.name} for c in service_codes],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"저장: {OUT} — 상권 {len(payload['areas'])}개 · 업종 {len(payload['service_codes'])}개"
          f" · 최신 분기 {payload['latest_quarter']}")


if __name__ == "__main__":
    asyncio.run(main())
