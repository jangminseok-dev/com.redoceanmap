from __future__ import annotations

from game.app.ports.output.game_account_repository import GameAccountRepository
from game.app.ports.output.game_clock_port import GameClockPort
from game.app.ports.output.community_moderation_repository import (
    CommunityModerationRepositoryPort,
)
from game.app.ports.output.game_intervention_repository import GameInterventionRepository
from game.domain.clock.game_epoch import GAME_EPOCH_ID, RULES_VERSION, describe
from game.domain.market import market_events, price_engine
from game.domain.market import price_intervention as intervention_rules
from game.domain.community.nickname import display_name
from game.domain.market.symbol_params import SYMBOLS, find
from game.domain.trading.trading_rules import INITIAL_CASH_KRW
from hub.app.dtos.game_ops_dto import (
    CapitalGrantCommand,
    CapitalGrantReceipt,
    GameSymbolBrief,
    GameWalletSummary,
    HideContentCommand,
    PriceInterventionCommand,
    PriceInterventionRecord,
    ReportedContent,
)
from hub.app.ports.output.game_ops_port import GameOpsPort

LEDGER_SOURCE = "admin"  # 원장에서 운영 지급을 한눈에 가려내는 값


class GameOpsGateway(GameOpsPort):
    """허브의 `GameOpsPort`를 game(스포크)이 구현한다.

    admin은 game을 직접 import할 수 없으므로(스타 토폴로지) 이 파일이 유일한 접점이다.
    **게임 규칙은 여기서 끝난다** — 에포크·틱·이벤트 변환을 전부 여기서 처리하고 허브
    계약에는 사람이 읽는 값(퍼센트·원·게임일)만 내보낸다.
    """

    def __init__(
        self,
        accounts: GameAccountRepository,
        interventions: GameInterventionRepository,
        clock: GameClockPort,
        moderation: CommunityModerationRepositoryPort,
    ) -> None:
        self._accounts = accounts
        self._interventions = interventions
        self._clock = clock
        self._moderation = moderation

    # --- 지갑 -------------------------------------------------------------

    async def get_wallet(self, user_id: int) -> GameWalletSummary:
        account = await self._accounts.load(user_id, GAME_EPOCH_ID)
        if account is None:
            return GameWalletSummary(
                user_id=user_id,
                exists=False,
                cash_krw=0,
                epoch_id=GAME_EPOCH_ID,
                rule_version=RULES_VERSION,
                open_position_count=0,
                ledger_total_krw=0,
            )
        return GameWalletSummary(
            user_id=user_id,
            exists=True,
            cash_krw=account.cash_krw,
            epoch_id=account.epoch_id,
            rule_version=account.rule_version,
            open_position_count=len(account.open_positions),
            ledger_total_krw=await self._accounts.ledger_total(user_id, GAME_EPOCH_ID),
        )

    async def grant_capital(self, command: CapitalGrantCommand) -> CapitalGrantReceipt:
        if command.amount_krw == 0:
            raise ValueError("지급 금액이 0원입니다")
        moment = describe(self._clock.now_tick())

        account = await self._accounts.load(command.user_id, GAME_EPOCH_ID)
        if account is None:
            # 아직 게임을 시작하지 않은 유저 — 초기 자본으로 지갑을 먼저 연다.
            # 게임 화면의 자동 생성과 같은 경로라 원장에 `initial`이 그대로 남는다.
            account = await self._accounts.create(
                user_id=command.user_id,
                epoch_id=GAME_EPOCH_ID,
                rule_version=RULES_VERSION,
                initial_cash_krw=INITIAL_CASH_KRW,
                game_day=moment.game_day,
            )

        cash = await self._accounts.adjust_cash(
            user_id=command.user_id,
            epoch_id=GAME_EPOCH_ID,
            amount_krw=command.amount_krw,
            game_day=moment.game_day,
            source=LEDGER_SOURCE,
        )
        return CapitalGrantReceipt(
            user_id=command.user_id,
            amount_krw=command.amount_krw,
            cash_krw=cash,
            epoch_id=GAME_EPOCH_ID,
            game_day=moment.game_day,
        )

    # --- 주가 -------------------------------------------------------------

    async def list_symbols(self) -> tuple[GameSymbolBrief, ...]:
        tick = self._clock.now_tick()
        extra = await self._active_events(tick)
        return tuple(
            GameSymbolBrief(
                symbol=s.symbol,
                name=s.name,
                sector_group=s.sector_group,
                price_krw=price_engine.price_at(s, tick, None, extra),
                meme=s.meme,
            )
            for s in SYMBOLS
        )

    async def intervene_price(
        self, command: PriceInterventionCommand
    ) -> PriceInterventionRecord:
        tick = self._clock.now_tick()
        target_name = self._resolve_target_name(command.scope, command.target)

        shock_pct = command.shock_pct
        if command.target_price_krw is not None:
            if command.scope != intervention_rules.SCOPE_SYMBOL:
                raise ValueError("목표가 지정은 종목 개입에서만 쓸 수 있습니다")
            params = find(command.target)
            if params is None:
                raise ValueError(f"없는 종목입니다: {command.target}")
            extra = await self._active_events(tick)
            current = price_engine.price_at(params, tick, None, extra)
            shock_pct = intervention_rules.shock_pct_for_target_price(
                current, command.target_price_krw
            )

        intervention_rules.validate(
            shock_pct=shock_pct,
            drift_pct_per_day=command.drift_pct_per_day,
            duration_days=command.duration_days,
            scope=command.scope,
        )
        if not command.headline.strip():
            raise ValueError("유저에게 보일 문구가 비어 있습니다")

        saved = await self._interventions.create(
            epoch_id=GAME_EPOCH_ID,
            scope=command.scope,
            target=command.target,
            target_name=target_name,
            from_tick=tick,
            shock_pct=round(shock_pct, 4),
            drift_pct_per_day=command.drift_pct_per_day,
            duration_days=command.duration_days,
            headline=command.headline.strip(),
            note=command.note,
            created_by=command.created_by,
        )
        return self._to_record(saved, tick)

    async def list_interventions(self, limit: int = 50) -> tuple[PriceInterventionRecord, ...]:
        tick = self._clock.now_tick()
        rows = await self._interventions.list_recent(GAME_EPOCH_ID, limit)
        return tuple(self._to_record(r, tick) for r in rows)

    # --- 토론방 운영 -------------------------------------------------------

    async def list_reported_content(self, limit: int = 50) -> tuple[ReportedContent, ...]:
        rows = await self._moderation.list_reported(limit)
        return tuple(
            ReportedContent(
                target_type=r.target_type,
                target_id=r.target_id,
                symbol=r.symbol,
                # 실명이 아니라 가명을 싣는다 — 운영 화면이 필요로 하는 것은 신원이 아니라
                # "같은 사람이 반복하는가"다. 허브 계약에 개인정보를 넣지 않는다.
                author=display_name(r.author_user_id),
                body=r.body,
                report_count=r.report_count,
                reasons=r.reasons,
                reported_at=r.reported_at,
                hidden=r.hidden,
            )
            for r in rows
        )

    async def hide_content(self, command: HideContentCommand) -> None:
        if not await self._moderation.hide(
            command.target_type, command.target_id, command.reason
        ):
            raise ValueError("대상이 없거나 이미 내려간 글입니다")

    async def unhide_content(self, target_type: str, target_id: int) -> None:
        if not await self._moderation.unhide(target_type, target_id):
            raise ValueError("대상이 없거나 숨겨져 있지 않습니다")

    # --- 내부 -------------------------------------------------------------

    async def _active_events(self, tick: int) -> tuple[market_events.MarketEvent, ...]:
        rows = await self._interventions.list_in_window(
            GAME_EPOCH_ID, tick, market_events.EVENT_WINDOW_TICKS
        )
        return intervention_rules.to_events(rows)

    @staticmethod
    def _resolve_target_name(scope: str, target: str) -> str:
        if scope == intervention_rules.SCOPE_MARKET:
            return "시장 전체"
        if scope == intervention_rules.SCOPE_SECTOR:
            groups = {s.sector_group for s in SYMBOLS}
            if target not in groups:
                raise ValueError(f"없는 묶음 업종입니다: {target}")
            return target
        params = find(target)
        if params is None:
            raise ValueError(f"없는 종목입니다: {target}")
        return params.name

    @staticmethod
    def _to_record(saved, tick: int) -> PriceInterventionRecord:
        return PriceInterventionRecord(
            id=saved.id,
            epoch_id=saved.epoch_id,
            scope=saved.scope,
            target=saved.target,
            target_name=saved.target_name,
            from_tick=saved.from_tick,
            from_game_day=describe(saved.from_tick).game_day,
            shock_pct=saved.shock_pct,
            drift_pct_per_day=saved.drift_pct_per_day,
            duration_days=saved.duration_days,
            headline=saved.headline,
            note=saved.note,
            created_by=saved.created_by,
            in_effect=0 <= tick - saved.from_tick <= market_events.EVENT_WINDOW_TICKS,
        )
