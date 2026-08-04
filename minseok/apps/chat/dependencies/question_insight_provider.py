from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from chat.adapter.outbound.gateways.question_insight_gateway import QuestionInsightGateway
from core.database import get_db
from hub.app.ports.output.question_insight_port import QuestionInsightPort


def get_question_insight_gateway(db: AsyncSession = Depends(get_db)) -> QuestionInsightPort:
    return QuestionInsightGateway(session=db)
