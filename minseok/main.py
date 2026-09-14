import logging
import os
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "apps"))

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import RedirectResponse

from admin.adapter.inbound.api.v1.analytics_router import analytics_router as admin_analytics_router
from admin.adapter.inbound.api.v1.area_router import area_router as admin_area_router
from admin.adapter.inbound.api.v1.audit_router import audit_router
from admin.adapter.inbound.api.v1.dashboard_router import dashboard_router as admin_dashboard_router
from admin.adapter.inbound.api.v1.data_source_router import data_source_router as admin_data_source_router
from admin.adapter.inbound.api.v1.grade_router import grade_router as admin_grade_router
from admin.adapter.inbound.api.v1.member_router import member_router as admin_member_router
from admin.adapter.inbound.api.v1.pdf_loader_router import (
    pdf_loader_router as admin_pdf_loader_router,
)
from admin.adapter.inbound.api.v1.recommendation_log_router import (
    recommendation_log_router as admin_recommendation_log_router,
)
from admin.adapter.inbound.api.v1.s3_image_upload_router import (
    s3_image_upload_router as admin_s3_image_upload_router,
)
from admin.adapter.inbound.api.v1.question_insight_router import (
    question_insight_router as admin_question_insight_router,
)
from admin.adapter.inbound.api.v1.steward_router import steward_router
from auth.dependencies.grade_policy_provider import get_grade_policy_gateway
from auth.dependencies.member_contact_provider import get_member_contact_gateway
from auth.dependencies.member_directory_provider import get_member_directory_gateway
from chat.adapter.inbound.api.v1.chat_router import chat_router
from chat.adapter.inbound.api.v1.concierge_router import concierge_router
from core.config import BUILT_AT, GIT_SHA, LOG_FORMAT
from core.logging_setup import setup_logging
from core.database import dispose_engine, dispose_market_engine, init_engine, init_market_engine
from core.database import ping as database_ping
from core.redis import dispose_redis
from core.redis import ping as redis_ping
from core.security import get_current_user_id, verify_docs_credentials
from chat.adapter.outbound.gateways.email_composer_gateway import EmailComposerN8nGateway
from hub.adapter.inbound.api.v1.dispatcher_router import dispatcher_router
from hub.adapter.inbound.api.v1.email_request_router import email_request_router
from hub.adapter.inbound.api.v1.face_recognition_router import face_recognition_router
from hub.adapter.inbound.api.v1.forecast_refit_router import forecast_refit_router
from hub.adapter.inbound.api.v1.forecast_snapshot_router import forecast_snapshot_router
from hub.adapter.inbound.api.v1.paper_trading_router import paper_trading_router
from hub.adapter.inbound.api.v1.fundamental_ingest_router import fundamental_ingest_router
from hub.adapter.inbound.api.v1.gemini_router import gemini_router
from hub.adapter.inbound.api.v1.image_classifier_router import image_classifier_router
from hub.adapter.inbound.api.v1.langchain_semantic_router import langchain_semantic_router
from hub.adapter.inbound.api.v1.semantic_router import semantic_router
from hub.adapter.inbound.api.v1.mail_ingest_router import mail_ingest_router
from hub.adapter.inbound.api.v1.market_news_ingest_router import market_news_ingest_router
from hub.adapter.inbound.api.v1.franchise_cost_ingest_router import franchise_cost_ingest_router
from hub.adapter.inbound.api.v1.news_ingest_router import news_ingest_router
from hub.adapter.inbound.api.v1.news_label_ingest_router import news_label_ingest_router
from hub.adapter.inbound.api.v1.postmaster_router import postmaster_router
from hub.adapter.inbound.api.v1.price_bar_ingest_router import price_bar_ingest_router
from hub.adapter.inbound.api.v1.bookmark_alert_router import bookmark_alert_router
from hub.adapter.inbound.api.v1.price_alert_scan_router import price_alert_scan_router
from hub.adapter.inbound.api.v1.news_alert_scan_router import news_alert_scan_router
from hub.adapter.inbound.api.v1.signal_scan_router import signal_scan_router
from hub.adapter.inbound.api.v1.stock_demand_router import stock_demand_router
from hub.dependencies.area_backtest_report_provider import get_area_backtest_report_port
from hub.dependencies.forecast_refit_provider import get_forecast_refit_port
from hub.dependencies.forecast_snapshot_provider import get_forecast_snapshot_port
from hub.dependencies.paper_trading_provider import get_paper_decision_port, get_paper_trading_port
from hub.dependencies.fundamental_ingest_provider import get_fundamental_storage_port
from hub.dependencies.mail_ingest_provider import get_mail_storage_port
from hub.dependencies.market_news_ingest_provider import get_market_news_storage_port
from hub.dependencies.franchise_cost_provider import get_franchise_cost_storage_port
from hub.dependencies.market_news_search_provider import get_market_news_search_port
from hub.dependencies.news_ingest_provider import get_news_storage_port
from hub.dependencies.news_label_ingest_provider import get_news_label_storage_port
from hub.dependencies.price_bar_ingest_provider import get_price_bar_storage_port
from hub.dependencies.email_request_provider import get_email_composer
from hub.dependencies.price_alert_directory_provider import get_price_alert_directory_port
from hub.dependencies.news_alert_feed_provider import get_news_alert_feed_port
from mail.adapter.inbound.api.v1.judge_router import judge_router
from mail.adapter.inbound.api.v1.inbound_mail_router import inbound_mail_router
from mail.adapter.inbound.api.v1.postman_router import postman_router
from mail.adapter.inbound.api.v1.watcher_router import watcher_router
from mail.dependencies.watcher_provider import get_mail_storage_gateway
from hub.dependencies.commercial_data_provider import get_commercial_data_port
from hub.dependencies.grade_policy_provider import get_grade_policy_port
from hub.dependencies.question_insight_provider import get_question_insight_port
from hub.dependencies.member_directory_provider import get_member_directory_port
from hub.dependencies.news_search_provider import get_news_search_port
from hub.dependencies.recommendation_directory_provider import get_recommendation_directory_port
from hub.dependencies.recommendation_record_provider import get_recommendation_record_port
from hub.dependencies.user_profile_provider import get_user_profile_port
from hub.dependencies.alert_delivery_provider import get_alert_delivery_port
from hub.dependencies.bookmark_directory_provider import get_bookmark_directory_port
from hub.dependencies.member_contact_provider import get_member_contact_port
from hub.dependencies.stock_analysis_provider import (
    get_stock_analysis_port,
    get_stock_analysis_port_batch,
)
from hub.dependencies.stock_forecast_provider import get_stock_forecast_port
from hub.dependencies.stock_status_provider import get_stock_status_port
from hub.dependencies.stock_signal_board_provider import get_stock_signal_board_port
from hub.dependencies.fundamental_read_provider import get_fundamental_read_port
from hub.dependencies.stock_demand_provider import get_stock_demand_port
from hub.dependencies.stock_dataset_stats_provider import get_stock_dataset_stats_port
from hub.dependencies.news_event_study_provider import get_news_event_study_port
from market.dependencies.area_backtest_report_provider import get_area_backtest_report_gateway
from market.dependencies.commercial_data_provider import get_commercial_data_gateway
from market.dependencies.market_news_provider import (
    get_franchise_cost_storage_gateway,
    get_market_news_search_gateway,
    get_market_news_storage_gateway,
)
from market.adapter.inbound.api.v1.area_detail_router import area_detail_router
from market.adapter.inbound.api.v1.area_router import area_router
from market.adapter.inbound.api.v1.area_ranking_router import area_ranking_router
from market.adapter.inbound.api.v1.area_score_router import area_score_router
from market.adapter.inbound.api.v1.area_fitness_router import (
    area_fitness_router as market_area_fitness_router,
)
from market.adapter.inbound.api.v1.area_public_router import area_public_router
from market.adapter.inbound.api.v1.area_showcase_router import area_showcase_router
from market.adapter.inbound.api.v1.area_stats_router import area_stats_router
from market.adapter.inbound.api.v1.cartographer_router import cartographer_router
from chat.dependencies.question_insight_provider import get_question_insight_gateway
from stock.adapter.inbound.api.v1.analyst_router import analyst_router
from stock.adapter.inbound.api.v1.stock_board_router import stock_board_router
from stock.adapter.inbound.api.v1.paper_router import paper_router
from stock.adapter.inbound.api.v1.stock_forecast_router import stock_forecast_router
from stock.adapter.inbound.api.v1.stock_history_router import stock_history_router
from stock.adapter.inbound.api.v1.stock_quote_router import stock_quote_router
from stock.adapter.inbound.api.v1.stock_router import stock_router
from stock.dependencies.forecast_refit_provider import get_forecast_refit_gateway
from stock.dependencies.forecast_snapshot_provider import get_forecast_snapshot_gateway
from stock.dependencies.paper_provider import get_paper_decision_gateway, get_paper_trading_gateway
from stock.dependencies.fundamental_provider import get_fundamental_storage_gateway
from stock.dependencies.news_label_provider import get_news_label_storage_gateway
from stock.dependencies.news_provider import get_news_search_gateway, get_news_storage_gateway
from stock.dependencies.price_bar_provider import get_price_bar_storage_gateway
from stock.dependencies.stock_demand_provider import get_stock_demand_gateway
from stock.dependencies.stock_dataset_stats_provider import get_stock_dataset_stats_gateway
from stock.dependencies.news_alert_feed_provider import get_news_alert_feed_gateway
from stock.dependencies.news_event_study_provider import get_news_event_study_gateway
from stock.dependencies.stock_forecast_provider import get_stock_forecast_gateway
from stock.dependencies.stock_status_provider import get_stock_status_gateway
from stock.dependencies.stock_signal_board_provider import get_stock_signal_board_gateway
from stock.dependencies.stock_history_provider import get_fundamental_read_gateway
from stock.dependencies.stock_provider import (
    get_stock_analysis_gateway,
    get_stock_analysis_gateway_batch,
)
from recommendation.adapter.inbound.api.v1.alert_setting_router import alert_setting_router
from recommendation.adapter.inbound.api.v1.price_alert_router import price_alert_router
from recommendation.adapter.inbound.api.v1.bookmark_board_router import bookmark_board_router
from recommendation.adapter.inbound.api.v1.bookmark_router import bookmark_router
from recommendation.adapter.inbound.api.v1.curator_router import curator_router
from recommendation.adapter.inbound.api.v1.profile_router import profile_router
from recommendation.adapter.inbound.api.v1.recommendation_router import recommendation_router
from recommendation.dependencies.bookmark_provider import (
    get_alert_delivery_gateway,
    get_bookmark_directory_gateway,
)
from recommendation.dependencies.price_alert_provider import get_price_alert_directory_gateway
from recommendation.dependencies.profile_provider import get_user_profile_gateway
from recommendation.dependencies.recommendation_provider import (
    get_recommendation_directory_gateway,
    get_recommendation_record_gateway,
)
from hub.adapter.inbound.api.v1.vision_router import vision_router

