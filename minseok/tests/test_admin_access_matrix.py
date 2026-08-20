"""어드민 접근 매트릭스 회귀 그물 — /admin 라우트가 RBAC 가드를 제대로 달고 있는가.

`tests/test_permission_guard.py`는 가드 **함수 자체**(401/403/통과)를 검증하고,
`tests/test_public_routes.py`는 **인증** 경계를 고정한다. 그 사이에 빈 칸이 있었다:
**새 어드민 라우터가 `require_permission`을 빠뜨려도 아무도 모른다.** main.py가 admin
라우터를 `dependencies=_authenticated`로 마운트하므로 로그인만 하면(=`basic` 등급이어도)
어드민 데이터가 그대로 나간다. 401도 403도 아닌 200이라 조용하다.

여기서 고정하는 것 네 가지:
  1. 모든 /admin 라우트가 권한 가드를 갖는다(면제 목록 제외)
  2. 라우터가 쓰는 권한 코드가 마이그레이션이 시드한 코드 집합 안에 있다(오타 차단)
  3. 상태를 바꾸는 메서드(POST·PATCH·DELETE)는 :read가 아니라 :write를 요구한다
  4. 면제 경로도 최소한 인증은 요구한다

가드는 `require_permission(code)`가 만드는 클로저라 route에서 코드를 역추출한다.
"""
from fastapi.routing import APIRoute

import main
from core.security import get_current_user_id

# 마이그레이션이 시드한 권한 코드 — alembic/versions/f0a1b2c3d4e5(RBAC 테이블),
# a1b2c3d4e5f6(audit:read), c1d2e3f4a5b6(analytics:read), g1a2b3c4d5e6(game:read·write) 등.
# 여기 없는 코드를 라우터가 쓰면 어떤 역할도 보유할 수 없어 영구 403이 된다.
SEEDED_PERMISSIONS = {
    "analytics:read",
    "areas:read",
    "audit:read",
    "dashboard:read",
    "datasources:read",
    "documents:read",
    "documents:write",
    "game:read",
    "game:write",
    "members:read",
    "members:write",
    "recommendations:read",
}

# 관리자 권한 없이 열려도 되는 /admin 경로. 줄을 더하는 것은 보안 결정이다 — 이유를 함께 적을 것.
NO_PERMISSION_REQUIRED = {
    "/admin/myself",  # 라우터 컨벤션 자기소개 — 데이터를 반환하지 않는다
    "/admin/me",      # 본인의 권한 목록 조회 — user_id를 토큰에서 받아 남의 것은 못 본다
}

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _all_dependency_calls(route: APIRoute):
    """route에 걸린 모든 의존성 callable — dependencies=[...] 와 파라미터 기본값 Depends()를
    한꺼번에 본다(권한 가드는 두 형태로 다 쓰인다)."""
    found = []

    def walk(dependant):
        for sub in dependant.dependencies:
            if sub.call is not None:
                found.append(sub.call)
            walk(sub)

    walk(route.dependant)
    return found


def _permission_codes(route: APIRoute) -> set[str]:
    """route가 요구하는 권한 코드. require_permission의 클로저에서 code를 꺼낸다."""
    codes = set()
    for call in _all_dependency_calls(route):
        if getattr(call, "__qualname__", "").startswith("require_permission"):
            free = call.__code__.co_freevars
            if "code" in free and call.__closure__:
                codes.add(call.__closure__[free.index("code")].cell_contents)
    return codes


def _admin_routes() -> list[APIRoute]:
    return [
        r for r in main.app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/admin")
    ]


def test_어드민_라우트가_실제로_존재한다():
    # 매트릭스가 빈 목록을 돌며 조용히 통과하는 것을 막는다.
    assert len(_admin_routes()) >= 20


def test_모든_어드민_라우트가_권한_가드를_갖는다():
    unguarded = sorted(
        f"{sorted(r.methods - {'HEAD', 'OPTIONS'})[0]} {r.path}"
        for r in _admin_routes()
        if r.path not in NO_PERMISSION_REQUIRED and not _permission_codes(r)
    )
    assert unguarded == [], f"권한 가드 없는 어드민 라우트: {unguarded}"


def test_라우터가_쓰는_권한_코드가_시드에_존재한다():
    used = {code for r in _admin_routes() for code in _permission_codes(r)}
    assert used <= SEEDED_PERMISSIONS, f"시드에 없는 권한 코드(오타 의심): {used - SEEDED_PERMISSIONS}"


def test_상태를_바꾸는_라우트는_write_권한을_요구한다():
    # :read 가드를 복사해 붙인 POST/DELETE를 잡는다 — 조회 권한만으로 변경이 되면 안 된다.
    read_only_writes = sorted(
        f"{sorted(r.methods & WRITE_METHODS)[0]} {r.path} → {sorted(_permission_codes(r))}"
        for r in _admin_routes()
        if r.methods & WRITE_METHODS
        and r.path not in NO_PERMISSION_REQUIRED
        and not any(c.endswith(":write") for c in _permission_codes(r))
    )
    assert read_only_writes == [], f"write 권한 없이 변경하는 라우트: {read_only_writes}"


def test_권한_면제_경로도_인증은_요구한다():
    # 면제는 "권한 불요"지 "누구나"가 아니다.
    for route in _admin_routes():
        if route.path in NO_PERMISSION_REQUIRED:
            calls = _all_dependency_calls(route)
            assert get_current_user_id in calls, f"{route.path}가 인증 없이 열려 있다"
