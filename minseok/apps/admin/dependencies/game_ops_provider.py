from __future__ import annotations

from fastapi import Depends

from admin.app.ports.input.game_ops_use_case import GameOpsUseCase
from admin.app.use_cases.game_ops_interactor import GameOpsInteractor
from admin.app.ports.output.audit_log_port import AuditLogPort
from admin.dependencies.audit_provider import get_audit_log_port
from hub.app.ports.output.game_ops_port import GameOpsPort
from hub.app.ports.output.member_directory_port import MemberDirectoryPort
from hub.dependencies.game_ops_provider import get_game_ops_port
from hub.dependencies.member_directory_provider import get_member_directory_port


def get_game_ops_use_case(
    game: GameOpsPort = Depends(get_game_ops_port),
    members: MemberDirectoryPort = Depends(get_member_directory_port),
    audit: AuditLogPort = Depends(get_audit_log_port),
) -> GameOpsUseCase:
    return GameOpsInteractor(game=game, members=members, audit=audit)
