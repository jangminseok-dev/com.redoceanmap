from __future__ import annotations

import logging

from mail.app.dtos.watcher_dto import (
    WatcherMailDecision,
    WatcherQuery,
    WatcherResponse,
    WatcherScreenResult,
)
from mail.app.ports.input.inbound_mail_use_case import InboundMailUseCase
from mail.app.ports.input.watcher_use_case import WatcherUseCase
from mail.app.ports.output.moderation_port import ModerationPort
from mail.app.ports.output.watcher_record_port import WatcherRecordPort
from mail.domain.entities.inbound_mail import InboundMail
from mail.domain.services import moderation_policy

logger = logging.getLogger(__name__)


class WatcherInteractor(WatcherUseCase):
    """왓처(Watcher) 대장 — 수신 메일 1차 분류(트리아지) 관문.

    v1: KcELECTRA+Unsmile 분류기(ModerationPort)의 점수에 도메인 정책
    (moderation_policy.judge)을 적용해 유해 메일은 차단하고, 정상 메일만
    기존 파이프라인(InboundMailUseCase → 임베딩 → pgvector)으로 전달한다.
    향후: 중요/보고서 요청은 허브 경유 오케스트레이터 격상(Case B).
    """

    def __init__(
        self,
        record: WatcherRecordPort,
        moderation: ModerationPort,
        mails: InboundMailUseCase,
    ) -> None:
        self._record = record
        self._moderation = moderation
        self._mails = mails

    async def introduce_myself(self, query: WatcherQuery) -> WatcherResponse:
        await self._record.record(subject="introduce_myself", note=f"{query.name} 자기소개 관찰")
        return WatcherResponse(
            id=query.id,
            name=query.name,
            introduction=(
                "수신 메일 1차 분류(트리아지) 담당입니다. KcELECTRA+Unsmile v1 분류기로 "
                "욕설·혐오 등 유해 한국어를 정책 기반(카테고리 9종, 임계값 0.5)으로 판정합니다 "
                "(POST /watcher/screen). 모든 관찰은 기록 포트로 남깁니다."
            ),
        )

    async def screen(self, text: str) -> WatcherScreenResult:
        scores = await self._moderation.moderate(text)
        verdict = moderation_policy.judge(scores)
        await self._record.record(
            subject="screen",
            note=f"{'유해' if verdict.is_abusive else '정상'} {list(verdict.categories)} | {text[:40]}",
        )
        return WatcherScreenResult(
            is_abusive=verdict.is_abusive,
            categories=verdict.categories,
            scores=scores,
        )

    async def screen_and_receive(self, mail: InboundMail) -> WatcherMailDecision:
        """수신 관문: 제목+본문을 필터링해 유해면 차단, 정상만 저장 파이프라인으로."""
        scores = await self._moderation.moderate(f"{mail.subject}\n{mail.preview}")
        verdict = moderation_policy.judge(scores)

        if verdict.is_abusive:
            await self._record.record(
                subject="blocked",
                note=f"유해 메일 차단 {list(verdict.categories)} | {mail.message_id} | {mail.subject[:40]}",
            )
            return WatcherMailDecision(blocked=True, saved=False, categories=verdict.categories)

        saved = await self._mails.receive(mail)  # 기존 파이프라인: 임베딩 → pgvector
        # 점수가 비면 검열 모델이 없어 검사하지 않은 것 — "정상"으로 기록하면 검열이 된 줄 안다
        passed = "정상 통과" if scores else "미검사 통과(검열 모델 없음)"
        await self._record.record(
            subject="passed",
            note=f"{passed}({'신규 저장' if saved else '중복'}) | {mail.message_id} | {mail.subject[:40]}",
        )
        return WatcherMailDecision(blocked=False, saved=saved, categories=())