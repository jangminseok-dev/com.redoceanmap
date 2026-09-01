"""게임 운영 대장 검증 — 스텁 포트로만 돈다(mock 프레임워크 대신 스텁, 백엔드 컨벤션)."""
from datetime import datetime, timezone

import pytest

from admin.app.dtos.game_ops_dto import (
    GameWalletQuery,
    GrantCapitalCommand,
    HideContentCommand,
    InterveneCommand,
)
from admin.app.use_cases.game_ops_interactor import GameOpsInteractor
from hub.app.dtos.game_ops_dto import (
    CapitalGrantReceipt,
    GameSymbolBrief,
    GameWalletSummary,
    PriceInterventionRecord,
    ReportedContent,
)

USER = 7
ADMIN = 1


class _StubGame:
    """허브 `GameOpsPort` 스텁. 게임 규칙은 흉내만 내고 호출 인자를 기록한다."""

    def __init__(self, *, exists=True, cash=1_000_000, ledger=1_000_000):
        self.summary = GameWalletSummary(
            user_id=USER,
            exists=exists,
            cash_krw=cash,
            epoch_id=2,
            rule_version="v2",
            open_position_count=1,
            ledger_total_krw=ledger,
        )
        self.grants: list = []
        self.interventions: list = []
        self.reported: tuple = ()
        self.hidden: dict[int, str] = {}

    async def get_wallet(self, user_id):
        return self.summary

    async def grant_capital(self, command):
        self.grants.append(command)
        if self.summary.cash_krw + command.amount_krw < 0:
            raise ValueError("잔고가 음수가 됩니다")
        return CapitalGrantReceipt(
            user_id=command.user_id,
            amount_krw=command.amount_krw,
            cash_krw=self.summary.cash_krw + command.amount_krw,
            epoch_id=2,
            game_day=10,
        )

    async def list_symbols(self):
        return (
            GameSymbolBrief("GX01", "세빛반도체", "반도체·AI", 71_000, False),
            GameSymbolBrief("GX02", "온누리식품", "소비·유통", 41_200, False),
            GameSymbolBrief("GX33", "은하수게임샵", "밈·테마", 3_200, True),
        )

    async def intervene_price(self, command):
        self.interventions.append(command)
        return PriceInterventionRecord(
            id=1,
            epoch_id=2,
            scope=command.scope,
            target=command.target,
            target_name="세빛반도체",
            from_tick=600,
            from_game_day=10,
            shock_pct=command.shock_pct,
            drift_pct_per_day=command.drift_pct_per_day,
            duration_days=command.duration_days,
            headline=command.headline,
            note=command.note,
            created_by=command.created_by,
            in_effect=True,
        )

    async def list_interventions(self, limit=50):
        return ()

    # --- 토론방 신고 처리 ---

    async def list_reported_content(self, limit=50):
        return self.reported

    async def hide_content(self, command):
        if command.target_id in self.hidden:
            raise ValueError("이미 내려간 글입니다")
        self.hidden[command.target_id] = command.reason

    async def unhide_content(self, target_type, target_id):
        if target_id not in self.hidden:
            raise ValueError("숨겨져 있지 않습니다")
        del self.hidden[target_id]


class _StubMembers:
    async def find_email(self, user_id):
        return "player@example.com"


class _StubAudit:
    def __init__(self):
        self.entries: list[tuple[int, str, str]] = []

    async def write(self, actor_id: int, action: str, detail: str) -> None:
        self.entries.append((actor_id, action, detail))

    async def list_recent(self, limit: int):
        return []


def _build(**kwargs):
    game = _StubGame(**kwargs)
    return GameOpsInteractor(game=game, members=_StubMembers(), audit=_StubAudit()), game


# --- 지갑 -------------------------------------------------------------------

async def test_지갑에_회원_이메일을_붙여_보여준다():
    interactor, _ = _build()
    view = await interactor.get_wallet(GameWalletQuery(user_id=USER))
    assert view.email == "player@example.com"
    assert view.cash_krw == 1_000_000
    assert view.ledger_matches is True


async def test_원장과_잔고가_어긋나면_바로_드러난다():
    """지급이 지갑만 고치고 원장을 빠뜨리는 버그를 화면에서 잡는다."""
    interactor, _ = _build(cash=1_500_000, ledger=1_000_000)
    view = await interactor.get_wallet(GameWalletQuery(user_id=USER))
    assert view.ledger_matches is False


