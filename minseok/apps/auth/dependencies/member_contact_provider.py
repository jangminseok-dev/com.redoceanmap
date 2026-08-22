from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.adapter.outbound.gateways.member_contact_gateway import MemberContactGateway
from core.database import get_db
from hub.app.ports.output.member_contact_port import MemberContactPort


def get_member_contact_gateway(db: AsyncSession = Depends(get_db)) -> MemberContactPort:
    """허브 MemberContactPort의 auth 구현. main.py가 주입한다."""
    return MemberContactGateway(session=db)
