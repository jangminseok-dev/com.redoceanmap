from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.forecast_signal_config_orm import ForecastSignalConfigOrm
from stock.app.dtos.signal_config_dto import ActiveSignalConfig, ConfigHistoryRow
from stock.app.ports.output.signal_config_port import SignalConfigPort
from stock.domain.entities.analysis_config import AnalysisConfig

# 행 부재 폴백 키 — 시드 행과 같은 값이라 폴백 여부가 이력에 흔적을 남기지 않는다
_FALLBACK_KEY = "forecast_signal"


class SignalConfigPgRepository(SignalConfigPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def active(self) -> ActiveSignalConfig:
        row = (await self._session.execute(
            select(ForecastSignalConfigOrm).where(ForecastSignalConfigOrm.is_active)
        )).scalar()
        if row is None:
            # 마이그레이션 전·시드 유실 — 현행 코드 상수로 열화(기존 동작과 동일)
            return ActiveSignalConfig(key=_FALLBACK_KEY, config=AnalysisConfig.forecast_signal())
        return ActiveSignalConfig(key=row.config_key, config=self._to_config(row))

    async def activate(self, key: str, config: AnalysisConfig) -> None:
        now = datetime.now(UTC)
        # 해제 → INSERT를 같은 트랜잭션에 — 부분 유니크(활성 1행)가 순서를 강제한다
        await self._session.execute(
            update(ForecastSignalConfigOrm)
            .where(ForecastSignalConfigOrm.is_active)
            .values(is_active=False)
        )
        self._session.add(ForecastSignalConfigOrm(
            config_key=key, is_active=True,
            up_threshold=config.up_threshold, down_threshold=config.down_threshold,
            w_sentiment=config.w_sentiment, w_rsi=config.w_rsi, w_trend=config.w_trend,
            w_bb=config.w_bb, w_obv=config.w_obv, w_momentum=config.w_momentum,
            atr_veto=config.atr_veto, volume_confirm=config.volume_confirm,
            source="refit", activated_at=now,
        ))
        await self._session.commit()

    async def history(self) -> list[ConfigHistoryRow]:
        rows = (await self._session.execute(
            select(ForecastSignalConfigOrm).order_by(ForecastSignalConfigOrm.id.desc())
        )).scalars().all()
        return [
            ConfigHistoryRow(
                key=r.config_key, is_active=r.is_active, config=self._to_config(r),
                source=r.source, created_at=r.created_at, activated_at=r.activated_at,
            )
            for r in rows
        ]

    @staticmethod
    def _to_config(r: ForecastSignalConfigOrm) -> AnalysisConfig:
        return AnalysisConfig(
            up_threshold=r.up_threshold, down_threshold=r.down_threshold,
            w_sentiment=r.w_sentiment, w_rsi=r.w_rsi, w_trend=r.w_trend,
            w_bb=r.w_bb, w_obv=r.w_obv, w_momentum=r.w_momentum,
            atr_veto=r.atr_veto, volume_confirm=r.volume_confirm,
        )
