import base64

from core.key.secret_manager import get_secret_manager

# `.env` 로드·조회는 전역 비밀값 관리자가 전담한다(core/key/secret_manager.py).
_secrets = get_secret_manager()

DATABASE_URL = _secrets.require("DATABASE_URL").replace(
    "postgresql://", "postgresql+psycopg://"
)

# market 전용 DB(market-pgvector, :5434) — 앱별 DB 불가침 원칙의 첫 사례.
# 미설정이면 메인 DB 폴백: 미구축 환경(맥 등)이 그대로 동작하고,
# 코드 배포와 데이터 컷오버(env 주입 + 재기동)를 분리할 수 있다.
# 폴백은 조용하면 안 된다 — 2026-07-24에 실운영 .env에서 이 키가 유실되며 컷오버가
# 무경고로 되돌아갔고, 사흘간 상권 뉴스가 메인 DB에 쌓였다. 기동 로그로 드러낸다.
_market_database_url = _secrets.get("MARKET_DATABASE_URL")
MARKET_DB_IS_FALLBACK = not _market_database_url
MARKET_DATABASE_URL = (_market_database_url or _secrets.require("DATABASE_URL")).replace(
    "postgresql://", "postgresql+psycopg://"
)

# JWT RS256 검증용 공개키 — 전 컨테이너 공용. 없으면 기동 실패가 맞다.
# (멀티라인 PEM은 env로 다루기 어려워 base64 단일 라인으로 주입한다 — scripts/generate_jwt_keys.sh)
JWT_PUBLIC_KEY = base64.b64decode(_secrets.require("JWT_PUBLIC_KEY_B64")).decode()


def jwt_private_key() -> str:
    """RS256 발급용 개인키 — auth 컨테이너 전용.

    반드시 호출 시점에 읽는다: backend 컨테이너는 이 env 없이도
    모듈 import·기동이 되어야 한다(발급 불가는 env 부재로 강제).
    `.env.auth`를 `load_auth_env()`로 명시 로드한 프로세스에서만 값이 잡힌다.
    """
    raw = _secrets.get("JWT_PRIVATE_KEY_B64")
    if not raw:
        raise RuntimeError("JWT_PRIVATE_KEY_B64 미설정 — 토큰 발급은 auth 컨테이너에서만 가능합니다.")
    return base64.b64decode(raw).decode()

# 실행 환경 — 쿠키 Secure 속성 분기(bff-cloudflared-harness 규칙 2)에만 사용.
ENV = _secrets.get("ENV", "development")

# 구조화 로깅(③-M4) — "json"이면 전 로그가 한 줄 JSON(운영 검색용), 기본 plain(로컬 가독성).
# prod compose가 environment로 json을 켠다.
LOG_FORMAT = _secrets.get("LOG_FORMAT", "plain")

# 기본 LLM 모델 태그(③-M5 교체 스위치) — 실소비처는 core/llm/llm_orchestrator.py
# (그쪽은 DATABASE_URL 없는 환경 지원을 위해 관리자를 직접 읽는다). 여기는 상수 등록 규칙 준수용.
LLM_MODEL = _secrets.get("LLM_MODEL", "exaone3.5:7.8b")

# 배포 식별 — Dockerfile ARG로 이미지에 굽는 값이다(.env 키가 아니다).
# 소스 마운트로 도는 dev나 --build-arg 없이 만든 이미지에서는 "unknown"이 맞다.
GIT_SHA = _secrets.get("GIT_SHA", "unknown")
BUILT_AT = _secrets.get("BUILT_AT", "unknown")

# BFF 쿠키 도메인 — prod `.redoceanmap.com`(auth 서브도메인 발급 쿠키를 apex와 공유),
# dev 미설정 = host-only. Secure·Domain만 ENV 분기, 나머지 속성은 리터럴(규칙 2).
COOKIE_DOMAIN = _secrets.get("COOKIE_DOMAIN")

# OAuth redirect_uri 조립 기준 — prod https://auth.redoceanmap.com/auth (이중문 직행),
# dev http://localhost:3000/api/backend/auth (프록시 경로 — 서브도메인 없음).
AUTH_CALLBACK_BASE = _secrets.get("AUTH_CALLBACK_BASE", "http://localhost:3000/api/backend/auth")

