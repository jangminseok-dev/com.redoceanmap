from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from recommendation.adapter.outbound.pg.alert_setting_pg_repository import AlertSettingPgRepository
from recommendation.app.ports.input.alert_setting_use_case import AlertSettingUseCase
from recommendation.app.use_cases.alert_setting_interactor import AlertSettingInteractor


def get_alert_setting_use_case(db: AsyncSession = Depends(get_db)) -> AlertSettingUseCase:
    return AlertSettingInteractor(settings=AlertSettingPgRepository(session=db))
