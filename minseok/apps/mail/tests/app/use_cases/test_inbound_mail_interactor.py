from mail.app.use_cases.inbound_mail_interactor import InboundMailInteractor
from mail.domain.entities.inbound_mail import InboundMail


class _StubRepository:
    def __init__(self):
        self.mails: dict[str, InboundMail] = {}
        self.embeddings: dict[str, list[float] | None] = {}

    async def save(self, mail: InboundMail, embedding=None) -> bool:
        if mail.message_id in self.mails:
            return False
        self.mails[mail.message_id] = mail
        self.embeddings[mail.message_id] = embedding
        return True

    async def list_recent(self, limit: int = 50):
        return list(self.mails.values())[:limit]

    async def search_similar(self, embedding, limit: int = 5):
        return [m for k, m in self.mails.items() if self.embeddings.get(k) is not None][:limit]


class _StubEmbeddings:
    async def embed(self, text: str, *, kind: str = "query") -> list[float]:
        return [0.1] * 1024


class _FailingEmbeddings:
    async def embed(self, text: str, *, kind: str = "query") -> list[float]:
        raise RuntimeError("모델 없음")


def _mail(message_id: str) -> InboundMail:
    return InboundMail(
        message_id=message_id, subject="제목", sender="a@b.com", recipient="c@d.com", preview="본문",
    )


async def test_신규는_임베딩과_함께_저장되고_중복은_무시된다():
    repo = _StubRepository()
    interactor = InboundMailInteractor(repository=repo, embeddings=_StubEmbeddings())
    assert await interactor.receive(_mail("m-1")) is True
    assert await interactor.receive(_mail("m-1")) is False
    assert repo.embeddings["m-1"] is not None and len(repo.embeddings["m-1"]) == 1024
    assert len(await interactor.list_mails()) == 1


async def test_임베딩_실패해도_수신은_저장된다():
    repo = _StubRepository()
    interactor = InboundMailInteractor(repository=repo, embeddings=_FailingEmbeddings())
    assert await interactor.receive(_mail("m-2")) is True
    assert repo.embeddings["m-2"] is None


async def test_의미_검색은_질의를_임베딩해_유사_메일을_찾는다():
    repo = _StubRepository()
    interactor = InboundMailInteractor(repository=repo, embeddings=_StubEmbeddings())
    await interactor.receive(_mail("m-3"))
    results = await interactor.search_mails("상권 문의")
    assert [m.message_id for m in results] == ["m-3"]