# 구조화 로깅(③-M4) — LOG_FORMAT=json이면 전 로그가 한 줄 JSON(운영 검색용)
setup_logging(LOG_FORMAT)

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    init_market_engine()  # market 전용 DB(:5434) — 미설정 시 메인 폴백
    try:
        yield
    finally:
        await dispose_engine()
        await dispose_market_engine()
        await dispose_redis()


# 문서 기본 라우트는 끄고 아래에서 HTTP Basic 가드를 걸어 다시 연다.
app = FastAPI(
    title="redoceanmap API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if LOG_FORMAT == "json":
    # 요청 단위 구조화 액세스 로그(③-M4) — uvicorn access는 setup_logging이 껐다
    # (여기가 method·path·status에 duration까지 실어 상위호환). 쿼리스트링은 싣지 않는다
    # (검색어 등 사용자 입력 최소화). /health는 업타임 모니터가 분 단위로 두드려 제외.
    import time as _time

    _access_logger = logging.getLogger("access")

    @app.middleware("http")
    async def access_log(request, call_next):
        start = _time.perf_counter()
        response = await call_next(request)
        if request.url.path != "/health":
            _access_logger.info(
                "%s %s %d", request.method, request.url.path, response.status_code,
                extra={"http": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((_time.perf_counter() - start) * 1000, 1),
                }},
            )
        return response

