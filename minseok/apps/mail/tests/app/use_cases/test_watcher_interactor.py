from mail.app.dtos.watcher_dto import WatcherQuery
from mail.app.use_cases.watcher_interactor import WatcherInteractor
from mail.domain.entities.inbound_mail import InboundMail


class _StubRecord:
    def __init__(self):
        self.records = []

    async def record(self, subject, note):
        self.records.append((subject, note))


class _StubModeration:
    def __init__(self, scores):
        self._scores = scores

    async def moderate(self, text):
        return self._scores


class _StubMails:
    def __init__(self):
        self.received = []

    async def receive(self, mail):
        self.received.append(mail)
        return True

    async def list_mails(self, limit=50):
        return self.received

    async def search_mails(self, query, limit=5):
        return []


def _mail(message_id="m-1", subject="제목", preview="본문"):
    return InboundMail(
        message_id=message_id, subject=subject, sender="a@b.com",
        recipient="c@d.com", preview=preview,
    )


def _interactor(scores, record=None, mails=None):
    return WatcherInteractor(
        record=record or _StubRecord(),
        moderation=_StubModeration(scores),
        mails=mails or _StubMails(),
    )


async def test_자기소개는_배역_정보를_반환하고_관찰을_기록한다():
    record = _StubRecord()
    result = await _interactor({}, record=record).introduce_myself(
        WatcherQuery(id=10, name="수신 분류기 (mail/watcher)")
    )
    assert result.id == 10
    assert "트리아지" in result.introduction
    assert record.records[0][0] == "introduce_myself"


async def test_스크리닝은_정책을_적용하고_판정을_기록한다():
    record = _StubRecord()
    result = await _interactor({"악플/욕설": 0.93, "clean": 0.05}, record=record).screen("아무 텍스트")
    assert result.is_abusive is True
    assert result.categories == ("악플/욕설",)
    assert record.records[0][0] == "screen" and "유해" in record.records[0][1]


async def test_유해_메일은_차단되어_저장_파이프라인에_전달되지_않는다():
    record, mails = _StubRecord(), _StubMails()
    decision = await _interactor(
        {"악플/욕설": 0.9, "clean": 0.1}, record=record, mails=mails
    ).screen_and_receive(_mail(subject="야 이 미친놈아"))
    assert decision.blocked is True and decision.saved is False
    assert decision.categories == ("악플/욕설",)
    assert mails.received == []  # 저장 파이프라인 미호출
    assert record.records[0][0] == "blocked"


async def test_정상_메일은_기존_파이프라인으로_전달되어_저장된다():
    record, mails = _StubRecord(), _StubMails()
    decision = await _interactor(
        {"clean": 0.95, "악플/욕설": 0.02}, record=record, mails=mails
    ).screen_and_receive(_mail(subject="상권 분석 문의"))
    assert decision.blocked is False and decision.saved is True
    assert len(mails.received) == 1  # 임베딩→pgvector 경로로 전달됨
    assert record.records[0][0] == "passed"


async def test_검열_점수가_비면_저장하고_미검사_통과로_기록한다():
    # 2026-09-17: 모델 산출물이 없는 운영에서 메일 수신이 500으로 죽었다 — 어댑터가 빈 점수를 주면 저장은 하고 기록에 남긴다
    record, mails = _StubRecord(), _StubMails()
    decision = await _interactor({}, record=record, mails=mails).screen_and_receive(_mail())
    assert not decision.blocked and decision.saved and len(mails.received) == 1
    assert record.records[-1][1].startswith("미검사 통과(검열 모델 없음)(신규 저장)")
