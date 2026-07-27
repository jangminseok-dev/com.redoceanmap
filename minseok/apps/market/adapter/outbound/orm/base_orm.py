from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column


class MarketStatMixin:
    """팩트 공통 — 대리키 + 분기 + 상권 FK.

    차원 속성(상권명·상권구분·지역)은 trade_area 차원으로 정규화되어 여기서 제거됨.
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    year_quarter: Mapped[int] = mapped_column(Integer, index=True)
    # 단일 인덱스를 두지 않는다 — 각 팩트가 (trdar_code, year_quarter) 복합을 선언하고
    # 그 접두사가 이 컬럼을 커버한다(리비전 b2c3d4e5f6a7에서 단일 9개 제거).
    trdar_code: Mapped[int] = mapped_column(ForeignKey("trade_area.code"))