# 인증 가드 — 공개 화이트리스트 방식: automation(웹훅 토큰)·/·/health만 공개,
# 나머지 라우터는 전부 JWT 필수(core/security — 스포크는 auth를 모른다).
# /auth/* 라우터는 auth_main.py(인증 전용 컨테이너)로 분리 — 발급은 개인키를 가진 그쪽에서만.
_authenticated = [Depends(get_current_user_id)]

# 공개 — 외부 자동화 창구(/automation/*), X-Webhook-Token 자체 검증 (dispatcher는 자기소개라 토큰 없음)
app.include_router(news_ingest_router)
app.include_router(market_news_ingest_router)
app.include_router(franchise_cost_ingest_router)
app.include_router(price_bar_ingest_router)
app.include_router(stock_demand_router)
app.include_router(news_label_ingest_router)
app.include_router(fundamental_ingest_router)
app.include_router(forecast_snapshot_router)
app.include_router(paper_trading_router)
app.include_router(forecast_refit_router)
app.include_router(mail_ingest_router)
app.include_router(signal_scan_router)
app.include_router(bookmark_alert_router)  # 허브 — 관심 종목 알림 스캔(웹훅 토큰, ③-M3)
app.include_router(price_alert_scan_router)  # 허브 — 가격 도달 알림 스캔(웹훅 토큰, [6])
app.include_router(news_alert_scan_router)  # 허브 — 티커 뉴스 알림 스캔(웹훅 토큰, B9)
app.include_router(dispatcher_router)
# 공개 — 비로그인 첫 화면 쇼케이스(읽기 전용·최소 필드). 데이터 라우터 중 유일하게
# 인증 없이 열린다. 여기에 라우터를 더 얹기 전에 tests/test_public_routes.py를 볼 것.
app.include_router(area_showcase_router)
# 공개 — 상권 1곳 공개 페이지(A-4, 2026-09-14) + sitemap 인덱스. 인증 대신 IP rate limit,
# 뷰 필드는 AreaPublicView가 명시적으로 절제한다(좌표·인허가 상호·인구 피라미드 없음).
app.include_router(area_public_router)
app.include_router(chat_router, dependencies=_authenticated)
app.include_router(concierge_router, dependencies=_authenticated)
app.include_router(area_detail_router, dependencies=_authenticated)
app.include_router(area_router, dependencies=_authenticated)
app.include_router(area_score_router, dependencies=_authenticated)
app.include_router(market_area_fitness_router, dependencies=_authenticated)
app.include_router(area_ranking_router, dependencies=_authenticated)
app.include_router(area_stats_router, dependencies=_authenticated)
app.include_router(cartographer_router, dependencies=_authenticated)
app.include_router(stock_router, dependencies=_authenticated)
app.include_router(stock_history_router, dependencies=_authenticated)
app.include_router(stock_forecast_router, dependencies=_authenticated)
app.include_router(stock_quote_router, dependencies=_authenticated)
app.include_router(stock_board_router, dependencies=_authenticated)
app.include_router(paper_router, dependencies=_authenticated)
app.include_router(analyst_router, dependencies=_authenticated)
app.include_router(recommendation_router, dependencies=_authenticated)
app.include_router(bookmark_router, dependencies=_authenticated)
app.include_router(bookmark_board_router, dependencies=_authenticated)
app.include_router(alert_setting_router, dependencies=_authenticated)
app.include_router(price_alert_router, dependencies=_authenticated)
app.include_router(profile_router, dependencies=_authenticated)
app.include_router(curator_router, dependencies=_authenticated)
app.include_router(email_request_router, dependencies=_authenticated)  # 허브 — 이메일 발송 요청
app.include_router(postmaster_router, dependencies=_authenticated)
app.include_router(inbound_mail_router, dependencies=_authenticated)
app.include_router(postman_router, dependencies=_authenticated)
app.include_router(watcher_router, dependencies=_authenticated)
app.include_router(judge_router, dependencies=_authenticated)
app.include_router(vision_router, dependencies=_authenticated)
app.include_router(face_recognition_router, dependencies=_authenticated)
app.include_router(image_classifier_router, dependencies=_authenticated)
# 어드민 콘솔 — 인증은 전 엔드포인트 공통(안전망), 권한(RBAC)은 엔드포인트 단 require_permission
app.include_router(steward_router, dependencies=_authenticated)
app.include_router(admin_dashboard_router, dependencies=_authenticated)
app.include_router(admin_area_router, dependencies=_authenticated)
app.include_router(admin_member_router, dependencies=_authenticated)
app.include_router(admin_grade_router, dependencies=_authenticated)
app.include_router(admin_recommendation_log_router, dependencies=_authenticated)
app.include_router(admin_data_source_router, dependencies=_authenticated)
app.include_router(admin_analytics_router, dependencies=_authenticated)
app.include_router(admin_pdf_loader_router, dependencies=_authenticated)
app.include_router(admin_s3_image_upload_router, dependencies=_authenticated)
app.include_router(admin_question_insight_router, dependencies=_authenticated)
app.include_router(audit_router, dependencies=_authenticated)
app.include_router(gemini_router, dependencies=_authenticated)  # 허브 — 외부 Gemini 답변
app.include_router(semantic_router, dependencies=_authenticated)  # 허브 — 시멘틱 게이트웨이(PoC)
app.include_router(langchain_semantic_router, dependencies=_authenticated)  # 허브 — 랭체인 게이트웨이(ROM 2.0)

