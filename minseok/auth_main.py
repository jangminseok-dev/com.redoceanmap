"""인증 전용 엔트리포인트 (auth.redoceanmap.com) — main.py(비즈니스)와 같은 코드베이스, 별도 컨테이너.

개인키(JWT_PRIVATE_KEY_B64)를 가진 유일한 프로세스다 — 발급은 여기서만, 백엔드는 공개키 검증만.
"""
import os
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "apps"))

from core.key.secret_manager import get_secret_manager

# 발급용 개인키 — 로컬 실행용. 컨테이너는 env_file(.env.auth) 주입이라 파일이 없어도 된다.
# `.env.auth`를 로드하는 유일한 엔트리포인트다(백엔드 프로세스는 개인키를 갖지 않는다).
get_secret_manager().load_auth_env()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from auth.adapter.inbound.api.v1.auth_router import auth_router
from auth.adapter.inbound.api.v1.gatekeeper_router import gatekeeper_router
from auth.adapter.inbound.api.v1.mobile_auth_router import mobile_auth_router
from auth.adapter.inbound.api.v1.mobile_gatekeeper_router import mobile_gatekeeper_router
from auth.adapter.inbound.api.v1.social_router import social_router
from core.config import LOG_FORMAT
from core.database import dispose_engine, init_engine
from core.logging_setup import setup_logging
from core.redis import dispose_redis

# 구조화 로깅(③-M4) — 백엔드(main.py)와 같은 스위치. 액세스 미들웨어는 트래픽이 적어
# 백엔드에만 둔다(여기는 포맷 통일까지).
setup_logging(LOG_FORMAT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    try:
        yield
    finally:
        await dispose_engine()
        await dispose_redis()


# 실서비스 노출 — 문서 라우트는 열지 않는다(main.py와 달리 재개방도 없음).
app = FastAPI(
    title="redoceanmap Auth",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    # 이중문(B.0): prod 프론트(apex)가 auth 오리진으로 직행 호출(credentials: include) —
    # 쿠키 동행을 위해 allow_credentials 필수. dev(localhost)는 프록시 경로라 same-origin.
    allow_origins=[
        "https://redoceanmap.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)  # 공개 — register/login/refresh, me·tabs는 자체 검증
app.include_router(social_router)  # 공개 — 소셜 로그인(google·kakao·naver), 코드 교환 후 자체 JWT 발급
app.include_router(gatekeeper_router)  # 공개 — auth 자기소개
app.include_router(mobile_auth_router)  # 공개 — Flutter 앱 카카오 로그인(본문으로 토큰 발급)
app.include_router(mobile_gatekeeper_router)  # 공개 — auth/mobile 자기소개


@app.get("/", include_in_schema=False)
def read_root():
    # 루트 직접 접속(브라우저) 안내 — 날 404 대신 자기소개로 넘긴다 (main.py의 /→/docs와 동일 취지)
    return RedirectResponse("/auth/myself")


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("auth_main:app", host="127.0.0.1", port=9000, reload=True)
