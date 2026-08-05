from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.stock_demand_orm import StockDemandOrm
from stock.app.ports.output.demand_record_port import DemandRecordPort


# 거래소 접미 — 야후 티커 후보 생성(yfinance_market_data_adapter)과 같은 목록.
# 알려진 접미만 벗긴다: 무조건 첫 '.'에서 자르면 BF.B 같은 미국 티커가 망가진다.
_EXCHANGE_SUFFIXES = (".KS", ".KQ")


def _canonical(ticker: str) -> str:
    """수요 집계용 표준형 — 같은 종목이 표기 때문에 갈라지지 않게 접미를 벗긴다.

    심볼 해석기는 "삼성전자"·"005930"을 6자리 코드로 주고, 프론트·히스토리 경로는
    저장 티커(005930.KS)를 그대로 넘긴다. 정규화가 없으면 한 종목이 두 행으로 쌓여
    질문 수가 쪼개진다 — 2026-08-05 실측에서 삼성전자가 005930(6) + 005930.KS(1)로
    갈라져 있었다. 이 수치는 워치리스트 자동 편입(screen_us_undervalued)의 입력이라
    순위가 어긋나고, 어드민 질문 인텔리전스 화면도 같은 종목을 두 줄로 보여준다.
    """
    t = ticker.strip().upper()
    for suffix in _EXCHANGE_SUFFIXES:
        if t.endswith(suffix):
            return t[: -len(suffix)]
    return t


class DemandPgRepository(DemandRecordPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, ticker: str) -> None:
        now = datetime.now(UTC)
        stmt = pg_insert(StockDemandOrm).values(
            ticker=_canonical(ticker), ask_count=1, last_asked_at=now,
        ).on_conflict_do_update(
            index_elements=["ticker"],
            set_={"ask_count": StockDemandOrm.ask_count + 1, "last_asked_at": now},
        )
        try:
            await self._session.execute(stmt)
            await self._session.commit()
        except Exception:
            # 실패 트랜잭션을 세션에 남기면 같은 세션을 쓰는 후속 조회(뉴스 등)까지
            # PendingRollbackError로 오염된다 — 되돌린 뒤 알린다(로깅은 호출자 몫).
            await self._session.rollback()
            raise