# 합성 루트: 허브(hub)의 포트들을 스포크 구현으로 주입한다.
# (허브는 스포크를 모르고, main.py만 둘을 안다 — 스타 토폴로지 허브 격리 유지)
app.dependency_overrides[get_commercial_data_port] = get_commercial_data_gateway
app.dependency_overrides[get_recommendation_record_port] = get_recommendation_record_gateway
app.dependency_overrides[get_stock_analysis_port] = get_stock_analysis_gateway
app.dependency_overrides[get_stock_analysis_port_batch] = get_stock_analysis_gateway_batch
app.dependency_overrides[get_stock_forecast_port] = get_stock_forecast_gateway
app.dependency_overrides[get_stock_status_port] = get_stock_status_gateway
app.dependency_overrides[get_stock_signal_board_port] = get_stock_signal_board_gateway
app.dependency_overrides[get_fundamental_read_port] = get_fundamental_read_gateway
app.dependency_overrides[get_news_storage_port] = get_news_storage_gateway
app.dependency_overrides[get_price_bar_storage_port] = get_price_bar_storage_gateway
app.dependency_overrides[get_news_label_storage_port] = get_news_label_storage_gateway
app.dependency_overrides[get_fundamental_storage_port] = get_fundamental_storage_gateway
app.dependency_overrides[get_news_search_port] = get_news_search_gateway
app.dependency_overrides[get_market_news_storage_port] = get_market_news_storage_gateway
app.dependency_overrides[get_franchise_cost_storage_port] = get_franchise_cost_storage_gateway
app.dependency_overrides[get_market_news_search_port] = get_market_news_search_gateway
app.dependency_overrides[get_email_composer] = lambda: EmailComposerN8nGateway()
app.dependency_overrides[get_member_directory_port] = get_member_directory_gateway
app.dependency_overrides[get_grade_policy_port] = get_grade_policy_gateway
app.dependency_overrides[get_recommendation_directory_port] = get_recommendation_directory_gateway
app.dependency_overrides[get_user_profile_port] = get_user_profile_gateway
app.dependency_overrides[get_bookmark_directory_port] = get_bookmark_directory_gateway
app.dependency_overrides[get_member_contact_port] = get_member_contact_gateway
app.dependency_overrides[get_alert_delivery_port] = get_alert_delivery_gateway
app.dependency_overrides[get_price_alert_directory_port] = get_price_alert_directory_gateway
app.dependency_overrides[get_news_alert_feed_port] = get_news_alert_feed_gateway
app.dependency_overrides[get_mail_storage_port] = get_mail_storage_gateway
app.dependency_overrides[get_stock_demand_port] = get_stock_demand_gateway
app.dependency_overrides[get_question_insight_port] = get_question_insight_gateway
app.dependency_overrides[get_stock_dataset_stats_port] = get_stock_dataset_stats_gateway
app.dependency_overrides[get_forecast_snapshot_port] = get_forecast_snapshot_gateway
app.dependency_overrides[get_paper_trading_port] = get_paper_trading_gateway
app.dependency_overrides[get_paper_decision_port] = get_paper_decision_gateway
app.dependency_overrides[get_forecast_refit_port] = get_forecast_refit_gateway
app.dependency_overrides[get_area_backtest_report_port] = get_area_backtest_report_gateway
app.dependency_overrides[get_news_event_study_port] = get_news_event_study_gateway