async def test_게임을_시작하지_않은_유저도_조회된다():
    interactor, _ = _build(exists=False, cash=0, ledger=0)
    view = await interactor.get_wallet(GameWalletQuery(user_id=USER))
    assert view.exists is False
    assert view.ledger_matches is True  # 지갑이 없는 상태는 불일치가 아니다


# --- 자본 지급 --------------------------------------------------------------

async def test_자본을_지급하면_잔고가_늘고_관리자가_기록된다():
    interactor, game = _build()
    result = await interactor.grant_capital(
        GrantCapitalCommand(user_id=USER, amount_krw=500_000, reason="보상", granted_by=ADMIN)
    )
    assert result.cash_krw == 1_500_000
    assert game.grants[0].granted_by == ADMIN
    assert game.grants[0].reason == "보상"


async def test_음수_지급으로_회수도_된다():
    interactor, _ = _build()
    result = await interactor.grant_capital(
        GrantCapitalCommand(user_id=USER, amount_krw=-300_000, reason="회수", granted_by=ADMIN)
    )
    assert result.cash_krw == 700_000


async def test_잔고를_음수로_만드는_회수는_거부한다():
    interactor, _ = _build()
    with pytest.raises(ValueError):
        await interactor.grant_capital(
            GrantCapitalCommand(
                user_id=USER, amount_krw=-2_000_000, reason="과다 회수", granted_by=ADMIN
            )
        )


# --- 주가 개입 --------------------------------------------------------------

async def test_개입_대상_목록에_묶음_업종이_유도된다():
    """업종 목록을 따로 관리하면 종목표와 갈라진다 — 종목에서 뽑는다."""
    interactor, _ = _build()
    board = await interactor.get_board()
    assert set(board.sector_groups) == {"반도체·AI", "소비·유통", "밈·테마"}
    assert len(board.symbols) == 3
    assert board.max_duration_days == 5


async def test_개입_지시가_그대로_game에_전달된다():
    interactor, game = _build()
    view = await interactor.intervene(
        InterveneCommand(
            scope="symbol",
            target="GX01",
            shock_pct=0.0,
            drift_pct_per_day=0.0,
            duration_days=2,
            headline="세빛반도체 신규 대형 수주 공시",
            note="이벤트 보상",
            created_by=ADMIN,
            target_price_krw=100_000,
        )
    )
    sent = game.interventions[0]
    assert sent.target_price_krw == 100_000  # 목표가 환산은 game이 한다(현재가를 아는 쪽)
    assert sent.created_by == ADMIN
    assert view.headline == "세빛반도체 신규 대형 수주 공시"
    assert view.in_effect is True


# --- 토론방 신고 처리 -------------------------------------------------------


async def test_신고_대기줄이_화면_DTO로_옮겨진다():
    interactor, game = _build()
    game.reported = (
        ReportedContent(
            target_type="post",
            target_id=11,
            symbol="GX01",
            author="느긋한 수달312",
            body="문제 글",
            report_count=3,
            reasons=("욕설", "욕설", "광고"),
            reported_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            hidden=False,
        ),
    )

    rows = await interactor.list_reported(50)

    assert len(rows) == 1
    assert rows[0].target_id == 11
    assert rows[0].report_count == 3
    # 사유 중복을 지우지 않는다 — 빈도가 곧 신호다
    assert rows[0].reasons == ("욕설", "욕설", "광고")
    # 실명이 아니라 게임이 만든 가명이 그대로 옮겨진다
    assert rows[0].author == "느긋한 수달312"


async def test_숨김_지시가_사유와_함께_game에_전달된다():
    interactor, game = _build()

    await interactor.hide_content(
        HideContentCommand(target_type="post", target_id=11, reason="욕설", hidden_by=1)
    )

    assert game.hidden[11] == "욕설"


@pytest.mark.parametrize("reason", ["", "   ", "\n"])
async def test_사유_없는_숨김은_거부한다(reason):
    """나중에 '왜 내렸나'를 답할 수 없게 된다."""
    interactor, game = _build()

    with pytest.raises(ValueError):
        await interactor.hide_content(
            HideContentCommand(target_type="post", target_id=11, reason=reason, hidden_by=1)
        )

    assert game.hidden == {}


async def test_숨김을_되돌릴_수_있다():
    interactor, game = _build()
    await interactor.hide_content(
        HideContentCommand(target_type="post", target_id=11, reason="욕설", hidden_by=1)
    )

    await interactor.unhide_content("post", 11, 1)

    assert game.hidden == {}


async def test_숨겨지지_않은_글의_해제는_거부된다():
    interactor, _ = _build()
    with pytest.raises(ValueError):
        await interactor.unhide_content("post", 999, 1)
