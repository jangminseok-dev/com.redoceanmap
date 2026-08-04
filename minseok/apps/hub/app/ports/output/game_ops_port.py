from __future__ import annotations

from abc import ABC, abstractmethod

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


class GameOpsPort(ABC):
    """게임 운영 추상 — admin(소비)과 game(구현)을 잇는다.

    두 기능을 한 포트에 두는 이유: 소비자가 하나(admin의 운영 화면)이고, 둘 다 "현재 에포크의
    게임 상태에 개입한다"는 같은 성질을 갖는다. 포트를 쪼개면 프로바이더·override·테스트 스텁이
    두 벌이 되는데 얻는 게 없다(소비자별 계약 분리 선례는 소비자가 **다를 때** 적용된다).
    """

    @abstractmethod
    async def get_wallet(self, user_id: int) -> GameWalletSummary:
        """유저 지갑 요약. 아직 게임을 시작하지 않았으면 `exists=False`."""
        ...

    @abstractmethod
    async def grant_capital(self, command: CapitalGrantCommand) -> CapitalGrantReceipt:
        """자본 지급·회수. 지갑이 없으면 초기 자본으로 먼저 만든다.

        원장에 한 줄이 함께 들어가므로 `SUM(ledger) == cash` 불변식이 유지된다.
        잔고가 음수가 되는 회수는 거부한다(`ValueError`).
        """
        ...

    @abstractmethod
    async def list_symbols(self) -> tuple[GameSymbolBrief, ...]:
        """개입 대상 선택지 — 전 종목의 현재가. 묶음 업종은 여기서 유도한다."""
        ...

    @abstractmethod
    async def intervene_price(
        self, command: PriceInterventionCommand
    ) -> PriceInterventionRecord:
        """주가 개입 생성. **지금부터 앞으로만** 효력이 있다 — 과거는 바뀌지 않는다.

        입력이 게임 규칙의 상한을 넘으면 `ValueError`.
        """
        ...

    @abstractmethod
    async def list_interventions(self, limit: int = 50) -> tuple[PriceInterventionRecord, ...]:
        """현재 에포크의 개입 이력(최신순)."""
        ...

    @abstractmethod
    async def list_reported_content(self, limit: int = 50) -> tuple[ReportedContent, ...]:
        """토론방 신고 대기줄(최근 신고순). 이미 내려간 것도 포함한다 — 되돌리려면 보여야 한다."""
        ...

    @abstractmethod
    async def hide_content(self, command: HideContentCommand) -> None:
        """신고된 글·댓글을 내린다. 대상이 없거나 이미 내려갔으면 `ValueError`.

        **작성자 본인 삭제와 다른 자리에 기록된다** — 누가 왜 내렸는지가 남아야 한다.
        """
        ...

    @abstractmethod
    async def unhide_content(self, target_type: str, target_id: int) -> None:
        """숨김 해제. 대상이 없거나 숨겨져 있지 않으면 `ValueError`.

        작성자가 스스로 지운 글은 되살리지 않는다 — 작성자 의사가 운영 판단보다 앞선다.
        """
        ...
