"""공개/비공개 경계 회귀 그물 — 어떤 라우트가 인증 없이 열려 있는가.

`main.py`는 화이트리스트 방식이라 **`dependencies=_authenticated`를 빠뜨리면
그 라우터가 통째로 조용히 공개된다.** 테스트가 없으면 아무도 모른다.

`/market/areas/showcase`(비로그인 첫 화면)를 열면서 `/market/areas/ranking`
(lat/lng·폐업률 포함 1,650행)이 같이 새지 않는지를 여기서 고정한다.
"""
import main
from core.security import get_current_user_id, verify_docs_credentials

# 인증 없이 열려도 되는 경로. 여기에 줄을 더하는 것은 보안 결정이다 — 이유를 함께 적을 것.
PUBLIC_PATHS = {
    "/",        # /docs로 보내는 리다이렉트뿐 — 도착지가 HTTP Basic으로 막힌다
    "/health",  # 헬스체크
    # 비로그인 첫 화면 쇼케이스 — 읽기 전용, 서울시 공개 데이터, 최소 6필드
    "/market/areas/showcase",
}

# 이 프로젝트가 쓰는 인증 가드 전부. JWT(데이터 API)와 HTTP Basic(/docs·/openapi.json)이
# 서로 다른 함수라 하나만 보면 문서 라우트가 '열려 있다'고 오판한다.
AUTH_GUARDS = {get_current_user_id, verify_docs_credentials}


def _guarded(route) -> bool:
    # route.dependencies는 Depends 객체 목록이다 — 대상 함수는 `.dependency`에 있다
    # (`.call`은 Dependant 쪽 이름이라 여기서 쓰면 인증 라우트에서만 AttributeError가 난다).
    return any(d.dependency in AUTH_GUARDS for d in route.dependencies)


def _app_routes():
    return [r for r in main.app.routes if getattr(r, "dependencies", None) is not None]


def test_쇼케이스는_인증_없이_열린다():
    route = next(r for r in _app_routes() if r.path == "/market/areas/showcase")
    assert not _guarded(route)


def test_상권_디렉터리는_여전히_인증을_요구한다():
    # 쇼케이스와 같은 프로바이더를 쓰지만 페이로드가 전혀 다르다 — 함께 열리면 안 된다
    route = next(r for r in _app_routes() if r.path == "/market/areas/ranking")
    assert _guarded(route)


def test_market_조회_경로_중_공개는_쇼케이스뿐():
    opened = {
        r.path for r in _app_routes()
        if r.path.startswith("/market") and not _guarded(r)
    }
    assert opened == {"/market/areas/showcase"}


def test_화이트리스트_밖의_경로는_모두_인증을_요구한다():
    # /automation/*은 X-Webhook-Token을 자체 검증하므로 이 가드의 대상이 아니다
    leaked = sorted(
        r.path for r in _app_routes()
        if not _guarded(r)
        and r.path not in PUBLIC_PATHS
        and not r.path.startswith("/automation")
    )
    assert leaked == []


def test_myself_자기소개는_market에_하나뿐():
    # 조회 슬라이스 라우터가 전부 prefix="/market"이라 /myself를 또 만들면 중복 등록된다
    assert [r.path for r in _app_routes()].count("/market/myself") == 1
