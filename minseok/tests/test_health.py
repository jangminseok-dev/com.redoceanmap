"""/health 회귀 그물 — 의존성이 죽으면 503으로 답하는가, 원인을 새지 않는가.

`/health`는 인증 없이 열린 유일한 상태 엔드포인트이고, 외부 업타임 모니터가 무는 지점이다.
200만 계속 답하면(예전 `{"status": "ok"}` 리터럴) 호스트가 살아 있는 한 DB가 죽어도
모니터는 정상으로 본다 — 2026-07-25~27 정지를 아무도 몰랐던 구조와 같다.

TestClient를 컨텍스트 매니저로 쓰지 않는다 — lifespan이 돌면 실제 DB에 붙는다.
"""
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def _stub_pings(monkeypatch, *, db: bool, market_db: bool, redis: bool) -> None:
    async def _database_ping() -> tuple[bool, bool]:
        return db, market_db

    async def _redis_ping() -> bool:
        return redis

    monkeypatch.setattr(main, "database_ping", _database_ping)
    monkeypatch.setattr(main, "redis_ping", _redis_ping)


def test_전부_살아있으면_200_ok(monkeypatch):
    _stub_pings(monkeypatch, db=True, market_db=True, redis=True)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["checks"] == {"database": True, "market_database": True, "redis": True}


def test_배포_커밋을_함께_답한다():
    # 상태만으로는 못 잡는 장애가 있다 — 2026-08-20에 12일 낡은 이미지가 돌며
    # /chat/ask/progress가 404였는데 /health는 계속 ok였다.
    # 밖에서 무는 모니터가 "떠 있는가"에 더해 "무엇이 떠 있는가"까지 보게 한다.
    version = client.get("/health").json()["version"]
    assert set(version) == {"commit", "builtAt"}


def test_공유_DB가_죽으면_503_degraded(monkeypatch):
    _stub_pings(monkeypatch, db=False, market_db=True, redis=True)
    res = client.get("/health")
    assert res.status_code == 503
    assert res.json()["status"] == "degraded"
    assert res.json()["checks"]["database"] is False


def test_market_DB만_죽어도_503(monkeypatch):
    # 상권 기능이 통째로 죽는 상태다 — 공유 DB가 살아 있다고 정상으로 보면 안 된다.
    _stub_pings(monkeypatch, db=True, market_db=False, redis=True)
    assert client.get("/health").status_code == 503


def test_redis만_죽어도_503(monkeypatch):
    _stub_pings(monkeypatch, db=True, market_db=True, redis=False)
    assert client.get("/health").status_code == 503


def test_실패_원인을_응답에_싣지_않는다(monkeypatch):
    # 인증 없이 열린 엔드포인트다 — 접속 문자열·예외 메시지가 나가면 안 된다.
    _stub_pings(monkeypatch, db=False, market_db=False, redis=False)
    body = res.text if (res := client.get("/health")) is not None else ""
    # version은 의도적으로 허용한다(커밋 sha·빌드 시각은 비밀이 아니다). 나머지 키가
    # 늘어나면 실패하게 두어, 원인 문자열이 섞여 들어오는 것을 계속 막는다.
    assert set(res.json()) == {"status", "checks", "version"}
    for leak in ("postgresql", "redis://", "localhost", "5432", "5434", "Traceback"):
        assert leak not in body


def test_health는_인증_없이_열려있다():
    # test_public_routes의 화이트리스트와 짝 — 가드가 붙으면 외부 모니터가 못 찌른다.
    route = next(r for r in main.app.routes if getattr(r, "path", None) == "/health")
    assert not route.dependencies