# API 문서(/docs·/redoc·/openapi.json) 보호 — HTTP Basic. 미설정 시 문서 접근 전면 차단.
DOCS_USER = _secrets.get("DOCS_USER")
DOCS_PASSWORD = _secrets.get("DOCS_PASSWORD")

# 리프레시 토큰 저장소 (auth) — 컨테이너는 redis://redis:6379/0 로 덮어쓴다.
REDIS_URL = _secrets.get("REDIS_URL", "redis://localhost:6379/0")

# 모바일 세션 전용 — 같은 Redis의 논리 db 1. 웹 세션(db 0)과 키 공간·커넥션을 분리한다.
REDIS_URL_MOBILE = _secrets.get("REDIS_URL_MOBILE", "redis://localhost:6379/1")

# n8n → 백엔드 인바운드 웹훅 검증 토큰. 비어 있으면 검증 생략(로컬 개발).
N8N_INBOUND_TOKEN = _secrets.get("N8N_INBOUND_TOKEN")

# 백엔드 → n8n 이메일 발송 웹훅 (Gmail 자격증명은 n8n이 보유).
N8N_EMAIL_WEBHOOK_URL = _secrets.get(
    "N8N_EMAIL_WEBHOOK_URL", "http://localhost:5678/webhook/redocean-email"
)
N8N_OUTBOUND_TOKEN = _secrets.get("N8N_OUTBOUND_TOKEN")

# 운영 알림 수신 주소 (scripts/check_freshness.py — 수집 지연·정지 통보).
# 비어 있으면 감시는 판정만 하고 발송에서 실패한다 — 조용히 넘어가지 않는다.
ALERT_EMAIL = _secrets.get("ALERT_EMAIL")

# vision 업로드 이미지를 저장할 S3 버킷 (자격 증명은 boto3 기본 체인 — .env의 AWS_* 키).
VISION_S3_BUCKET = _secrets.get("VISION_S3_BUCKET")
AWS_DEFAULT_REGION = _secrets.get("AWS_DEFAULT_REGION", "ap-northeast-2")

# 어드민 업로드 이미지를 저장할 S3 버킷 (admin image_upload 슬라이스).
# 비어 있으면 업로드 엔드포인트만 503 — 기동은 막지 않는다.
ADMIN_IMAGE_S3_BUCKET = _secrets.get("ADMIN_IMAGE_S3_BUCKET")

# 비전 / ConvNeXt 이미지 분류 (hub — 신뢰도 게이팅 임계값).
CONVNEXT_DEVICE = _secrets.get("CONVNEXT_DEVICE", "auto")  # "auto" | "cuda" | "cpu"
CONVNEXT_HIGH_CONFIDENCE = float(_secrets.get("CONVNEXT_HIGH_CONFIDENCE", "0.85"))  # 이상이면 자동 확정
CONVNEXT_LOW_CONFIDENCE = float(_secrets.get("CONVNEXT_LOW_CONFIDENCE", "0.55"))  # 미만이면 사람 확인
CONVNEXT_TOP_K = int(_secrets.get("CONVNEXT_TOP_K", "5"))

# Google Gemini API (허브 gemini 슬라이스 — 외부 LLM 답변). 비어 있으면 호출 시 계약 예외.
GEMINI_API_KEY = _secrets.get_gemini_api_key()
GEMINI_MODEL = _secrets.get_gemini_model_name()

# 소셜 로그인 OAuth (auth social 슬라이스). 비어 있으면 해당 프로바이더 로그인 시 401.
GOOGLE_CLIENT_ID = _secrets.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _secrets.get("GOOGLE_CLIENT_SECRET")
KAKAO_CLIENT_ID = _secrets.get("KAKAO_CLIENT_ID")  # 카카오 REST API 키
KAKAO_CLIENT_SECRET = _secrets.get("KAKAO_CLIENT_SECRET")  # 콘솔에서 선택 사항
# 카카오 앱 ID(숫자) — REST/네이티브 앱 키와 다른 값이다. 모바일 로그인에서 토큰의 앱 소유권 검증에 쓴다.
# 비어 있으면 모바일 카카오 로그인이 전부 거부된다(검증 불가 상태로 통과시키지 않는다).
KAKAO_APP_ID = _secrets.get("KAKAO_APP_ID")
NAVER_CLIENT_ID = _secrets.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = _secrets.get("NAVER_CLIENT_SECRET")