# API 문서 — 루트 접속 시 바로 브라우저 로그인창(HTTP Basic)이 뜨는 /docs로 보낸다.
_docs_protected = [Depends(verify_docs_credentials)]


@app.get("/", include_in_schema=False)
def read_root():
    return RedirectResponse("/docs")


@app.get("/docs", include_in_schema=False, dependencies=_docs_protected)
def swagger_ui():
    return get_swagger_ui_html(openapi_url="/openapi.json", title="redoceanmap API - Swagger UI")


@app.get("/redoc", include_in_schema=False, dependencies=_docs_protected)
def redoc_ui():
    return get_redoc_html(openapi_url="/openapi.json", title="redoceanmap API - ReDoc")


@app.get("/openapi.json", include_in_schema=False, dependencies=_docs_protected)
def openapi_schema():
    return app.openapi()


@app.get("/health")
async def health(response: Response):
    """의존성까지 확인하는 헬스체크 — 외부 업타임 모니터가 물리는 지점이다.

    같은 PC에 둔 감시는 그 PC가 꺼지면 함께 죽는다(2026-07-25~27 2일 정지를 아무도 몰랐던 이유).
    밖에서 이 엔드포인트를 폴링하는 것만이 호스트·컨테이너 다운을 잡는다.
    하나라도 죽으면 503으로 답해 모니터가 실패로 세게 한다. 실패 원인 문자열은 싣지 않는다 —
    인증 없이 열린 엔드포인트다(원인은 서버 로그에 남는다).
    """
    db_ok, market_db_ok = await database_ping()
    checks = {
        "database": db_ok,
        "market_database": market_db_ok,
        "redis": await redis_ping(),
    }
    healthy = all(checks.values())
    response.status_code = 200 if healthy else 503
    return {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
        # 배포 식별 — 실패 원인과 달리 이건 공개해도 되는 값이고, 밖에서 폴링하는
        # 모니터가 "떠 있는가"에 더해 "무엇이 떠 있는가"까지 보게 한다.
        # 2026-08-20: 12일 낡은 이미지가 돌며 /chat/ask/progress가 404였는데
        # /health는 계속 ok였다 — 상태만으로는 잡을 수 없는 장애다.
        "version": {"commit": GIT_SHA, "builtAt": BUILT_AT},
    }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
