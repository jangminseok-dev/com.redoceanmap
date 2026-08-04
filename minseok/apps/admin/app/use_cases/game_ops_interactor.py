from __future__ import annotations

from admin.app.dtos.game_ops_dto import (
    GameOpsBoard,
    GameWalletQuery,
    GameWalletView,
    GrantCapitalCommand,
    GrantCapitalResult,
    HideContentCommand,
    InterveneCommand,
    InterventionView,
    ReportedContentView,
    SymbolOption,
)
from admin.app.ports.input.game_ops_use_case import GameOpsUseCase
from hub.app.dtos.game_ops_dto import (
    CapitalGrantCommand,
    HideContentCommand as HubHideContentCommand,
    PriceInterventionCommand,
    PriceInterventionRecord,
)
from hub.app.ports.output.game_ops_port import GameOpsPort
from hub.app.ports.output.member_directory_port import MemberDirectoryPort

# 게임 규칙 상한 — game이 검증의 정본이고 여기서는 **화면에 보여줄 값**으로만 쓴다.
# 두 벌로 갈라지는 걸 막으려고 game이 거절하는 값을 그대로 옮겨 적지 않고,
# 허브 계약에 실려 오지 않는 값이라 화면 안내 문구용 상수로만 둔다(초과 입력은 game이 400).
MAX_SHOCK_PCT = 300.0
MAX_DRIFT_PCT_PER_DAY = 20.0
MAX_DURATION_DAYS = 5


class GameOpsInteractor(GameOpsUseCase):
    """게임 운영 대장 — 지갑 지급·주가 개입·토론방 신고 처리.

    게임 규칙은 하나도 모른다. 에포크·틱·이벤트 모델은 전부 game 쪽 게이트웨이가 갖고,
    여기서는 **누구에게 얼마** · **무엇을 몇 %** 를 옮기고 회원 정보를 붙일 뿐이다.
    """

    def __init__(self, game: GameOpsPort, members: MemberDirectoryPort) -> None:
        self._game = game
        self._members = members

    async def get_wallet(self, query: GameWalletQuery) -> GameWalletView:
        summary = await self._game.get_wallet(query.user_id)
        # 이메일만 붙인다 — 지급 대상을 눈으로 확인할 최소 정보이고, 회원 검색은
        # 이미 /admin/members가 한다(같은 조회를 두 곳에 두지 않는다)
        email = await self._members.find_email(query.user_id)
        return GameWalletView(
            user_id=summary.user_id,
            email=email or "",
            exists=summary.exists,
            cash_krw=summary.cash_krw,
            epoch_id=summary.epoch_id,
            rule_version=summary.rule_version,
            open_position_count=summary.open_position_count,
            ledger_total_krw=summary.ledger_total_krw,
            # 지급이 지갑만 고치고 원장을 빠뜨리면 여기서 즉시 드러난다
            ledger_matches=(not summary.exists) or summary.ledger_total_krw == summary.cash_krw,
        )

    async def grant_capital(self, command: GrantCapitalCommand) -> GrantCapitalResult:
        receipt = await self._game.grant_capital(
            CapitalGrantCommand(
                user_id=command.user_id,
                amount_krw=command.amount_krw,
                reason=command.reason,
                granted_by=command.granted_by,
            )
        )
        return GrantCapitalResult(
            user_id=receipt.user_id,
            amount_krw=receipt.amount_krw,
            cash_krw=receipt.cash_krw,
            game_day=receipt.game_day,
        )

    async def get_board(self) -> GameOpsBoard:
        symbols = await self._game.list_symbols()
        history = await self._game.list_interventions()
        return GameOpsBoard(
            symbols=tuple(
                SymbolOption(
                    symbol=s.symbol,
                    name=s.name,
                    sector_group=s.sector_group,
                    price_krw=s.price_krw,
                    meme=s.meme,
                )
                for s in symbols
            ),
            # 묶음 업종은 종목 목록에서 유도한다 — 두 곳에서 관리하면 갈라진다
            sector_groups=tuple(sorted({s.sector_group for s in symbols})),
            interventions=tuple(_to_view(r) for r in history),
            max_shock_pct=MAX_SHOCK_PCT,
            max_drift_pct_per_day=MAX_DRIFT_PCT_PER_DAY,
            max_duration_days=MAX_DURATION_DAYS,
        )

    async def intervene(self, command: InterveneCommand) -> InterventionView:
        record = await self._game.intervene_price(
            PriceInterventionCommand(
                scope=command.scope,
                target=command.target,
                shock_pct=command.shock_pct,
                drift_pct_per_day=command.drift_pct_per_day,
                duration_days=command.duration_days,
                headline=command.headline,
                note=command.note,
                created_by=command.created_by,
                target_price_krw=command.target_price_krw,
            )
        )
        return _to_view(record)


    # --- 토론방 신고 처리 -------------------------------------------------

    async def list_reported(self, limit: int = 50) -> tuple[ReportedContentView, ...]:
        rows = await self._game.list_reported_content(limit)
        return tuple(
            ReportedContentView(
                target_type=r.target_type,
                target_id=r.target_id,
                symbol=r.symbol,
                author=r.author,
                body=r.body,
                report_count=r.report_count,
                reasons=r.reasons,
                reported_at=r.reported_at,
                hidden=r.hidden,
            )
            for r in rows
        )

    async def hide_content(self, command: HideContentCommand) -> None:
        # 내리는 이유를 비워둘 수 없다 — 나중에 "왜 내렸나"를 답할 수 없게 된다
        reason = command.reason.strip()
        if not reason:
            raise ValueError("숨김 사유를 입력해주세요")
        await self._game.hide_content(
            HubHideContentCommand(
                target_type=command.target_type,
                target_id=command.target_id,
                reason=reason,
            )
        )

    async def unhide_content(self, target_type: str, target_id: int) -> None:
        await self._game.unhide_content(target_type, target_id)



def _to_view(record: PriceInterventionRecord) -> InterventionView:
    return InterventionView(
        id=record.id,
        scope=record.scope,
        target=record.target,
        target_name=record.target_name,
        from_game_day=record.from_game_day,
        shock_pct=record.shock_pct,
        drift_pct_per_day=record.drift_pct_per_day,
        duration_days=record.duration_days,
        headline=record.headline,
        note=record.note,
        in_effect=record.in_effect,
    )
