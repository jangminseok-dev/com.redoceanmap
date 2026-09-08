import ast
import json
import logging
import re

from chat.app.dtos.chat_dto import (
    AreaRecommendation,
    AreaStats,
    AskResponse,
    NewsCardItem,
    StockCard,
)
from chat.app.exceptions import (
    CommercialDataUnavailableError,
    ConversationNotFoundError,
    InvalidLLMResponseError,
)
from chat.app.dtos.area_stat_dto import AreaStatDto
from chat.app.ports.input.chat_use_case import ChatUseCase
from chat.app.ports.output.conversation_repository import ConversationRepository
from chat.domain.entities.conversation_entity import ConversationSummary, Message
from chat.domain.services import answer_guard
from chat.domain.services.verdict import strength as verdict_strength
from chat.domain.services.verdict import verdict as verdict_headline
from core.llm.llm_orchestrator import llm_orchestrator
from hub.app.dtos.commercial_data_dto import (
    AreaInfo,
    AreaInsight,
    AreaRankingInfo,
    AreaRawStat,
    AreaScoreInfo,
    AreaSummary,
    PermitChurnInfo,
)
from hub.app.dtos.market_news_dto import MarketNewsHit
from hub.app.dtos.news_dto import NewsHit, NewsKeyword
from hub.app.dtos.recommendation_record_dto import RecommendedArea
from hub.app.dtos.stock_forecast_dto import StockForecastSummary
from hub.app.dtos.stock_analysis_dto import StockAnalysisResult
from hub.app.dtos.user_profile_dto import UserProfileSummary
from hub.app.ports.output.commercial_data_port import CommercialDataPort
from hub.app.ports.output.gemini_answer_port import GeminiAnswerError, GeminiAnswerPort
from hub.app.ports.output.market_news_search_port import MarketNewsSearchPort
from hub.app.ports.output.news_search_port import NewsSearchPort
from hub.app.ports.output.recommendation_record_port import RecommendationRecordPort
from hub.app.dtos.forecast_refit_dto import RefitCandidateRow, RefitReportInfo
from hub.app.ports.output.forecast_refit_port import ForecastRefitPort
from hub.app.ports.output.fundamental_read_port import FundamentalReadPort
from hub.app.ports.output.stock_analysis_port import StockAnalysisPort, StockAnalysisUnavailable
from hub.app.ports.output.stock_forecast_port import StockForecastPort
from hub.app.ports.output.paper_decision_port import PaperDecisionPort
from hub.app.ports.output.stock_signal_board_port import StockSignalBoardPort
from hub.app.ports.output.user_profile_port import UserProfilePort

logger = logging.getLogger(__name__)

AGE_FIELDS = [
    ("age_10_floating_pop", "10대"),
    ("age_20_floating_pop", "20대"),
    ("age_30_floating_pop", "30대"),
    ("age_40_floating_pop", "40대"),
    ("age_50_floating_pop", "50대"),
    ("age_60_plus_floating_pop", "60대 이상"),
]
# (필드, 표기, 구간 시간수) — 구간 폭이 제각각이라 총합 최대를 그대로 쓰면 가장 넓은
# 새벽 0~6시가 늘 "피크"로 뽑힌다. 시간당으로 나눠 비교해야 실제 붐비는 시간이 나온다
# (미아사거리 실측: 총합 1위는 0~6시지만 시간당으로는 최하위, 실제 1위는 오후 2~5시).
TIME_FIELDS = [
    ("time_00_06_floating_pop", "새벽 0~6시", 6),
    ("time_06_11_floating_pop", "오전 6~11시", 5),
    ("time_11_14_floating_pop", "오전 11시~오후 2시", 3),
    ("time_14_17_floating_pop", "오후 2~5시", 3),
    ("time_17_21_floating_pop", "오후 5~9시", 4),
    ("time_21_24_floating_pop", "밤 9시~자정", 3),
]

# 서울 외 지역 가드 안내의 고정 접두 — question_insight 게이트웨이가 이 문구로
# "가드가 차단한 질문"을 식별한다(단일 정의처 — 문구를 바꾸면 집계도 함께 따라온다).
NONSEOUL_GUARD_PREFIX = "지금은 서울 상권 데이터만 분석할 수 있어요."

# 서울 외 주요 지역명 — 상권 데이터가 서울뿐이라, 이 지명만 언급된 질문은
# phase1 호출 전에 결정론적으로 "준비중" 안내로 차단한다.
# "경기"는 경기(景氣), "김포"는 김포공항(서울 강서구)과 겹쳐 제외.
NON_SEOUL_REGIONS = (
    "수원", "인천", "부산", "대구", "대전", "광주", "울산", "세종", "제주",
    "성남", "용인", "고양", "부천", "안양", "안산", "화성", "평택",
    "파주", "의정부", "남양주", "하남", "광명", "시흥", "군포", "구리",
    "분당", "판교", "일산", "동탄",
    "춘천", "원주", "강릉", "청주", "천안", "아산", "전주", "군산",
    "목포", "여수", "순천", "포항", "경주", "구미", "창원", "김해", "진주",
    "경기도", "강원도", "충청북도", "충청남도", "전라북도", "전라남도",
    "경상북도", "경상남도",
)

# phase2에 넘길 상권 수 상한 — 답변 분량은 상권 수 × reason 길이로 곱해진다.
# PHASE2_PROMPT가 "모든 상권을 각각 포함"을 요구하기 때문(그 규칙은 모델이 일부만 서술하는
# 3차 실측 결함을 막는 것이라 뺄 수 없다). 그래서 분량은 프롬프트가 아니라 **투입 개수**로 줄인다.
# 지역·반경 가드가 이미 [:3]으로 좁히므로 같은 값을 쓴다(2026-08-28, "답이 너무 길다" 피드백).
MAX_AREAS = 3

# 상권 해석 문장(area_narrator)의 주입 우선순위 — 프롬프트 예산상 상권당 상위 4개만 쓴다.
# 앞쪽일수록 "여기가 어떤 상권인가"를 먼저 규정한다. 성별은 정보량이 가장 낮아 뒤로.
_INSIGHT_PRIORITY = (
    "demand_type",          # 오피스형/주거형/혼합 — 상권 성격의 뼈대
    "facility_anchor",      # 역·대학·백화점 — "여기 사람이 왜 오는가"
    "change_indicator",     # 상권 생멸의 방향(서울시 1급 축) — 이름만으론 의미가 없어 해석 문장으로(I-1)
    "traffic_vs_sales",     # 통행↔매출 괴리 — 부정 신호가 추천 신뢰도를 가장 크게 올린다
    "avg_ticket",           # 객단가 — 창업 판단에 직결
    "avg_ticket_age",       # 가장 비싸게 쓰는 연령대(방문층과 다를 때 특히 값어치)
    "avg_ticket_rhythm",    # 주중/주말 객단가 차이
    "customer_age",         # 핵심 연령대
    "sales_rhythm_peak",    # 피크 시간대·요일
    "spending_power",       # 배후 소득·지출 카테고리
    "sales_rhythm_weekend",  # 주말/주중 리듬
    "demand_apartment",     # 아파트 배후 비중
    "customer_gender",      # 우세 성별
)

INTENT_PROMPT = """사용자 질문의 의도를 분류하라.
- "stock": 특정 회사/종목(시세·전망·분석)을 묻는 질문. 회사 이름만 언급해도 stock이다.
- "market_news": 특정 종목이 아니라 업종·산업·증시 전반의 동향/뉴스를 묻는 질문.
- "market": 동네/상권/창업/입지를 묻는 질문.
- "general": 위 셋에 해당하지 않는 질문 — 인사·잡담·일반 상식·인물·기술 등 상권/주식과 무관한 것 전부.

stock이면 종목을 stock_query에 추출한다. 한국 회사는 **한국어 이름 그대로** 쓰고 절대
티커를 지어내지 않는다. 해외(미국) 회사만 널리 알려진 공식 티커로 정규화한다
(예: 테슬라 → "TSLA", 애플 → "AAPL"). 티커가 확실하지 않으면 이름 그대로 둔다.

예시:
- "삼성전자 주가 어때?" → {"intent": "stock", "stock_query": "삼성전자"}
- "하이닉스 어때?" → {"intent": "stock", "stock_query": "하이닉스"}
- "엔비디아는 어때?" → {"intent": "stock", "stock_query": "NVDA"}
- "샌디스크 어때?" → {"intent": "stock", "stock_query": "샌디스크"}
- "카카오 지금 사도 돼?" → {"intent": "stock", "stock_query": "카카오"}
- "반도체 업황 어때?" → {"intent": "market_news", "stock_query": ""}
- "요즘 금리가 증시에 어떤 영향 주고 있어?" → {"intent": "market_news", "stock_query": ""}
- "AI 관련주 분위기 어때?" → {"intent": "market_news", "stock_query": ""}
- "성수동은 어때?" → {"intent": "market", "stock_query": ""}
- "홍대에 카페 차릴만해?" → {"intent": "market", "stock_query": ""}
- "카파시가 누구야?" → {"intent": "general", "stock_query": ""}
- "안녕! 뭐 할 수 있어?" → {"intent": "general", "stock_query": ""}

반드시 아래 JSON 형식으로만 응답하라 (마크다운 코드블록 없이):
{"intent": "market", "stock_query": ""}"""

STOCK_ANSWER_PROMPT = """당신은 주식 분석 상담사입니다.
제공된 지표·감성 수치만 근거로 종목의 현재 상황을 한국어 **3~4문장**으로 설명하세요.
길게 쓰지 마세요 — 읽는 사람이 알고 싶은 것은 지금 상태가 어떤지이지 지표 전체 목록이 아닙니다.

**첫 문장은 결론입니다.** 추세와 거래량을 합쳐 지금 상태를 한 줄로 판정하세요
(예: "정배열이지만 거래량이 따라오지 않아 신뢰하기 어려운 상태입니다").
그다음 문장에서 그 판정의 근거를 짧게 붙입니다.

담을 것 (1·2는 필수, 3은 두드러진 것 **하나만**):
1. 추세 — 이동평균 배열과 현재가 위치. 배열은 **지금까지의 결과**다. 정배열/역배열을
   "매수세가 강하다"처럼 현재의 힘으로 바꿔 말하지 말 것
2. 거래량 검증 — 추세 방향에 거래량이 동의하는지 '신뢰' 또는 '의심'이라는 단어로 판정할 것
   (가격 방향 + 거래량 증가 = 신뢰 / 방향은 있는데 거래량 감소·한산 = 의심 / 추세가 뚜렷하지
   않으면 판정을 생략하고 거래량 수준만 언급)
3. 모멘텀(RSI·12-1) 또는 가격대(지지·저항선, 거래 밀집 구간, 볼린저 위치) 중
   **현재가와 가장 가깝고 특기할 만한 것 하나만** — 둘 다 쓰지 말 것

규칙:
- 수치는 제공된 그대로 인용 (전부 나열하지 말 것)
- '참고 신호'가 제공된 경우에만 검증된 참고 신호로 언급하되, 상승 확률이나 매수 권유로 표현 금지
- '거래 밀집 구간'은 과거 거래량이 몰린 가격대라는 **팩트로만** 인용한다. 지지선·저항선으로
  바꿔 부르거나 "여기서 지지받는다/막힌다"처럼 앞으로의 움직임을 단정하지 말 것
- '관련 뉴스'가 제공되면 감성 라벨(호재/악재 방향)과 함께 근거로 인용
- 매수/매도 지시 금지, 상승/하락 확률 단정 금지 — 방향 전망은 참고 신호로만 표현
- 주식 초보자도 이해할 수 있게 설명 — 전문 용어를 처음 쓸 때는 괄호로 짧은 우리말 풀이를 붙인다
  (예: RSI(최근 상승·하락 힘의 균형을 0~100으로 나타낸 지표), 지지선(주가가 잘 안 내려가는 가격대))
- 수치가 의미하는 바를 일상적인 말로 해석해 서술 — 전문성은 유지하되 어려운 표현만 나열하지 말 것
- 출처 표기: 수치나 사실을 말하는 문장 끝에 근거 번호를 [1]처럼 붙일 것(복수 근거면 [1][5]).
  컨텍스트에 '근거 [n]'으로 표시된 번호만 쓰고, 표시되지 않은 번호를 만들지 말 것
- 마지막에 투자 판단은 본인 책임이라는 고지 한 문장을 포함 — 이 고지 문장에는 근거 번호를 붙이지 않는다"""

MARKET_NEWS_ANSWER_PROMPT = """당신은 시장·업황 분석 상담사입니다.
제공된 수집 뉴스 헤드라인과 감성 라벨만 근거로 질문한 업황/시장 동향을 한국어 **3~4문장**으로 설명하세요.
**첫 문장은 결론입니다** — 지금 이 업황이 어느 쪽으로 기울어 있는지 한 줄로 말하고,
그다음에 그렇게 본 근거가 된 헤드라인을 붙이세요. 헤드라인을 순서대로 나열하지 마세요.

규칙:
- 헤드라인에 없는 사실을 지어내지 않고, 감성 라벨(호재/악재 방향)을 함께 해석
- 헤드라인의 발행일을 감안해 시점을 명시 (오래된 뉴스는 그렇게 안내)
- 초보자도 이해할 수 있게 어려운 경제 용어는 괄호로 짧은 우리말 풀이를 곁들여 설명
- 개별 종목 매수/매도 지시 금지, 방향 단정 금지
- 출처 표기: 수치나 사실을 말하는 문장 끝에 근거가 된 뉴스 번호를 [1]처럼 붙일 것(복수면 [1][3]).
  컨텍스트에 '근거 [n]'으로 표시된 번호만 쓰고, 표시되지 않은 번호를 만들지 말 것
- 근거가 헤드라인(제목) 수준임을 감안해 단정을 피하고, 마지막에 투자 판단 책임 고지 한 문장
  (고지 문장에는 근거 번호를 붙이지 않는다)"""

PHASE1_PROMPT = """당신은 서울 상권 분석 전문가입니다.
사용자 질문을 보고 다음을 결정하세요:
1. 가장 적합한 service_code (업종 코드)
2. 추천할 상권 trdar_code 3~5개

반드시 아래 JSON 형식으로만 응답하세요 (마크다운 코드블록 없이):
{"service_code": "CS000000", "service_name": "업종명", "trdar_codes": [1000001, 1000002, 1000003]}

규칙:
- 위 예시의 값은 **형식 안내용 자리표시자**다. 그대로 복사하지 말고 아래 규칙대로 실제 값을 고를 것
- service_code는 반드시 제공된 목록에서 선택
- trdar_code는 반드시 상권 데이터에 있는 값 사용
- 질문에 특정 지역(동·역·상권명)이 언급되면 '질문지역' 칸에 ★ 표시된 상권을 반드시 우선 선택
- 제공된 상권 데이터는 모두 서울이다 — 질문 지역이 표에 없으면 비슷한 이름의 다른 상권을 임의로 고르지 말 것
- 상권 전체 월매출 규모와 위치(자치구, 행정동)를 기준으로 사용자 질문에 맞는 곳 선택
- 질문이 "작년 대비"·"성장"·"매출 오른"을 물으면 '매출전년동분기대비(%)' 열이 큰 상권을 우선 선택 ('-'는 산출 불가)
- 질문이 "폐업률 낮은"·"안정적인"·"오래 가는"을 물으면 '폐업률(%)' 열이 작은 상권을 우선 선택 ('-'는 미집계)
- 질문이 "점포당 매출"·"장사 잘 되는"·"한 가게당"을 물으면 '점포당월매출(만원)' 열이 큰 상권을 우선 선택 ('-'는 미집계)"""

PHASE2_PROMPT = """당신은 서울 창업 컨설턴트입니다.
제공된 각 상권의 공공데이터 수치를 기반으로 창업자에게 유용한 설명을 작성하세요.

반드시 아래 JSON 형식으로만 응답하세요 (마크다운 코드블록 없이):
{
  "text": "결론 1~2문장 — 어디를 추천하는지 먼저 말하고, 그 판단의 핵심 근거 수치 하나를 붙인다",
  "areas": [
    {
      "trdar_code": 1000001,
      "reason": "이 상권을 추천하는 이유 (분량은 아래 차등 규칙을 따를 것. 반드시 제공된 수치 인용, 창업자 관점. 마지막 문장은 반드시 '유의할 점: …'으로 시작)"
    }
  ]
}

**분량 차등 — areas 배열의 첫 번째 상권만 상세히 쓴다.**
읽는 사람은 어디로 갈지를 정하려는 것이지 모든 후보의 평가서를 원하지 않는다.

- **1순위(배열 첫 항목)**: 3문장 + "유의할 점" 1문장. 서술 순서는 아래 판단 순서를 따른다.
  1. 수요 — 유동인구·상권 성격
  2. 경쟁 — 동일 업종 점포 수·프랜차이즈 비중
  3. 수익성 — 점포당 매출과 그 산출 근거 (생존 지표는 유의할 점에서 다뤄도 된다)
- **2순위 이하**: 1문장 + "유의할 점" 1문장. 그 상권을 고를 이유가 되는 **수치 하나만**
  골라 쓰고 나머지는 생략한다. 1순위와 무엇이 다른지가 드러나면 충분하다.

"유의할 점: …"은 **모든 상권에 빠짐없이** 쓴다(순위 무관). 제공된 수치 중 **부정 신호 하나**
(높은 폐업률·경쟁 밀집·통행-매출 괴리·거래 한산 등)를 솔직하게 짚을 것. 부정 신호가 없어
보이면 데이터의 한계(임대료·권리금 미보유 등)를 유의점으로 쓸 것.

규칙:
- **areas에는 위 컨텍스트에 제공된 모든 상권을 각각 하나씩 포함할 것** — 일부만 쓰고
  끝내면 나머지 상권은 이유 없는 추천이 된다 (3차 실측: 모델이 상권 3곳 중 1곳만 서술).
  분량을 줄이는 것은 2순위 이하의 **문장 수**이지 상권 자체를 빼는 것이 아니다
- text와 reason 모두 자연스러운 한국어로 작성
- 수치는 **제공된 단위 그대로** 인용 — 만원을 억원으로 바꾸는 등 단위 환산 금지
- 종합점수는 제공된 표기("N점")로만 인용 — "N/100", "성장도 N" 등 다른 형식 창작 금지
- 임대료·보증금·권리금 데이터는 없다 — 추정해 말하지 말 것
- 수치를 단순 나열하지 말고 의미를 해석해서 서술
- '서울 평균 대비' 종합점수가 제공된 상권은 그 근거(성장·건강도·지속성)를 추천 이유에 반영 (50점 = 서울 평균 수준)
- '관련 지역 기사'가 제공되면 해당 지역 상권의 트렌드 근거로 반영 (기사 제목 인용 가능, 없는 사실 창작 금지).
  기사에는 **제목과 발행일만** 있다 — 연도·매체 평가 등 제공되지 않은 부가 정보를 붙이지 말 것
- '인허가 업소 교체'가 제공되면 개업·폐업을 함께 읽어 상권이 커지는 중인지 갈아치우는 중인지 해석
  (개업만 인용해 '성장'으로 단정하지 말 것). '현재 영업중' 수는 위 '점포' 수치와 **출처가 다르므로
  둘을 비교하거나 검산하지 말 것** — 어느 쪽이 맞다/틀리다는 서술 금지
- **위 컨텍스트에 없는 사실을 절대 지어내지 말 것**. 특히 지하철 노선·환승역·행정구·랜드마크·
  '○○구 관문' 같은 입지 설명은 제공되지 않았으므로 언급 자체를 금지한다
  (실제 오류 사례: 성북구 미아사거리를 '5,8호선 환승, 강동구 관문'이라고 서술)
- 기사는 지역 트렌드 배경으로만 쓰고, 기사에 나온 다른 지역·상권의 특성을 이 상권의 특성인 것처럼 옮기지 말 것
- '유동인구 최다 연령대'는 통행량 기준이다. 이를 '주요 고객층'·'구매층'으로 바꿔 부르지 말 것
- '상권 성격'(고객층·배후 수요·객단가·소비력)은 제공된 문장만 인용하고, 제공되지 않은 해석을 새로 만들지 말 것"""

STREAM_SYSTEM_PROMPT = """당신은 서울 상권 분석 상담사입니다.
사용자와 자연스럽게 대화하며 상권 선택·창업 관련 조언을 제공합니다.
이전 대화 맥락을 이어받아 답하고, 확실치 않은 수치는 단정하지 말고 솔직히 안내합니다.
서울 외 지역 상권 질문에는 해당 지역 데이터가 아직 준비 중이라고 안내합니다.
구체적인 상권 추천이 필요하면 사용자가 지역과 업종을 말하도록 유도합니다.
구체적인 종목 분석이나 업황/시장 동향은 데이터 근거가 있는 일반 질문(ask) 경로를 이용하도록 안내합니다."""


def _top_field(obj, fields: list[tuple[str, str]]) -> str:
    best = max(fields, key=lambda f: getattr(obj, f[0], 0) or 0)
    return best[1]


def _top_time_field(obj, fields: list[tuple[str, str, int]]) -> str:
    """시간당 평균이 가장 큰 시간대 — 구간 폭 보정(위 TIME_FIELDS 주석 참고)."""
    best = max(fields, key=lambda f: (getattr(obj, f[0], 0) or 0) / f[2])
    return best[1]


# 지시어 — 직전 추천을 가리키는 후속 질문의 표지. 보수적으로 유지한다("여기"는
# "여기 어때?"처럼 새 질문에도 흔해 제외). 지시어 + 직전 추천 존재 = 후보 제한 가드.
# 도메인 후속 어휘(P4-7) — general 판정을 직전 도메인으로 되돌릴 단서. 보수적으로:
# 상권·주식 대화에서만 나오는 명사를 담고, 인사·잡담 어휘는 담지 않는다.
_DOMAIN_FOLLOWUP_RE = re.compile(
    r"등급|점수|상권|경쟁|폐업|유동인구|매출|배후|업종|창업|가게|점포"
    r"|종목|주가|매물대|지지선|저항선|수급|거래량|신호|차트"
)

DEICTIC_TOKENS = (
    "그 중", "그중", "거기", "그곳", "방금", "아까", "그 상권", "그 동네", "이 중",
)


def _has_deixis(prompt: str) -> bool:
    return any(token in prompt for token in DEICTIC_TOKENS)


# 제외 조건 어휘(P2·P7) — "강남 말고" 류는 직전 추천으로 제한하면 정반대 답이 된다
EXCLUSION_TOKENS = ("말고", "빼고", "제외", "다른 데", "다른 곳", "다른 동네", "딴 데")


def _has_exclusion(prompt: str) -> bool:
    return any(token in prompt for token in EXCLUSION_TOKENS)


# 일반명사와 동음인 지명 어간(4차 실측 M8 t2: "방학엔 장사 안 되지 않아?"의 '방학'이
# 도봉구 방학역에 걸려 관악구 질문이 방학역 추천으로 샜다). 이 어간은 장소 접미가
# 따라올 때만 지명으로 인정한다. 실측으로 잡힌 것만 등재한다.
_HOMONYM_STEMS = ("방학", "신사", "대치")


def _stem_means_place(stem: str, prompt: str) -> bool:
    if stem not in _HOMONYM_STEMS:
        return True
    return bool(re.search(re.escape(stem) + r"\s?(?:역|동|상권|쪽|근처|인근|사거리)", prompt))


# 장소를 겨눈 제외("다른 데/곳/동네" 류)는 어떤 경우든 지역 승계를 끊어야 한다
_PLACE_EXCLUSION_RE = re.compile(r"다른\s?(?:데|곳|동네)|딴\s?데|(?:거기|여기)\s?(?:말고|빼고)")


def _exclusion_targets_service(prompt: str, service_codes) -> bool:
    """제외 어휘가 전부 업종을 겨눴는지 — "국밥 말고 돈까스집"은 업종 교체이지 지역
    이탈이 아니다(4차 실측 M4 t4: 지역 승계가 풀려 노원→이태원 점프). 말고/빼고/제외의
    바로 앞 어절이 업종 단서일 때만 업종 제외로 인정한다(보수적)."""
    if _PLACE_EXCLUSION_RE.search(prompt):
        return False
    hits = list(re.finditer(r"말고|빼고|제외", prompt))
    if not hits:
        return False
    for m in hits:
        head = prompt[max(0, m.start() - 12):m.start()]
        if _detect_service(head, service_codes) is None:
            return False
    return True


# 업종 단서 어휘(P2) — 질문이 업종을 새로 말했는지의 보수적 판정. phase1이 고른 업종명
# 토큰과 함께 본다("카페는 포화 아니야?"는 힌트 있음 → phase1 신뢰, "뭘 조심해야 해?"는
# 힌트 없음 → 직전 업종 승계).
_SERVICE_HINT_TOKENS = (
    "카페", "커피", "치킨", "분식", "한식", "중식", "일식", "양식", "고기", "곱창",
    "술집", "호프", "주점", "빵", "제과", "베이커리", "디저트", "미용", "네일", "옷",
    "의류", "패션", "편의점", "약국", "식당", "음식점", "반찬", "정육", "과일", "꽃",
    "문구", "서점", "학원", "피시방", "노래방", "세탁", "부동산", "김밥", "국수", "피자",
    "버거", "족발", "횟집", "초밥",
)


def _service_hinted(prompt: str, service_name: str) -> bool:
    if any(token in prompt for token in _SERVICE_HINT_TOKENS):
        return True
    return any(t in prompt for t in re.findall(r"[가-힣]{2,}", service_name or ""))


# 업종 결정론 감지(2026-09-01 실측) — "길음동에서 떡볶이집"을 phase1이 커피-음료로
# 오선택했고, 업종 승계 가드가 그 오선택을 3턴 내내 고착시켰다(사용자가 "떡볶이집을
# 추천해달라고 했는데?"라고 정정해도 단서 토큰에 '떡볶이'가 없어 승계가 이김).
# 사용자가 말한 업종은 코드가 감지해 **항상 이기게** 한다. (별칭, 서비스명 포함 키워드) 쌍.
_SERVICE_ALIASES = (
    ("떡볶이", "분식"), ("떡볶기", "분식"), ("순대", "분식"), ("어묵", "분식"),
    ("라볶이", "분식"), ("김밥", "분식"), ("튀김", "분식"),
    ("카페", "커피"), ("커피", "커피"), ("디저트", "제과"), ("빵", "제과"),
    ("베이커리", "제과"), ("케이크", "제과"),
    ("치킨", "치킨"), ("통닭", "치킨"),
    ("술집", "주점"), ("호프", "주점"), ("맥주", "주점"), ("포차", "주점"), ("주점", "주점"),
    ("햄버거", "패스트푸드"), ("버거", "패스트푸드"),
    ("한식", "한식"), ("국밥", "한식"), ("백반", "한식"), ("고기", "한식"),
    ("삼겹", "한식"), ("갈비", "한식"), ("족발", "한식"), ("찌개", "한식"),
    ("초밥", "일식"), ("스시", "일식"), ("돈까스", "일식"), ("라멘", "일식"),
    ("횟집", "일식"), ("일식", "일식"),
    ("짜장", "중식"), ("짬뽕", "중식"), ("마라", "중식"), ("중식", "중식"),
    ("파스타", "양식"), ("피자", "양식"), ("스테이크", "양식"), ("양식", "양식"),
    ("편의점", "편의점"), ("반찬", "반찬"), ("미용", "미용"), ("헤어", "미용"),
    ("네일", "네일"), ("세탁", "세탁"), ("문구", "문구"), ("서점", "서적"),
)

# 정정 신호 — 사용자가 앞선 답을 바로잡는 중이면 직전 업종을 승계하지 않는다
_CORRECTION_TOKENS = (
    "라고 했", "라고 말했", "말했잖", "했잖아", "아니라", "아닌데", "잘못", "다시 추천",
)


def _has_correction(prompt: str) -> bool:
    return any(token in prompt for token in _CORRECTION_TOKENS)


def _detect_service(prompt: str, service_codes) -> tuple[str, str] | None:
    """프롬프트가 말한 업종을 결정론으로 찾는다 — 없으면 None(phase1·승계에 맡김).

    서비스명 직접 언급(긴 이름 우선)을 먼저, 별칭(긴 것 우선)을 다음에 본다.
    별칭은 전부 2자 이상 — 1자("회")는 "회사" 류 오탐을 만든다.
    """
    for sc in sorted(service_codes, key=lambda c: -len(c.name)):
        if any(t in prompt for t in re.findall(r"[가-힣]{2,}", sc.name)):
            return sc.code, sc.name
    for alias, keyword in sorted(_SERVICE_ALIASES, key=lambda a: -len(a[0])):
        if alias in prompt:
            for sc in service_codes:
                if keyword in sc.name:
                    return sc.code, sc.name
    return None


# 서비스 메타 질문 가드(1-2) — "너희 UP 시그널 적중률이 어떻게 돼?"를 LLM에 보내면
# 자기 서비스를 제3자 취급하는 일반론("해당 서비스에 데이터를 요구하세요")이 나온다
# (2026-08-31 프로덕션 실측). 자기 지칭 + 검증 어휘가 함께 있을 때만 결정론으로 가로챈다 —
# 자기 지칭 없는 "삼성전자 신호 검증된 거야?"는 기존 종목 경로를 그대로 탄다(보수적 매칭).
_META_SELF_RE = re.compile(r"너희|너네|니네|당신들|이\s?(서비스|사이트|앱)")
# 3차 실측(P1): "너네 신호 지난달에 몇 개나 맞았는데?"가 "적중률" 어휘가 없어 새어나가
# general(Gemini)로 낙하했다 — 구어 검증 어휘까지 넓힌다(자기 지칭 동반 조건은 유지).
_META_VERIFY_RE = re.compile(
    r"적중|백테스트|표본|신뢰\s?구간|승률|검증|맞았|맞춘|맞혔|증거|성적|실적"
)


# 급등주 찍기 질의(P5) — 종목/주식 명사와 결합했을 때만(보수적 — "이 주식 추천해?"는 제외)
# AI 모의투자 기록 질의(2026-09-08 QA) — 정체성 질문("너 뭐 사?")과 구분하려고 AI·모의투자 명사를 요구한다
_PAPER_RE = re.compile(
    r"(?:AI|에이아이|인공지능|EXAONE|엑사원)\s*(?:는|은|가|이)?\s*(?:요즘|최근|오늘|지금|어제)?\s*(?:뭐|무엇|무슨|어떤|어느)\s*\S{0,4}\s*(?:사|샀|매수|팔|판|들고|보유|굴리)"
    r"|모의\s*투자|AI\s*투자|엑사원|EXAONE",
    re.IGNORECASE,
)
# 상대 비교 후속(2026-09-08 QA P10) — "제일 안전한 데"에 폐업률이 가장 높은 곳을 골랐다. 축이 있는 비교는 코드가 정한다
_SUPERLATIVE_AXES = (
    ("closure", re.compile(r"(?:제일|가장|젤)\s*(?:안전|덜\s*위험|안\s*망|망하지\s*않|폐업\s*(?:률|율)?\s*(?:이|가)?\s*(?:낮|적))")),
    ("sales", re.compile(r"(?:제일|가장|젤)\s*(?:매출|장사|수익)\s*(?:이|가)?\s*(?:높|많|큰|잘)")),
)
# 업종 초점 후속(2026-09-08 QA P08) — "내 예산으로 할 수 있는 업종은?"에 직전 상권·업종을 재탕했다.
# 직전 추천 상권이 있고 질문이 업종을 묻는데 업종명을 안 대면, 그 상권의 업종별 수치를 코드가 낸다.
# 예산 금액 파싱 — "1억 2천", "8천만원", "5000만원", "1.5억" → 원. 못 읽으면 None.
_BUDGET_RE = re.compile(r"(\d+(?:\.\d+)?)\s*억(?:\s*(\d+)\s*천?\s*만?)?|(\d+(?:,\d{3})*)\s*(천만|만)\s*원?")
SMALL_SAMPLE_STORES = 5   # 점포 수가 이 미만이면 점포당 매출·폐업률을 결론 근거로 쓰지 않는다(2026-09-08 감사)
GENERIC_SERVICE_CODE = "CS000000"   # 업종 미지정 질문의 범용 코드 — market 게이트웨이가 전 업종 합계로 답한다
BUDGET_RESERVE_RATIO = 0.7  # 창업비용은 예산의 70%까지 — 보증금·운영자금 몫을 남긴다(가정치)
# 질문 어휘 → 공정위 업종 중분류명(브랜드 집계 기준). 질문한 업종을 먼저 판정하기 위한 별칭
_INDUSTRY_ALIASES = (
    ("카페", "커피"), ("커피", "커피"), ("치킨", "치킨"), ("분식", "분식"), ("떡볶이", "분식"), ("편의점", "편의점"),
    ("한식", "한식"), ("피자", "피자"), ("빵집", "제과제빵"), ("베이커리", "제과제빵"), ("제과", "제과제빵"),
    ("주점", "주점"), ("술집", "주점"), ("호프", "주점"), ("중식", "중식"), ("일식", "일식"), ("패스트푸드", "패스트푸드"),
    ("햄버거", "패스트푸드"), ("아이스크림", "아이스크림/빙수"), ("빙수", "아이스크림/빙수"), ("음료", "음료 (커피 외)"),
    ("미용", "이미용"), ("네일", "이미용"), ("세탁", "세탁"), ("학원", "교육 (교과)"), ("헬스", "스포츠 관련"),
)


def fmt_won(amount: float) -> str:
    """1억 2,000만원 · 8,036만원 — 만원 단위, 억은 앞에 뗀다."""
    man = int(round(amount / 10_000))
    if man >= 10_000:
        eok, rest = divmod(man, 10_000)
        return f"{eok}억원" if rest == 0 else f"{eok}억 {rest:,}만원"
    return f"{man:,}만원"


def parse_budget_krw(text: str) -> int | None:
    m = _BUDGET_RE.search(text)
    if not m:
        return None
    if m.group(1):
        won = float(m.group(1)) * 100_000_000
        if m.group(2):
            won += int(m.group(2)) * 10_000_000  # "1억 2천" — 천 단위는 천만원으로 읽는다
        return int(won)
    n = int(m.group(3).replace(",", ""))
    return n * (10_000_000 if m.group(4) == "천만" else 10_000)


_SERVICE_FOCUS_RE = re.compile(r"업종|뭘\s*팔|무슨\s*(?:장사|가게|업)|어떤\s*(?:가게|장사|업)|아이템")
_SERVICE_SHORTLIST = ("커피", "치킨", "한식", "분식", "편의점", "미용", "네일", "제과", "호프", "중식", "일식", "패스트푸드", "의약품", "세탁")
_COMPARE_RE = re.compile(r"비교|vs|중에|둘\s*중|셋\s*중|어디가|어느\s*(?:쪽|게|것)|(?:랑|이랑|와|과|하고)\s")
_SURGE_PICK_RE = re.compile(
    # 4차 실측 S4: "내일 급등할 종목 알려줘"가 관형형 어미(할/하는) 때문에 빠져나가
    # market_news로 낙하했다. 거절 후 재요구("아 그러지 말고 하나만 찍어줘")도 잡는다.
    r"(?:급등|상한가|오를|수익\s?나?\s?는)(?:할|하는)?\s*(?:만한)?\s*(?:종목|주식).{0,10}(?:찍|골라|추천|알려)"
    r"|(?:종목|주식)\s*(?:하나|한\s?개)?\s*만?\s*(?:찍어|골라)"
    r"|하나만\s*찍어"
)


# 신호 보드 조회(4차 실측 S8 t4) — "상승 신호 종목 뭐야?"가 market_news로 낙하해 신호
# 데이터가 아니라 뉴스로 답했다. 보드(종목 예측 화면)와 같은 자료를 코드가 읽어 답한다.
# 보수적으로: 방향 어휘 또는 '나온/뜬' 류 동반 + 종목/주식 명사. "삼성전자 신호 어때?"처럼
# 종목 하나를 묻는 문장은 잡지 않는다(그건 stock 경로의 몫).
_SIGNAL_BOARD_RE = re.compile(
    r"(?:상승|하락|매수|매도)\s*신호(?:가|이|는|은)?\s*(?:나온|뜬|난|있는|잡힌|보이는|켜진)?\s*(?:종목|주식)"
    r"|신호(?:가|이)?\s*(?:나온|뜬|난|잡힌|켜진)\s*(?:종목|주식)"
    r"|신호\s*보드"
)
_SIGNAL_BOARD_LIMIT = 5  # 답변에 싣는 종목 수 — 전체는 화면 보드로 안내

# 뉴스 상세 후속(3차 P8 s08 t2) — "그 뉴스가 뭔데?"에 지표 분석으로 답했다. 직전 카드의
# 근거 뉴스(제목·날짜·라벨)를 코드가 그대로 보여준다. 지시어 동반 조건으로 새 질문
# ("반도체 뉴스 알려줘")과 가른다.
_NEWS_DETAIL_RE = re.compile(
    r"(?:그|아까|방금)\s*(?:뉴스|기사)"
    r"|(?:뉴스|기사)(?:가|는|은|를|들)?\s*(?:뭔데|뭐였|뭐길래|뭐지|자세히|상세|제목)"
)

# 알림 기능 질문 판정 — "알림" 명시 + 사용 의도 어휘가 함께 있을 때만(오탐 억제).
# "떨어지면 알려줄 수 있어?" 류(알림 단어 없음)는 P6(알림 의사 감지) 백로그의 몫.
_ALERT_HOWTO_RE = re.compile(
    r"알림(?:[^.\n]{0,20})?(?:설정|등록|어떻게|방법|걸|받|없어|있어|되|돼|가능)"
    # 알림 의사(3차 P6, 4차 S6 t5) — '알림' 단어 없이 조건부(-면)로 통지를 청하는 표현.
    # 조건 어미를 요구해 "떨어지는 이유 알려줘" 같은 설명 요청과 가른다.
    r"|(?:떨어지면|내려가면|오르면|올라가면|도달하면|닿으면|찍으면|되면)[^.\n]{0,12}알려"
)
# 실기능만 적는다(허브 컴포저·프로필 화면과 일치). 여기 없는 기능을 안내하면 안 된다.
_ALERT_HOWTO_TEXT = (
    "알림은 세 가지를 제공해요.\n"
    "1) 가격 도달 알림 — 프로필 페이지의 '가격 도달 알림'에서 종목·기준가·방향(이상/이하)을"
    " 등록하면, 매시 자동 스캔이 도달을 확인해 이메일·텔레그램으로 한 번 알려드려요"
    "(도달 후 자동 비활성화). 시세는 수집 주기 기준이라 최대 1시간가량 늦을 수 있어요.\n"
    "2) 관심 종목 뉴스 알림 — 종목을 북마크해 두면 감성이 강한 새 기사가 수집될 때 감성"
    " 라벨과 현재 신호 상태를 함께 알려드려요.\n"
    "3) 북마크 신호 알림 — 북마크 종목에 검증된 상승 참고 신호가 켜지면 알려드려요.\n"
    "상권 쪽 알림(임대료·권리금 변동 등)은 제공하지 않아요 — 상권 데이터는 분기 단위"
    " 공공데이터라 실시간 통지 대상이 아니에요."
)


# 점수 방법론·서비스 개념 질문(4차 실측 M7 t1·t2, M10 t2) — "점수 어떻게 계산해?"에
# 추천을 발사했다. 지역 언급이 없으면 설명이 답이다 — LLM 없이 코드가 답한다.
_METHOD_QUERY_RE = re.compile(
    r"(?:점수|종합점수)[^.\n]{0,14}(?:어떻게|계산|산출|기준|믿을|신뢰)"
    r"|서울\s?평균이?\s?기준"
    r"|상권\s?분석이?\s?(?:뭔데|뭐야|무엇)"
)
# 산출 방식 블록(I-20 wants_detail 주입분)과 같은 내용 — 정의가 갈리면 안 된다
_METHOD_QUERY_TEXT = (
    "상권 분석은 서울시 공공데이터(분기 단위)로 상권별 매출·유동인구·점포·개폐업을 읽고,"
    " 업종·지역에 맞는 후보를 추려 드리는 기능이에요.\n"
    "종합점수는 서울 평균을 50점으로 놓고 4개 컴포넌트 — 매출 성장·유동인구 성장(직전"
    " 분기 대비)·개폐업 건강도·영업 지속성 — 를 0~100으로 환산해 종합한 값이에요."
    " 50점보다 높으면 서울 평균 상회, '주의/위험' 등급은 평균에 크게 못 미친다는 뜻이에요.\n"
    "특정 상권의 점수와 근거가 궁금하시면 \"성수역 상권 점수 알려줘\"처럼 상권 이름과"
    " 함께 물어봐 주세요."
)


def _is_service_meta(prompt: str) -> bool:
    return bool(_META_SELF_RE.search(prompt) and _META_VERIFY_RE.search(prompt))


# 반경 질의 가드(I-10) — "반경 500m"·"1km 이내" 같은 거리 제약을 결정론으로 처리한다.
# 실측(2026-08-24): "강남역 반경 500m" 질문에 어간 매칭이 강남구 104곳을 후보로 올려
# 추천 5곳 중 3곳이 3km 밖이었다. 좌표 필터가 성립하면 코드로 자르고, 중심을 못 찾으면
# 필터한 척하지 않고 미적용을 답변 문두에 명시한다.
_RADIUS_PATTERN = re.compile(
    r"(?:반경\s*)?(\d+(?:\.\d+)?)\s*(km|㎞|킬로미터|킬로|미터|m)(?![a-zA-Z])"
)

# 중심 상권 매칭에서 제외하는 상권명 일반 어휘 — 이런 낱말 하나로 중심을 잡으면
# "먹자골목 반경 500m"이 엉뚱한 골목 상권을 중심으로 삼는다.
_RADIUS_NAME_STOPWORDS = frozenset(
    {"상권", "시장", "거리", "골목", "공원", "광장", "상가", "단지", "타운", "프라자", "먹자골목"}
)

# 전문가 데이터 질문 라우팅(I-20, 2026-08-31 실측 p04·p05·p09) — 추이·산출근거·개폐업
# 데이터 요청에 151자 일반 추천이 나갔다. 데이터는 스코어 슬라이스에 이미 있다 — 감지 시
# 분기 추이·산출 방식을 컨텍스트에 주입한다(평시 미주입 — 프롬프트 예산 보호).
_EXPERT_DETAIL_RE = re.compile(r"추이|추세|분기별|산출\s*근거|산출\s*방식|어떻게\s*계산|개폐업")

# 미지원 축 결정론 고지(I-12) + 확률 질문 안내(I-17) — 질문이 우리가 갖고 있지 않은
# 데이터를 물으면 "없다"를 첫 문장에 코드가 말한다. 모델은 부재를 회피 서술한다
# (2026-08-31 실측 m5: 임대료 질문에 임대료 언급 0, q03: 배당 데이터 없이 배당주 나열,
# s4: 확률 요구에 일반론 1,800자).
_MARKET_UNSUPPORTED_NOTICES = (
    # 예산 질문(2026-09-08 QA P01·P02·P08) — "1억으로 되나"에 답이 없이 끝났다. 판정 불가를 먼저 말하고
    # 다음 행동(어디서 확인할지)을 준다. 창업비용 축은 GAME_SUNSET 계획 C1(공정위 정보공개서)에서 채운다.
    (re.compile(r"임대료|월세|보증금|권리금"),
     "임대료·보증금·권리금 데이터는 제공하지 않아요(공공데이터에 없어요)."
     " 아래는 매출·점포·유동인구 등 보유 데이터 기준이에요."),
    (re.compile(r"정확한?\s*매출|실제\s*매출"),
     "매출 수치는 카드사 기반 추정 집계예요 — 개별 점포의 실제 매출 데이터는 제공하지 않아요."),
)
_STOCK_UNSUPPORTED_NOTICES = (
    (re.compile(r"배당"),
     "배당수익률·배당 이력 데이터는 아직 제공하지 않아요. 아래는 가격·수급·가치 지표 기준이에요."),
    (re.compile(r"PER\s*(?:이|가)?\s*(?:낮은|높은)|저\s*PER|PER\s*비교"),
     "종목 간 PER 비교·스크리닝은 아직 지원하지 않아요 — 개별 종목의 밸류에이션 한 줄만 제공해요."),
    (re.compile(r"확률|몇\s*(?:퍼센트|%)"),
     "오르거나 내릴 확률은 단정해서 제시하지 않아요 — 과거 통계 참고치는 종목 예측 화면에서"
     " 표본·신뢰구간과 함께 볼 수 있어요."),
)


def _unsupported_notice(
    prompt: str, table: tuple[tuple[re.Pattern[str], str], ...],
) -> str:
    lines = [f"※ {msg}" for pattern, msg in table if pattern.search(prompt)]
    return "\n".join(lines) + "\n\n" if lines else ""


# 조건 질의 결정론 라우팅(I-14 확장, 2026-08-31 실측 m4) — "유동인구 많고 폐업률 낮은
# 상권 3곳"은 phase1(LLM)이 답할 수 없다: 후보 표에 판정 축이 없어 62초 뒤 422였다.
# 지역 미언급 + 조건 어휘면 랭킹 집계를 코드로 정렬해 답한다. 유동인구 축은 랭킹에
# 없으므로 정렬 근거로 쓰지 않고 없다고 고지한다(I-12와 같은 태도).
_CONDITION_AXES = (
    ("closure", re.compile(r"폐업\s*률?\s*(?:이|가|은|는|도)?\s*(?:낮|적)")),
    ("flow", re.compile(r"유동\s*인구\s*(?:가|는|도)?\s*많")),
    ("sales", re.compile(r"매출\s*(?:이|가|은|는|도)?\s*(?:높|많|큰|잘)")),
)
_CONDITION_COUNT = re.compile(r"(\d+)\s*(?:곳|군데|개)")
_CONDITION_DEFAULT_COUNT = 3
_CONDITION_MAX_COUNT = 10
# 점포 극단값 컷 — 점포 1~2개 상권은 폐업률 0%가 흔하다(랭킹 쇼케이스 하한과 같은 취지)
_CONDITION_MIN_STORES = 10


def _parse_llm_json(raw: str) -> dict:
    raw = raw.strip()
    # 마크다운 코드펜스 제거
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    text = match.group() if match else raw
    # 후행 콤마 제거(소형 모델 빈발 오류)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


class ChatInteractor(ChatUseCase):

    def __init__(
        self,
        market: CommercialDataPort,
        recorder: RecommendationRecordPort,
        conversations: ConversationRepository,
        stocks: StockAnalysisPort,
        news: NewsSearchPort,
        market_news: MarketNewsSearchPort,
        gemini: GeminiAnswerPort,
        forecaster: StockForecastPort | None = None,
        fundamentals: FundamentalReadPort | None = None,
        profiles: UserProfilePort | None = None,
        refit: ForecastRefitPort | None = None,
        signals: StockSignalBoardPort | None = None,
        paper: PaperDecisionPort | None = None,
    ) -> None:
        self._paper = paper
        self._market = market
        self._recorder = recorder
        self._conversations = conversations
        self._stocks = stocks
        self._news = news
        self._market_news = market_news
        self._gemini = gemini
        self._forecaster = forecaster
        self._fundamentals = fundamentals
        self._profiles = profiles
        self._refit = refit
        self._signals = signals

    def _history_block(self, history: list[Message]) -> str:
        if not history:
            return ""
        turns = "\n".join(f"{m.role}: {m.content[:200]}" for m in history[-6:])
        return f"이전 대화(맥락 참고용):\n{turns}\n\n"

    @staticmethod
    def _place_stem(name: str) -> str:
        """지명 어간 — 선행 한글 구간에서 행정 접미(구·동·가·로 등)를 뗀다 (예: 성수1가1동 → 성수).

        선행 한글이 1자로 퇴화하면 숫자를 걷어내고 다시 딴다 — "목1동"의 선행 한글은
        "목"이라 2자 미만 필터에서 탈락했다(2026-08-31 실측 p06: 목동 반찬가게 질문 422).
        """
        match = re.match(r"^[가-힣]+", name or "")
        stem = match.group() if match else ""
        if len(stem) < 2:
            match = re.match(r"^[가-힣]+", re.sub(r"\d+", "", name or ""))
            stem = match.group() if match else ""
        while len(stem) > 2 and stem[-1] in "구동가로읍면리":
            stem = stem[:-1]
        return stem

    def _area_mentioned_in(self, area: AreaInfo, text: str) -> bool:
        # 괄호 별칭("발산역(마곡)"의 '마곡')도 지명이다 — 어간은 선행 한글만 보므로 별칭을
        # 따로 후보에 넣는다(I-11 골든 재완주 MR20 실측: 마곡 질문이 강남으로 튀었다).
        aliases = re.findall(r"\(([가-힣]+)\)", area.trdar_name or "")
        for name in (area.district_name, area.adm_dong_name, area.trdar_name, *aliases):
            stem = self._place_stem(name)
            # "건대입구역"은 "건대입구 쪽"과 어긋난다(첫 재측정 실측) — '역'을 뗀
            # 변형도 본다. 단 뗀 결과가 3자 이상일 때만: "서울역→서울"처럼 흔한
            # 지명이 되면 서울이 들어간 모든 질문에 걸린다.
            variants = {stem}
            if stem.endswith("역") and len(stem) >= 4:
                variants.add(stem[:-1])
            if any(
                len(v) >= 2 and v in text and _stem_means_place(v, text)
                for v in variants
            ):
                return True
        return False

    def _mentioned_codes(self, summary: AreaSummary, prompt: str) -> set[int]:
        """질문에 지역(자치구·행정동·상권명 어간)이 언급된 상권 코드 집합."""
        return {
            a.trdar_code for a in summary.areas if self._area_mentioned_in(a, prompt)
        }

    def _excluded_area_codes(self, summary: AreaSummary, prompt: str) -> set[int]:
        """제외 어휘 바로 앞에 언급된 지역의 상권 집합 — "홍대 말고 다른 데"(4차 실측
        M2 t4: 홍대 계열을 다시 추천했다). 어간 매칭은 언급 판정과 같은 규칙을 쓴다."""
        heads = [
            prompt[max(0, m.start() - 10):m.start()]
            for m in re.finditer(r"말고|빼고|제외", prompt)
        ]
        if not heads:
            return set()
        # 제외 어휘 바로 앞 어절("홍대")은 상권명("홍대입구역")의 어간보다 짧은 통칭일 수
        # 있다 — 역방향 포함(어절 ⊂ 상권명)도 본다. 위치가 '말고' 직전이라 지명일 개연이
        # 높아 동음이의 가드는 걸지 않는다.
        last_words = [
            tokens[-1] for head in heads
            if (tokens := re.findall(r"[가-힣]{2,}", head))
        ]
        codes: set[int] = set()
        for a in summary.areas:
            if any(self._area_mentioned_in(a, head) for head in heads):
                codes.add(a.trdar_code)
                continue
            names = (a.district_name, a.adm_dong_name, a.trdar_name)
            if any(w in name for w in last_words for name in names):
                codes.add(a.trdar_code)
        return codes

    @staticmethod
    def _parse_radius_m(prompt: str) -> int | None:
        """질문의 반경 제약(m) — 거리+단위 표현이 없으면 None.

        50m 미만·20km 초과는 상권 반경 질의로 보지 않는다(도로 폭·행정 단위 오탐 차단).
        """
        match = _RADIUS_PATTERN.search(prompt)
        if not match:
            return None
        value = float(match.group(1))
        if match.group(2) in ("km", "㎞", "킬로미터", "킬로"):
            value *= 1000
        meters = int(round(value))
        return meters if 50 <= meters <= 20_000 else None

    @staticmethod
    def _radius_center(summary: AreaSummary, prompt: str) -> AreaInfo | None:
        """반경 질의의 중심 상권 — 상권명 낱말이 질문에 그대로 있는 가장 긴 매칭.

        자치구·행정동 어간 매칭(_mentioned_codes)은 중심 '점'이 못 된다("강남" → 강남구
        104곳). 상권명 낱말(예: "성수역")이 질문에 있을 때만 중심으로 삼고, 없으면 None —
        호출부가 "반경 미적용"을 명시한다(틀린 중심으로 자신 있게 답하는 것보다 낫다).
        """
        best: tuple[int, int, AreaInfo] | None = None  # (낱말 길이, 매출, 상권)
        for a in summary.areas:
            if a.x_coord is None or a.y_coord is None:
                continue
            for word in re.findall(r"[가-힣]{2,}", a.trdar_name):
                if word in _RADIUS_NAME_STOPWORDS:
                    continue
                # "건대입구역" 낱말은 "건대입구"로도 본다(_mentioned_codes와 같은 논리)
                variants = {word}
                if word.endswith("역") and len(word) >= 4:
                    variants.add(word[:-1])
                hit = max((len(v) for v in variants if v in prompt), default=0)
                if hit == 0:
                    continue
                sales = summary.sales_by_code.get(a.trdar_code) or 0
                if best is None or (hit, sales) > (best[0], best[1]):
                    best = (hit, sales, a)
        return best[2] if best else None

    @staticmethod
    def _within_radius(center: AreaInfo, area: AreaInfo, radius_m: int) -> bool:
        """좌표(EPSG:5174 TM, m)가 있는 상권만 중심과의 유클리드 거리로 판정한다."""
        if area.x_coord is None or area.y_coord is None:
            return False
        dx = area.x_coord - center.x_coord
        dy = area.y_coord - center.y_coord
        return dx * dx + dy * dy <= radius_m * radius_m

    @staticmethod
    def _previous_area_codes(
        history: list[Message], area_map: dict[int, AreaInfo]
    ) -> list[int]:
        """직전 상권 추천 카드(payload)에서 상권 코드를 복원한다.

        지역명 없는 후속 질문("카페 창업을 한다면?")의 맥락 승계용 — phase1 LLM이
        이전 대화에서 상권을 이어받지 못해 후보가 비는 경우를 결정론적으로 보정한다.
        """
        for m in reversed(history):
            payload = m.payload or {}
            recs = payload.get("recommendations")
            if recs:
                codes = [int(r["id"]) for r in recs if str(r.get("id", "")).isdigit()]
            else:
                # 조건 질의 랭킹 응답의 후속 앵커(P3) — 카드 없이 코드만 남긴다
                codes = [c for c in payload.get("rankingCodes") or [] if isinstance(c, int)]
            valid = [c for c in codes if c in area_map]
            if valid:
                return valid
        return []

    @staticmethod
    def _inherit_intent(prompt: str, history: list[Message]) -> tuple[str, list[str]] | None:
        """general 판정 후속 질문을 직전 카드의 도메인으로 되돌린다 — 조건 미충족이면 None."""
        if not (_has_deixis(prompt) or _DOMAIN_FOLLOWUP_RE.search(prompt)):
            return None
        for m in reversed(history):
            payload = m.payload or {}
            if payload.get("recommendations") or payload.get("rankingCodes"):
                return "market", []
            card = payload.get("stock")
            if card and card.get("symbol"):
                return "stock", [str(card["symbol"])]
        return None

    @staticmethod
    def _market_verdict_line(code: int, area_map: dict, real_stats: dict, service_name: str, area_scores: dict) -> str:
        """1순위 상권 결론 한 줄 — 데이터 있는 축만 잇는다('데이터 없음'은 쓰지 않는다)."""
        area = area_map.get(code)
        if area is None:
            return ""
        st = real_stats.get(code, {})
        parts = []
        if st.get("small_sample"):
            # 점포 5개 미만은 점포당 매출·폐업률이 튄다 — 결론 근거로 쓰지 않고 표본 사실만 적는다
            parts.append(st.get("store_count_text", "점포 수 적음") + "(표본 작음)")
        else:
            if st.get("revenue_text") and "없음" not in st["revenue_text"]:
                parts.append(st["revenue_text"])
            if st.get("closure_text") and "없음" not in st["closure_text"]:
                parts.append(st["closure_text"])
        score = area_scores.get(code)
        if score is not None and getattr(score, "grade", None):
            parts.append(f"상권 건강 {score.total:.0f}점 '{score.grade}'")
        basis = f" — {' · '.join(parts)}" if parts else ""
        return f"**결론** {service_name} 기준으로는 {area.trdar_name}부터 보세요{basis}."

    @staticmethod
    def _superlative_pick(prompt: str, codes: list[int], raw_stats: dict, area_map: dict) -> tuple[int, str] | None:
        """'제일 안전한/매출 높은' 질문의 결론을 코드가 정한다 — 후보 2곳 이상·지표 보유 시에만."""
        axis = next((a for a, rx in _SUPERLATIVE_AXES if rx.search(prompt)), None)
        if axis is None or len(codes) < 2:
            return None
        rows = []
        for c in codes:
            r = raw_stats.get(c)
            if r is None or c not in area_map:
                continue
            if r.has_store and r.store_count is not None and 0 < r.store_count < SMALL_SAMPLE_STORES:
                continue  # 점포 5개 미만 — 폐업률 0%(0개)·점포당 매출이 표본 때문에 튄다
            if axis == "closure" and r.has_store and r.closure_rate is not None:
                rows.append((c, float(r.closure_rate)))
            elif axis == "sales" and r.has_sales and r.monthly_sales_amount and (r.store_count or 0) > 0:
                rows.append((c, r.monthly_sales_amount / r.store_count / 10000))
        if len(rows) < 2:
            return None
        rows.sort(key=lambda x: x[1] if axis == "closure" else -x[1])
        best = rows[0][0]
        if axis == "closure":
            listing = " · ".join(f"{area_map[c].trdar_name} {v:g}%" for c, v in rows)
            ties = [c for c, v in rows if v == rows[0][1]]
            who = "·".join(area_map[c].trdar_name for c in ties)
            line = f"분기 폐업률 기준({listing}) — 가장 낮은 곳은 {who}입니다."
        else:
            listing = " · ".join(f"{area_map[c].trdar_name} {round(v):,}만원" for c, v in rows)
            line = f"점포당 월매출 기준({listing}) — 가장 높은 곳은 {area_map[best].trdar_name}입니다."
        return best, line

    async def _budget_notice(self, prompt: str, profile: UserProfileSummary | None) -> str:
        """예산 질문의 첫 문단 — 공정위 창업비용이 있으면 예산 안 업종을 나열, 없으면 판정 불가+다음 행동.

        2026-09-08 QA P01·P02·P08: "1억으로 되나"에 답 없이 끝났다. 창업비용은 가맹 기준 평균이라
        임대료·인테리어를 뺀 금액이고, 예산의 70%(가정치)까지만 창업비용으로 잡는다.
        """
        asked = bool(re.search(r"예산|자본금|자금으로|돈으로", prompt)) or parse_budget_krw(prompt) is not None
        if not asked:
            return ""
        budget = parse_budget_krw(prompt)
        if budget is None and profile is not None:
            budget = parse_budget_krw(profile.budget_label.replace("~", " ").split()[-1]) if profile.budget_label else None
        try:
            costs = await self._market.get_startup_costs()
        except Exception:
            logger.warning("[chat] 창업비용 조회 실패", exc_info=True)
            costs = []
        if not costs:
            return ("※ 예산에 맞는 자리인지는 판정하지 않았어요 — 창업비용·임대료·권리금 데이터가 없어요."
                    " 아래 점포당 월매출을 보증금·임대료 시세(부동산 중개 사이트)와 함께 보시면 감이 잡혀요.\n\n")
        year = costs[0].year
        by_name = {c.industry_name: c for c in costs}
        asked_names = []
        for word, name in _INDUSTRY_ALIASES:
            if word in prompt and name in by_name and name not in asked_names:
                asked_names.append(name)
        note = "가맹금·교육비·보증금·기타 합계(브랜드 중앙값)이고 점포 임대료·인테리어는 별도라 실제 총액은 이보다 커요."
        if budget is None:
            if asked_names:
                c = by_name[asked_names[0]]
                return (f"※ {c.industry_name} 업종 평균 창업비용은 공정위 정보공개서({year}) 기준 {fmt_won(c.total_amount)}이에요"
                        f" — {note} 예산을 말씀해 주시면 맞는지 봐 드려요.\n\n")
            cheapest = ", ".join(f"{c.industry_name} {fmt_won(c.total_amount)}" for c in costs[:5])
            return (f"※ 공정위 정보공개서({year}) 업종별 평균 창업비용은 낮은 순으로 {cheapest} 등이에요 — {note}"
                    " 예산을 말씀해 주시면 그 안에 드는 업종을 골라 드려요.\n\n")
        cap = budget * BUDGET_RESERVE_RATIO
        lead = ""
        for name in asked_names[:1]:
            c = by_name[name]
            verdict = "들어와요" if c.total_amount <= cap else "빠듯해요(넘어요)"
            lead = (f"{c.industry_name} 업종 평균 창업비용 {fmt_won(c.total_amount)}은(는) 예산 {fmt_won(budget)}의 70%"
                    f"({fmt_won(cap)}) 안에 {verdict}. ")
        fit = [c for c in costs if c.total_amount <= cap and c.industry_name not in asked_names[:1]]
        listing = ", ".join(f"{c.industry_name} {fmt_won(c.total_amount)}" for c in fit[:6])
        more = f" 외 {len(fit) - 6}개" if len(fit) > 6 else ""
        if not fit and not lead:
            floor = costs[0]
            return (f"※ 예산 {fmt_won(budget)}의 70%({fmt_won(cap)}) 안에 드는 가맹 업종이 공정위 정보공개서({year}) 기준으로는"
                    f" 없어요 — 가장 낮은 {floor.industry_name}도 {fmt_won(floor.total_amount)}이에요. 개인 창업(비가맹)은 이 표에 없고,"
                    " 임대료·인테리어는 별도예요.\n\n")
        others = f" 같은 예산에 드는 다른 업종: {listing}{more}." if fit else ""
        return f"※ {lead}{others} 공정위 정보공개서({year}) 기준이며 {note}\n\n"

    async def _answer_service_candidates(self, conversation_id: int, history: list[Message], on_stage=None) -> AskResponse | None:
        """직전 추천 상권 1곳의 업종별 점포당 월매출·폐업률을 코드가 나열한다. 직전 카드가 없으면 None(기존 흐름)."""
        previous = None
        for m in reversed(history):
            recs = (m.payload or {}).get("recommendations")
            if recs:
                previous = recs[0]
                break
        if not previous or not str(previous.get("id", "")).isdigit():
            return None
        self._notify(on_stage, "data", "상권의 업종별 수치를 모으고 있어요")
        code, name = int(previous["id"]), previous.get("name", "이 상권")
        summary = await self._market.get_area_summary()
        quarter = summary.latest_quarter
        if not quarter:
            return None
        services = [sv for sv in await self._market.get_service_codes() if any(k in sv.name for k in _SERVICE_SHORTLIST)][:14]
        rows = []
        for sv in services:
            raw = (await self._market.get_area_raw_stats([code], sv.code, quarter)).get(code)
            if raw is None or not raw.has_sales or not raw.monthly_sales_amount or not (raw.store_count or 0) > 0:
                continue
            per_store = round(raw.monthly_sales_amount / raw.store_count / 10000)
            closure = f"{raw.closure_rate:g}%" if raw.has_store and raw.closure_rate is not None else "폐업률 미집계"
            rows.append((sv.name, per_store, closure, raw.store_count))
        if not rows:
            return None
        rows.sort(key=lambda r: -r[1])
        lines = [f"{i}. {n} — 점포당 월매출 {v:,}만원 · 폐업률 {c} · {cnt}개 점포" for i, (n, v, c, cnt) in enumerate(rows[:8], 1)]
        text = (
            f"{name}에서 업종별로 보면(최신 분기, 점포당 월매출 순):\n" + "\n".join(lines) +
            "\n\n창업비용·임대료 데이터가 없어 예산에 맞는지는 판정하지 않았어요 — 업종을 하나 정해"
            ' "성수역에 카페 어때?"처럼 물으면 그 업종 기준으로 상권을 다시 비교해 드려요.'
        )
        await self._conversations.add_message(conversation_id, "assistant", text)
        return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

    async def _answer_paper(self, conversation_id: int, on_stage=None) -> AskResponse:
        """AI 모의투자 기록 — 허브 PaperDecisionPort를 코드가 읽어 '어느 계정이 무엇을 샀다'까지만 말한다."""
        self._notify(on_stage, "data", "AI 모의투자 기록을 읽고 있어요")
        try:
            infos = await self._paper.latest(["exaone", "signal"])
        except Exception:
            logger.warning("[chat] 모의투자 기록 조회 실패", exc_info=True)
            infos = []
        act = {"BUY": "매수", "SELL": "매도", "SHORT": "숏 진입", "COVER": "숏 청산"}
        label = {"exaone": "EXAONE 계정(AI가 직접 판단)", "signal": "지표 규칙 계정(검증된 신호만 따름)"}
        lines = []
        for info in infos:
            orders = ", ".join(f"{act.get(o.action, o.action)} {o.ticker}" for o in info.orders) or "주문 없음(관망)"
            filled = ", ".join(info.filled_tickers) if info.filled_tickers else "아직 없음(다음 장 시가 체결)"
            ret = f"{info.return_pct * 100:+.1f}%" if info.return_pct is not None else "—"
            lines.append(f"- {label.get(info.account, info.account)} — {info.as_of:%m/%d} 판단: {orders} · 체결: {filled} · 자산 {ret}")
            if info.account == "exaone" and info.orders:
                o = info.orders[0]
                lines.append(f"  · {o.ticker} 이유: {o.reason[:120]}")
        if not lines:
            text = ("AI 모의투자 기록이 아직 없어요. EXAONE 계정은 매일 14:00 판단하고 다음 장 시가에 사후 체결돼요 —"
                    " AI 모의투자 화면(/paper)에서 볼 수 있어요.")
        else:
            text = (
                "AI 모의투자는 실제 돈이 아닌 기록이에요 — EXAONE이 매일 우리 예측 스냅샷·뉴스 라벨을 읽고 1억원으로"
                " 판단한 것을 다음 장 시가에 사후 체결합니다.\n" + "\n".join(lines) +
                "\n\n어느 계정이 무엇을 샀다는 사실이지 매수·매도 권유가 아니에요. 판단 근거·인용 기사·거부된 주문은"
                " AI 모의투자 화면(/paper)에서 볼 수 있어요."
            )
        await self._conversations.add_message(conversation_id, "assistant", text)
        return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

    @staticmethod
    def _previous_service(history: list[Message]) -> tuple[str, str] | None:
        """직전 추천 카드에서 (업종 코드, 업종명)을 복원한다 — 업종 승계(P2)용."""
        for m in reversed(history):
            recs = (m.payload or {}).get("recommendations")
            if recs:
                code, name = recs[0].get("serviceCode"), recs[0].get("category")
                if code and name:
                    return str(code), str(name)
        return None

    def _build_area_context(
        self, summary: AreaSummary, prompt: str = "", limit: int = 80,
        ranking: dict[int, AreaRankingInfo] | None = None, safety_first: bool = False,
    ) -> str:
        # 상권 1650개 전체를 넣으면 모델 컨텍스트를 초과한다.
        # 행 상한은 80을 유지한다(I-11 골든 재완주 실측): 60으로 줄이자 어간 가드가 못 잡는
        # 지명("발산역(마곡)"의 '마곡')을 phase1이 표에서 읽어 고르던 경로가 끊겨 MR20이
        # 강남으로 튀었다. 판정 축 2열을 더해도 prompt_eval은 창(8,192)에 여유가 있다.
        # 질문에 언급된 지역(자치구·행정동·상권명 어간)을 우선 포함하고,
        # 나머지는 월매출 상위로 상한까지 채운다. 언급 상권은 ★로 표시해 phase1 선택을 유도한다.
        def sales_of(a) -> int:
            return summary.sales_by_code.get(a.trdar_code) or 0

        all_mentioned = self._mentioned_codes(summary, prompt)
        ranking = ranking or {}
        if safety_first:
            # 안정형 프로파일(2026-09-08 QA P08) — 후보를 매출순이 아니라 폐업률 낮은 순으로 채운다.
            # 폐업률 미집계 상권은 뒤로(없는 값을 0으로 읽지 않는다).
            def safety_key(a):
                row = ranking.get(a.trdar_code)
                closure = row.closure_rate if row is not None and row.closure_rate is not None else None
                return (closure is None, closure if closure is not None else 0.0, -sales_of(a))
            ranked = sorted(summary.areas, key=safety_key)
        else:
            ranked = sorted(summary.areas, key=sales_of, reverse=True)
        picked = [a for a in ranked if a.trdar_code in all_mentioned][:limit]
        mentioned_codes = {a.trdar_code for a in picked}
        seen = set(mentioned_codes)
        for a in ranked:
            if len(picked) >= limit:
                break
            if a.trdar_code not in seen:
                picked.append(a)
                seen.add(a.trdar_code)

        # YoY 열(I-10) — "작년 대비" 질의를 표가 지원하지 않으면 모델이 근거 없이
        # "증가율이 높다"고 서술한다(실측). 산출 불가 상권은 '-'로 정직하게 남긴다.
        # 판정 축 2열(I-11) — 표에 없는 축을 물으면 모델이 근거 없이 "폐업률이 낮다"고
        # 서술했다(3차 실측 M1·M6). 랭킹 집계(전 업종)에서 잇고, 미집계는 '-'로 남긴다.
        lines = [
            ("[질문자는 안정 최우선 — 폐업률(%)이 낮은 상권을 먼저 고를 것. 표는 폐업률 낮은 순]\n" if safety_first else "")
            + "상권코드|상권명|자치구|행정동|상권전체월매출합계(만원)|매출전년동분기대비(%)"
            "|폐업률(%)|점포당월매출(만원)|질문지역"
        ]
        for a in picked:
            sales = summary.sales_by_code.get(a.trdar_code)
            wan = round(sales / 10000) if sales else None
            yoy = summary.yoy_by_code.get(a.trdar_code)
            row = ranking.get(a.trdar_code)
            closure = row.closure_rate if row is not None else None
            per_store = row.sales_per_store if row is not None else None
            lines.append(
                f"{a.trdar_code}|{a.trdar_name}|{a.district_name}|{a.adm_dong_name}"
                f"|{wan if wan is not None else '데이터없음'}"
                f"|{f'{yoy:+.1f}' if yoy is not None else '-'}"
                f"|{f'{closure:.1f}' if closure is not None else '-'}"
                f"|{round(per_store / 10000) if per_store else '-'}"
                f"|{'★' if a.trdar_code in mentioned_codes else ''}"
            )
        return "\n".join(lines)

    def _format_stats(
        self, raw_stats: dict[int, AreaRawStat], quarter: int, generic: bool = False,
    ) -> dict[int, AreaStatDto]:
        quarter_label = f"{str(quarter)[:4]}년 {str(quarter)[4]}분기"
        scope = "전 업종 합계" if generic else "업종"

        result: dict[int, AreaStatDto] = {}
        for code, raw in raw_stats.items():
            has_data = raw.has_sales or raw.has_store or raw.has_fp

            # monthly_sales_amount는 market 경계에서 분기÷3으로 환산된 값이다(sales_unit).
            # 2026-09-08 감사: "수서역 분식 점포당 월평균 18,544만원"은 분기 합계를 월로 표기한 3배 과장 +
            # 점포 2개 분모였다. 점포 5개 미만은 표본이 작다고 적고 결론·1순위에서 뺀다.
            small_sample = bool(raw.has_store and raw.store_count is not None and 0 < raw.store_count < SMALL_SAMPLE_STORES)
            if raw.has_sales and raw.has_store and raw.store_count and raw.store_count > 0:
                sales_wan = round(raw.monthly_sales_amount / 10000)
                per_store_wan = round(sales_wan / raw.store_count)
                revenue_text = f"점포당 월평균 {per_store_wan:,}만원"
                if small_sample:
                    revenue_text += f" (점포 {raw.store_count}개 — 표본 작음, 참고만)"
                revenue_source = (f"{scope} 분기 매출 {sales_wan * 3 / 10000:.1f}억원 ÷ 3개월 ÷ {raw.store_count}개 점포"
                                  " (서울시 추정매출은 분기 합계)")
            elif raw.has_sales:
                sales_wan = round(raw.monthly_sales_amount / 10000)
                revenue_text = f"{scope} 월 매출 {sales_wan:,}만원 (점포수 미집계, 분기÷3 환산)"
                revenue_source = "점포당 매출 계산 불가 (점포수 데이터 없음)"
            else:
                # 축을 명시한다 — 이 값은 질문 업종 한정이라, 상권 전체 매출이 있는 상세
                # 페이지와 "없음/366억"으로 모순돼 보였다(2026-08-31 프로덕션 실측).
                revenue_text = "이 업종 매출 데이터 없음"
                revenue_source = "해당 분기 이 업종 매출 미수집 — 상권 전체 매출과는 별개"

            weekday_text = "데이터 없음"
            if raw.has_sales and raw.monthly_sales_amount and raw.weekday_sales_amount:
                wd = round(raw.weekday_sales_amount / raw.monthly_sales_amount * 100)
                weekday_text = f"주중 {wd}% / 주말 {100 - wd}%"

            store_count_text = f"{raw.store_count}개 점포 영업 중" if raw.has_store else "점포 데이터 없음"
            # 율만 주면 소규모 상권에서 오독한다("3개 중 1개 폐업 = 33%") — 절대 건수를 병기한다.
            closure_text = (
                f"분기 폐업률 {raw.closure_rate}%({raw.closure_store_count}개)"
                if raw.has_store and raw.closure_store_count is not None
                else f"분기 폐업률 {raw.closure_rate}%" if raw.has_store else "데이터 없음"
            )
            opening_text = (
                f"분기 개업률 {raw.opening_rate}%({raw.opening_store_count}개)"
                if raw.has_store and raw.opening_store_count is not None
                else f"분기 개업률 {raw.opening_rate}%" if raw.has_store else "데이터 없음"
            )
            # 경쟁 강도 — 같은 업종 점포가 몇 개인가. 창업 판단에 직결된다.
            rival_text = (
                f"동일 업종 {raw.similar_industry_store_count}개 경쟁"
                if raw.similar_industry_store_count is not None else "데이터 없음"
            )

            if raw.has_store and raw.store_count and raw.store_count > 0:
                fr = round(raw.franchise_store_count / raw.store_count * 100)
                franchise_text = f"프랜차이즈 {raw.franchise_store_count}개 ({fr}%)"
            else:
                franchise_text = "데이터 없음"

            if raw.has_fp:
                daily = round(raw.total_floating_pop / 91)
                foot_text = f"일평균 {daily:,}명 (분기 총 {raw.total_floating_pop:,}명 ÷ 91일)"
                top_age = _top_field(raw, AGE_FIELDS)
                peak_time = _top_time_field(raw, TIME_FIELDS)
            else:
                foot_text = "유동인구 데이터 없음"
                top_age = "데이터 없음"
                peak_time = "데이터 없음"

            if raw.has_cc:
                change_text = raw.change_indicator_name or "데이터 없음"
                op_months = raw.operating_months_avg
                region_op = raw.region_operating_months_avg
                # 지역 평균 결측 시 괄호를 생략한다 — "None개월"이 그대로 노출됐다(2026-08-31 실측).
                op_text = "데이터 없음"
                if op_months:
                    op_text = f"이 상권 평균 {op_months}개월 영업"
                    if region_op:
                        op_text += f" (지역 평균 {region_op}개월)"
                # 생존 중 점포의 영업개월만으론 "얼마 만에 닫는가"를 알 수 없다.
                if raw.closure_months_avg:
                    op_text += f", 폐업 점포는 평균 {raw.closure_months_avg}개월 만에 닫음"
                    if raw.region_closure_months_avg:
                        op_text += f" (지역 평균 {raw.region_closure_months_avg}개월)"
            else:
                change_text = "데이터 없음"
                op_text = "데이터 없음"

            result[code] = {
                "revenue_text": revenue_text,
                "revenue_source": revenue_source,
                "small_sample": small_sample,
                "weekday_text": weekday_text,
                "store_count_text": store_count_text,
                "closure_text": closure_text,
                "opening_text": opening_text,
                "franchise_text": franchise_text,
                "rival_text": rival_text,
                "foot_text": foot_text,
                "top_age": top_age,
                "peak_time": peak_time,
                "change_text": change_text,
                "op_months_text": op_text,
                "quarter_label": quarter_label,
                "has_data": has_data,
            }

        return result

    @staticmethod
    def _notify(on_stage, stage: str, label: str) -> None:
        """진행 단계 통지 — 통지 실패가 답변 자체를 깨지 않게 삼킨다."""
        if on_stage is None:
            return
        try:
            on_stage(stage, label)
        except Exception:
            logger.warning("[chat] 진행 통지 실패: %s", stage, exc_info=True)

    async def ask(
        self, prompt: str, conversation_id: int | None = None, user_id: int | None = None,
        on_stage=None,
    ) -> AskResponse:
        if conversation_id is None:
            conversation_id = (await self._conversations.create_conversation(user_id=user_id)).id
        history = await self._conversations.get_messages(conversation_id)
        await self._conversations.add_message(conversation_id, "user", prompt)

        # 서비스 메타 질문(자기 시그널 검증치)은 LLM 진입 전에 결정론으로 답한다(1-2)
        if _is_service_meta(prompt):
            return await self._answer_service_meta(conversation_id)
        if _SURGE_PICK_RE.search(prompt):
            # 급등주 찍기(3차 실측 P5) — market_news로 낙하해 특정 종목을 '단기 투자
            # 기회'로 서술했다. 단기 급등 예측은 백테스트 우위가 없고 매매 지시 금지가
            # 원칙이므로 LLM 없이 결정론으로 거절·안내한다.
            text = (
                "특정 종목을 찍어드리지는 않아요 — 단기 급등 예측은 백테스트에서 우위가"
                " 확인되지 않았고, 매매 지시를 하지 않는 것이 이 서비스의 원칙이에요."
                " 대신 볼 수 있는 것: ① 오늘 상승·하락 신호가 뚜렷한 종목은 주식 화면의"
                " 신호 보드(또는 \"상승 신호 나온 종목 알려줘\"), ② EXAONE이 실제 데이터로 굴리는"
                " 모의투자 계정이 무엇을 샀는지는 AI 모의투자 화면(/paper) 또는 \"AI는 요즘 뭐 사?\","
                " ③ 궁금한 종목을 물으면 지표·과거 통계(표본·신뢰구간)로 현재 상태를 읽어드리고,"
                " 프로필의 가격 도달 알림으로 원하는 가격 통지를 받아보실 수 있어요."
            )
            await self._conversations.add_message(conversation_id, "assistant", text)
            return AskResponse(text=text, recommendations=[], conversationId=conversation_id)
        if _ALERT_HOWTO_RE.search(prompt):
            # 알림 사용법(4차 실측 S1 t5·S9 t5) — general(Gemini)이 "종 모양 아이콘",
            # "상권 권리금/임대료 변동 알림" 같은 없는 기능·UI를 지어냈다. 실기능 안내는
            # LLM에게 맡기지 않고 코드가 답한다.
            text = _ALERT_HOWTO_TEXT
            await self._conversations.add_message(conversation_id, "assistant", text)
            return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

        if self._paper is not None and _PAPER_RE.search(prompt):
            # AI 모의투자 기록 조회(2026-09-08 QA P06·P09) — "AI는 요즘 뭐 사?"에 정체성 답변을
            # 하고, "AI 모의투자가 뭐야?"에 "제공하지 않는 기능"이라 했다. 허브 기록을 코드가 읽는다.
            return await self._answer_paper(conversation_id, on_stage)
        if self._signals is not None and _SIGNAL_BOARD_RE.search(prompt):
            # 신호 보드 조회(4차 실측 S8 t4) — 워치리스트 신호를 코드가 읽어 답한다.
            return await self._answer_signal_board(conversation_id, prompt, on_stage)
        if _NEWS_DETAIL_RE.search(prompt):
            # 뉴스 상세 후속(3차 P8) — 직전 카드에 근거 뉴스가 있을 때만 가로챈다.
            detail = self._news_detail_text(history)
            if detail is not None:
                await self._conversations.add_message(conversation_id, "assistant", detail)
                return AskResponse(text=detail, recommendations=[], conversationId=conversation_id)

        if _SERVICE_FOCUS_RE.search(prompt):
            focus = await self._answer_service_candidates(conversation_id, history, on_stage)
            if focus is not None:
                return focus

        # phase0(의도 분류 = 도메인 판단) — 단일 모델(7.8B) 정책
        self._notify(on_stage, "intent", "질문 의도를 파악하고 있어요")
        intent, stock_queries = await self._classify_intent(prompt, history)
        # 프로파일은 데이터 근거 서술(stock·market)에만 주입한다 — 미작성·실패는 None(무손상)
        profile = await self._load_profile(user_id) if intent in ("stock", "market") else None
        if intent == "stock":
            return await self._answer_stock(conversation_id, prompt, stock_queries, on_stage, profile)
        if intent == "market_news":
            return await self._answer_market_news(conversation_id, prompt, on_stage)
        if intent == "general":
            self._notify(on_stage, "answer", "답변을 만들고 있어요")
            return await self._answer_general(conversation_id, prompt)

        summary = await self._market.get_area_summary()
        quarter = summary.latest_quarter
        if not quarter:
            raise CommercialDataUnavailableError("상권 데이터가 없습니다.")

        # 방법론·개념 질문 결정론 응답(P4-9) — 지역 언급이 없으면 추천이 아니라 설명이
        # 답이다. 지역이 함께 언급되면 기존 흐름(I-20 wants_detail 주입) 유지.
        if _METHOD_QUERY_RE.search(prompt) and not self._mentioned_codes(summary, prompt):
            await self._conversations.add_message(conversation_id, "assistant", _METHOD_QUERY_TEXT)
            return AskResponse(
                text=_METHOD_QUERY_TEXT, recommendations=[], conversationId=conversation_id,
            )

        # 서울 외 지역 가드 — 데이터가 서울뿐이라 phase1이 서울 상권을 임의로
        # 고르는 오답을 코드로 차단한다. 서울 지명이 함께 언급되면 기존 흐름(서울 분석) 유지.
        if not self._mentioned_codes(summary, prompt):
            region = next((r for r in NON_SEOUL_REGIONS if r in prompt), None)
            if region:
                text = (
                    f"{NONSEOUL_GUARD_PREFIX} {region} 등 다른 지역은 "
                    "아직 준비 중이라 조금만 기다려 주세요. 서울에서 궁금한 동네(예: 성수동, "
                    "홍대)를 말씀해 주시면 바로 분석해 드릴게요."
                )
                await self._conversations.add_message(conversation_id, "assistant", text)
                return AskResponse(
                    text=text, recommendations=[], conversationId=conversation_id,
                )
            # 조건 질의 결정론 라우팅 — 지역 미언급 + 조건 어휘면 LLM 없이 랭킹으로 답한다
            axes = [key for key, pattern in _CONDITION_AXES if pattern.search(prompt)]
            if axes:
                return await self._answer_condition_ranking(
                    conversation_id, prompt, axes, on_stage,
                )

        # 반경 질의 가드(I-10) — 중심 상권을 좌표로 특정할 수 있으면 반경 안 상권 집합을
        # 만들어 phase1 결과를 자르고, 못 하면 "미적용"을 답변 문두에 결정론으로 명시한다.
        radius_m = self._parse_radius_m(prompt)
        radius_codes: set[int] | None = None
        radius_note = ""
        if radius_m is not None:
            center = self._radius_center(summary, prompt)
            if center is None:
                radius_note = (
                    # '추천' 어휘를 쓰지 않는다 — 등급 가드(suppress_recommendation) 치환
                    # 뒤에 붙는 결정론 고지가 추천 어휘를 재삽입하면 채점기 grade_caution에
                    # 걸린다(골든 재완주 MR21 실측).
                    f"※ 반경 {radius_m:,}m 조건은 기준 지점을 좌표로 특정하지 못해 적용하지"
                    " 못했어요. 아래 결과는 지역명 기준이에요.\n\n"
                )
            else:
                radius_codes = {
                    a.trdar_code for a in summary.areas
                    if self._within_radius(center, a, radius_m)
                }
                radius_note = (
                    f"※ '{center.trdar_name}' 중심 반경 {radius_m:,}m 안의 상권"
                    f" {len(radius_codes)}곳으로 후보를 제한했어요.\n\n"
                )

        area_map = {a.trdar_code: a for a in summary.areas}
        # 판정 축(I-11) — 조회 실패는 열 전체 '-'로 열화(표 자체는 유지).
        try:
            ranking = {r.trdar_code: r for r in await self._market.get_area_ranking()}
        except Exception:
            logger.warning("[chat] 랭킹 집계 조회 실패 — phase1 판정 축 생략", exc_info=True)
            ranking = {}
        safety_first = profile is not None and profile.risk_label in ("안정형", "안정추구형")
        area_context = self._build_area_context(summary, prompt, ranking=ranking, safety_first=safety_first)

        service_codes = await self._market.get_service_codes()
        service_code_list = "\n".join(f"{sc.code}|{sc.name}" for sc in service_codes)

        phase1_contents = (
            f"{self._history_block(history)}"
            f"사용자 질문: {prompt}\n\n"
            f"업종 코드 목록:\n{service_code_list}\n\n"
            f"서울 상권 데이터:\n{area_context}"
        )
        # phase1(상권/업종 선택 = 도메인 판단) — 단일 모델(7.8B) 정책
        self._notify(on_stage, "select", "후보 상권을 고르고 있어요")
        try:
            p1 = await self._orchestrate_json(
                f"{PHASE1_PROMPT}\n\n{phase1_contents}", "Phase1",
            )
        except Exception:
            logger.error("[chat] Phase1 파싱 실패(재시도 포함)")
            raise InvalidLLMResponseError("AI 응답 파싱 실패")

        service_code: str = p1.get("service_code", "")
        service_name: str = p1.get("service_name", "")
        # 업종 결정론 가드 — 사용자가 말한 업종("떡볶이집")은 phase1 오선택·승계보다
        # 항상 이긴다. 감지가 없을 때만 승계(P2)를 보되, 정정 신호("~라고 했는데")가
        # 있으면 승계하지 않는다(오선택 고착 방지 — 2026-09-01 실측 3턴 표류).
        detected = _detect_service(prompt, service_codes)
        if detected is not None:
            service_code, service_name = detected
        else:
            prev_service = self._previous_service(history)
            if (prev_service and not _service_hinted(prompt, service_name)
                    and not _has_correction(prompt)):
                service_code, service_name = prev_service
        trdar_codes: list[int] = [int(c) for c in p1.get("trdar_codes", []) if str(c).isdigit()]
        valid_codes = [c for c in trdar_codes if c in area_map]

        # 결정론적 지역 가드 — 질문에 지역이 언급되면 그 지역 상권으로 보정.
        # 모델이 ★ 지시를 무시하고 유명 상권(홍대 등)으로 쏠리는 경우를 코드로 방지한다.
        # 제외 지역(P4-8 "홍대 말고")은 언급 집합에서 빼고, 아래에서 후보에서도 걸러낸다.
        excluded_codes = self._excluded_area_codes(summary, prompt)
        mentioned_codes = self._mentioned_codes(summary, prompt) - excluded_codes
        if mentioned_codes:
            local = [c for c in valid_codes if c in mentioned_codes]
            if local:
                valid_codes = local
            else:
                valid_codes = sorted(
                    mentioned_codes,
                    key=lambda c: summary.sales_by_code.get(c) or 0, reverse=True,
                )[:3]
        else:
            previous = self._previous_area_codes(history, area_map)
            if previous and (
                _has_deixis(prompt)
                or not _has_exclusion(prompt)
                or _exclusion_targets_service(prompt, service_codes)
            ):
                # 직전 추천으로 후보를 **제한**한다. 지시어("그 중에서/거기")뿐 아니라
                # 지역 미언급 후속 전반으로 확대(3차 실측 P2): "경쟁 몇 개야?"·"포화
                # 아니야?" 류에서 phase1이 전면 재선택해 동대문·홍대로 리셋됐다.
                # 제외 어휘("말고/빼고")가 있으면 제한하지 않는다 — 정반대 답이 된다.
                # 단 업종을 겨눈 제외("국밥 말고 돈까스집")는 지역 맥락을 유지한다(P4-4).
                kept = [c for c in valid_codes if c in previous]
                valid_codes = kept or previous
            elif not valid_codes:
                # 지역 미언급 후속 질문 — 직전 추천 상권을 이어받아 맥락을 유지한다.
                # (phase1 LLM이 이전 대화에서 상권을 못 이어받아 후보가 빈 경우만 보정)
                valid_codes = previous
        if excluded_codes:
            valid_codes = [c for c in valid_codes if c not in excluded_codes]
            if not valid_codes:
                # 제외를 걸러 후보가 비면 매출 상위 비제외 상권으로 대체한다 —
                # "홍대 말고"에 매칭 실패 안내를 주는 것은 답이 아니다.
                valid_codes = [
                    c for c in sorted(
                        summary.sales_by_code,
                        key=lambda c: summary.sales_by_code.get(c) or 0, reverse=True,
                    )
                    if c in area_map and c not in excluded_codes
                ][:3]
        if radius_codes is not None:
            # 지역·지시어 가드를 거친 후보를 반경으로 자른다. 반경 안 후보가 하나도 없으면
            # 반경 안 매출 상위로 대체한다(중심 상권 자신이 항상 포함되므로 공집합이 아니다).
            kept = [c for c in valid_codes if c in radius_codes]
            valid_codes = kept or sorted(
                radius_codes, key=lambda c: summary.sales_by_code.get(c) or 0, reverse=True,
            )[:3]
        if not valid_codes:
            # 매칭 실패는 오류(422)가 아니라 안내 답변이다 — "목동 반찬가게"·"유동인구 많은
            # 상권 3곳" 질문이 62~86초 기다린 끝에 오류 원문을 받았다(2026-08-31 프로덕션).
            # 대화는 계속돼야 하므로 다음 질문 방법을 알려주고 정상 응답으로 돌려보낸다.
            text = (
                "질문에서 분석할 상권을 특정하지 못했어요. 동네·역·거리 이름을 함께 물어봐"
                ' 주세요 (예: "강남역 카페 어때?", "성수동 분식집 괜찮아?").'
                " 조건으로 찾고 싶다면 상권 지도의 랭킹에서 자치구·업종·변화 유형별로"
                " 정렬해 볼 수 있어요."
            )
            await self._conversations.add_message(conversation_id, "assistant", text)
            return AskResponse(text=text, recommendations=[], conversationId=conversation_id)
        # 분량 상한 — 가드를 **전부 통과한 뒤**에 자른다. 앞에서 자르면 지역·지시어·반경 가드가
        # 되돌리려던 상권이 이미 사라져 region_hit_rate가 깎인다.
        valid_codes = valid_codes[:MAX_AREAS]

        self._notify(on_stage, "data", "공공데이터를 분석하고 있어요")
        raw_stats = await self._market.get_area_raw_stats(valid_codes, service_code, quarter)
        real_stats = self._format_stats(raw_stats, quarter, generic=(service_code == GENERIC_SERVICE_CODE))
        # 업종 데이터 없는 상권은 뒤로(2026-09-08 QA P02·P03) — "치킨 순위"에 치킨 매출이 없는 곳이
        # 같은 비중으로 섞여 판단이 안 됐다. 데이터 있는 곳을 앞에 두고, 없는 곳은 참고용으로 고지한다.
        no_data_codes = [c for c in valid_codes if not (raw_stats.get(c) and raw_stats[c].has_sales)]

        def _tier(c: int) -> int:  # 0 정상 · 1 표본 작음(점포 5개 미만) · 2 업종 데이터 없음 — 안정 정렬
            if c in no_data_codes:
                return 2
            return 1 if real_stats.get(c, {}).get("small_sample") else 0

        if len({_tier(c) for c in valid_codes}) > 1:
            valid_codes = sorted(valid_codes, key=_tier)
        # 상대 비교 축(P10) — "제일 안전한 데"는 코드가 폐업률로 고른다. LLM은 그 결론을 받아 쓴다.
        superlative = self._superlative_pick(prompt, valid_codes, raw_stats, area_map)
        if superlative is not None:
            best_code, superlative_line = superlative
            valid_codes = [best_code] + [c for c in valid_codes if c != best_code]
        # M3 스코어링 근거 주입 — 시도 벤치마크 대비 종합점수(산출 불가 상권은 라인 생략)
        area_scores = await self._market.get_area_scores(valid_codes)
        # 상권 성격 해석 — 고객 프로필·배후 수요·소비·객단가. 지도 오버레이만 보던 문장을
        # 채팅에도 공급한다(근거 팩트 없는 상권은 키 자체가 없어 라인 생략).
        area_insights = await self._market.get_area_insights(valid_codes, service_code)
        # 인허가 업소 교체 — 분기 팩트가 답하는 "얼마나 있나"에 "지금 늘고 있나"를 더한다
        # (인허가가 붙은 업소가 없는 상권은 키가 없어 라인 생략).
        permit_churn = await self._market.get_area_permit_churn(valid_codes)
        # 상권 뉴스 RAG 근거 — 지역 기사 의미 검색(히트 없으면 블록 생략)
        area_articles = await self._market_news.search(prompt, limit=4)

        quarter_label = f"{str(quarter)[:4]}년 {str(quarter)[4]}분기"
        wants_detail = bool(_EXPERT_DETAIL_RE.search(prompt))
        stats_context_lines = [f"사용자 질문: {prompt}\n업종: {service_name}\n기준: {quarter_label}\n"]
        for code in valid_codes:
            area = area_map[code]
            st = real_stats.get(code, {})
            score = area_scores.get(code)
            score_line = f"- 서울 평균 대비: {self._score_text(score)}\n" if score else ""
            trend_line = self._trend_text(score) if wants_detail and score else ""
            insight_line = self._insight_text(area_insights.get(code))
            permit_line = self._permit_text(permit_churn.get(code))
            stats_context_lines.append(
                f"[{area.trdar_name} / {area.district_name}] (trdar_code: {code})\n"
                f"- 수익: {st.get('revenue_text')} | {st.get('revenue_source')}\n"
                f"- 매출패턴: {st.get('weekday_text')}\n"
                f"- 점포: {st.get('store_count_text')} | {st.get('closure_text')} | {st.get('opening_text')} | {st.get('franchise_text')} | {st.get('rival_text')}\n"
                f"- 유동인구: {st.get('foot_text')}\n"
                f"- 유동인구 최다 연령대: {st.get('top_age')} (통행량 기준 — 매출 기준 고객층이 아님)"
                f" | 유동인구 피크시간(시간당): {st.get('peak_time')}\n"
                f"- 상권변화: {st.get('change_text')} | {st.get('op_months_text')}\n"
                f"{score_line}{trend_line}{permit_line}{insight_line}"
            )
        if wants_detail:
            stats_context_lines.append(
                "[종합점수 산출 방식] 시도(서울) 벤치마크 대비 4개 컴포넌트 — 매출 성장·"
                "유동인구 성장(직전 분기 대비), 개폐업 건강도, 영업 지속성 — 를 0~100으로"
                " 환산해 종합. 50점 = 서울 평균 동률."
            )
        if area_articles:
            stats_context_lines.append(self._format_area_articles(area_articles))
        if profile is not None:
            stats_context_lines.append(self._profile_market_block(profile))
        if superlative is not None:
            stats_context_lines.append(
                f"[비교 결론 — 코드가 정함] {superlative_line} text의 첫 문장은 이 결론과 같아야 하고,"
                " 다른 상권을 더 권하려면 그 기준(매출·유동인구 등)을 수치와 함께 밝힐 것."
            )

        # phase2(최종 서술 = 최종 사용자 답변) → 오케스트레이터 기본 모델(7.8B)
        self._notify(on_stage, "narrate", "추천 이유를 정리하고 있어요")
        phase2_context = "\n".join(stats_context_lines)
        try:
            p2 = await self._orchestrate_json(f"{PHASE2_PROMPT}\n\n{phase2_context}", "Phase2")
        except Exception:
            logger.error("[chat] Phase2 파싱 실패(재시도 포함)")
            raise InvalidLLMResponseError("AI 서술 생성 실패")

        # 모델이 trdar_code를 문자열("3110131")로 되돌리는 일이 잦다 — int로 정규화하지
        # 않으면 조회가 전부 빗나가 reason이 빈 채 나간다(3차 실측: reason 69%가 빈 문자열).
        # reason 키 누락도 열화한다(4차 실측 M8 t1: 7.8B가 reason을 빼먹어 KeyError→500).
        # 빈 이유는 아래 _ensure_risk_note·폴백 서술이 채운다 — 500보다 얕은 답이 낫다.
        reason_map = {
            int(item["trdar_code"]): str(item.get("reason") or "")
            for item in p2.get("areas", [])
            if str(item.get("trdar_code", "")).isdigit()
        }
        # 값 재라벨 금지 가드(I-15 상권판, 2026-08-31 실측 m1) — 폐업률 데이터가 없는
        # 상권의 이유에 "폐업률"이 등장하면 문장째 걷어낸다(영업 기간 재라벨 차단).
        # 유의 문장이 지워지면 바로 아래 _ensure_risk_note가 데이터 기반 문장으로 다시 채운다.
        reason_map = {
            code: (
                answer_guard.strip_unsupported_metric(reason, "폐업률")
                if real_stats.get(code, {}).get("closure_text") == "데이터 없음"
                else reason
            )
            for code, reason in reason_map.items()
        }
        # 서술-숫자 근거 가드(2026-09-08 QA P02·P03) — 컨텍스트에 없는 숫자가 든 문장은 걷어낸다.
        # 걷힌 유의 문장은 바로 아래 _ensure_risk_note가 데이터 기반으로 다시 채운다.
        grounded = answer_guard.grounded_numbers(phase2_context) | answer_guard.grounded_numbers(prompt)
        reason_map = {
            code: answer_guard.strip_forecast_claims(answer_guard.strip_ungrounded_numbers(reason, grounded))
            for code, reason in reason_map.items()
        }
        # C2 리스크 의무의 결정론 보강 — 모델이 "유의할 점"을 빼먹으면(첫 재측정 준수율 31%)
        # 이미 컨텍스트에 주입된 수치를 재인용해 붙인다. 창작이 아니라 팩트의 재사용이다.
        reason_map = {
            code: self._ensure_risk_note(reason, real_stats.get(code, {}))
            for code, reason in reason_map.items()
        }
        # 이유 없는 추천은 내보내지 않는다 — 프롬프트로 "모든 상권 서술"을 의무화해도
        # 모델이 일부만 쓰는 일이 남는다(4차 실측: 빈 reason 33%). 서술된 상권만 남기되,
        # 전부 서술이 없으면 기존 추천을 유지해 답변 자체는 살린다(열화 동작).
        reasoned = [c for c in valid_codes if reason_map.get(c, "").strip()]
        if reasoned:
            valid_codes = reasoned
        text = answer_guard.strip_forecast_claims(
            answer_guard.strip_ungrounded_numbers(str(p2.get("text", "") or ""), grounded)
        )
        # 본문이 먼저 지목한 상권 = 카드 1번(2026-09-08 QA P01) — 본문은 카페거리, 카드 1번은 성수역이라
        # 어디를 믿을지 몰랐다. 비교 축이 있으면 그 결론이 우선이라 재정렬하지 않는다.
        if superlative is None and text:
            mention = {c: text.find(area_map[c].trdar_name) for c in valid_codes}
            first = min((c for c in valid_codes if mention[c] >= 0), key=lambda c: mention[c], default=None)
            if first is not None and valid_codes[0] != first:
                valid_codes = [first] + [c for c in valid_codes if c != first]

        # 등급 결정론 가드(2026-08-31 실측 p04) — '주의'/'위험' 상권은 모델이 무엇을 썼든
        # 추천 어휘를 차단하고, 등급 고지를 답변 첫 문단에 코드로 삽입한다(아래 text 조립).
        caution_codes = [
            code for code in valid_codes
            if (s := area_scores.get(code)) and s.grade in answer_guard.CAUTION_GRADES
        ]
        for code in caution_codes:
            if reason_map.get(code):
                reason_map[code] = answer_guard.suppress_recommendation(reason_map[code])

        recommendations: list[AreaRecommendation] = []
        for code in valid_codes:
            area = area_map[code]
            st = real_stats.get(code, {})
            recommendations.append(AreaRecommendation(
                id=str(code),
                name=area.trdar_name,
                lat=area.lat,
                lng=area.lng,
                category=service_name,
                serviceCode=service_code,
                reason=reason_map.get(code, ""),
                stats=AreaStats(
                    monthlyRevenueText=st.get("revenue_text", ""),
                    revenueSourceText=st.get("revenue_source", ""),
                    weekdayText=st.get("weekday_text", ""),
                    storeCountText=st.get("store_count_text", ""),
                    closureRateText=st.get("closure_text", ""),
                    openingRateText=st.get("opening_text", ""),
                    franchiseText=st.get("franchise_text", ""),
                    footTrafficText=st.get("foot_text", ""),
                    topAgeText=st.get("top_age", ""),
                    peakTimeText=st.get("peak_time", ""),
                    changeText=st.get("change_text", ""),
                    operatingMonthsText=st.get("op_months_text", ""),
                    dataSource=f"서울시 공공데이터 {quarter_label} 기준",
                    hasRealData=st.get("has_data", False),
                ),
            ))

        if superlative is not None:
            text = f"{superlative_line}\n\n{text}" if text else superlative_line
        elif valid_codes:
            # 결론 먼저(계획서 4장 I-21 / C2 골격의 첫 조각) — 1순위 상권과 그 근거 수치를 코드가 한 줄로.
            # LLM 서술은 그 뒤에 온다. 숫자는 real_stats에서 그대로 인용하므로 근거 가드와 정합.
            verdict = self._market_verdict_line(valid_codes[0], area_map, real_stats, service_name, area_scores)
            if verdict:
                text = f"{verdict}\n\n{text}" if text else verdict
        if no_data_codes and len(no_data_codes) < len(valid_codes):
            names = "·".join(area_map[c].trdar_name for c in no_data_codes if c in area_map)
            text = f"{text.rstrip()}\n\n※ {names}은(는) 이 업종({service_name}) 매출 데이터가 없어 참고용이에요."
        if caution_codes:
            text = answer_guard.suppress_recommendation(text)
            # 같은 대화에서 이미 고지한 상권은 한 줄로(2026-09-08 QA P10 — 매 턴 두 줄씩 반복)
            already = [
                code for code in caution_codes
                if any(m.role == "assistant" and area_map[code].trdar_name in (m.content or "")
                       and "등급으로" in (m.content or "") for m in history)
            ]
            fresh = [c for c in caution_codes if c not in already]
            notices = " ".join(
                answer_guard.grade_caution_notice(
                    area_map[code].trdar_name, area_scores[code].grade, area_scores[code].total,
                )
                for code in fresh
            )
            if already and not fresh:
                notices = answer_guard.GRADE_NOTICE_REPEAT
            text = f"{notices}\n\n{text}" if text else notices
        # 미지원 축 고지(I-12)가 맨 앞 — "없다"부터 말하고 보유 데이터 서술이 따른다
        text = (await self._budget_notice(prompt, profile)) + _unsupported_notice(prompt, _MARKET_UNSUPPORTED_NOTICES) + radius_note + text
        # 구조화 카드를 payload로 동반 저장 — 히스토리 재진입 시 카드 복원용
        await self._conversations.add_message(
            conversation_id, "assistant", text,
            payload={"recommendations": [r.model_dump() for r in recommendations]},
        )

        # 기록 경로: chat → 허브 포트 → recommendation (스포크끼리 직접 잇지 않음)
        await self._recorder.record(
            conversation_id,
            [
                RecommendedArea(
                    trdar_code=code,
                    trdar_name=area_map[code].trdar_name,
                    district_name=area_map[code].district_name,
                    category=service_name,
                    reason=reason_map.get(code, ""),
                    lat=area_map[code].lat,
                    lng=area_map[code].lng,
                )
                for code in valid_codes
            ],
        )

        return AskResponse(
            text=text, recommendations=recommendations, conversationId=conversation_id,
        )

    async def _answer_condition_ranking(
        self, conversation_id: int, prompt: str, axes: list[str], on_stage,
    ) -> AskResponse:
        """조건 질의 결정론 응답 — 랭킹 집계를 코드로 정렬해 N곳을 채운다(LLM 미사용).

        정렬 축은 실제 보유 지표만 쓴다: 폐업률(낮은 순)·월매출(높은 순).
        유동인구는 랭킹 집계에 없다 — 정렬한 척하지 않고 없다고 말한다(반경 가드와 같은 태도).
        """
        self._notify(on_stage, "data", "조건에 맞는 상권을 찾고 있어요")
        rows = await self._market.get_area_ranking()
        pool = [
            r for r in rows
            if r.closure_rate is not None and r.monthly_sales
            and (r.store_count or 0) >= _CONDITION_MIN_STORES
        ]
        count_match = _CONDITION_COUNT.search(prompt)
        count = int(count_match.group(1)) if count_match else _CONDITION_DEFAULT_COUNT
        count = max(1, min(count, _CONDITION_MAX_COUNT))

        want_closure = "closure" in axes
        pool.sort(key=lambda r: (
            r.closure_rate if want_closure else 0.0,
            -(r.monthly_sales or 0),
        ))
        top = pool[:count]
        if not top:
            text = (
                "조건으로 정렬할 상권 데이터를 찾지 못했어요. 동네·역·거리 이름을 함께"
                ' 물어봐 주세요 (예: "강남역 카페 어때?").'
            )
            await self._conversations.add_message(conversation_id, "assistant", text)
            return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

        crit = "폐업률 낮은 순(동률은 월매출 높은 순)" if want_closure else "월매출 높은 순"
        lines = [f"서울 전체(업종 무관, 점포 {_CONDITION_MIN_STORES}개 이상 상권)에서"
                 f" {crit} 상위 {len(top)}곳이에요."]
        for i, r in enumerate(top, 1):
            per = (
                f" · 점포당 월 {round(r.sales_per_store / 10000):,}만원"
                if r.sales_per_store else ""
            )
            change = f" · {r.change_indicator_name}" if r.change_indicator_name else ""
            lines.append(
                f"{i}. {r.trdar_name} ({r.district_name} {r.dong_name}) —"
                f" 폐업률 {r.closure_rate:.0f}% · 월매출 {r.monthly_sales / 1e8:.1f}억원"
                f"{per}{change}"
            )
        if "flow" in axes:
            lines.append(
                "※ 유동인구 순 정렬은 아직 지원하지 않아 위 결과에는 반영되지 않았어요."
            )
        lines.append(
            '특정 동네가 궁금하면 지역과 업종을 함께 물어봐 주세요 (예: "성수동 카페 어때?").'
        )
        text = "\n".join(lines)
        # 후속 앵커(3차 실측 P3) — "그 중 첫 번째" 류가 이어받을 코드를 payload로 남긴다.
        # recommendations 키가 아니므로 프론트 카드 복원에는 걸리지 않는다.
        await self._conversations.add_message(
            conversation_id, "assistant", text,
            payload={"rankingCodes": [r.trdar_code for r in top]},
        )
        return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

    async def _load_profile(self, user_id: int | None) -> UserProfileSummary | None:
        """프로파일 조회 — 비로그인·미작성·조회 실패는 전부 None(주입 생략, 답변 무손상)."""
        if user_id is None or self._profiles is None:
            return None
        try:
            return await self._profiles.get_profile(user_id)
        except Exception:
            logger.warning("[chat] 프로파일 조회 실패: user=%s", user_id, exc_info=True)
            return None

    @staticmethod
    def _profile_market_block(p: UserProfileSummary) -> str:
        """질문자 프로파일 블록 — phase2 서술의 관점 조정용(미작성 사용자는 블록 자체가 없다).

        프로파일은 근거 데이터가 아니다 — 유의점의 강조점만 조정하게 하고, 이를 근거로
        수치를 창작하거나 "이 예산으로 가능하다"고 단정하지 못하게 규칙을 함께 싣는다
        (임대료·권리금 데이터가 없어 예산 적합 판정 자체가 불가능하다).
        """
        return (
            "[질문자 프로파일 — 서술 관점 조정용]\n"
            f"- {p.purpose_label} · 투자성향 {p.risk_label} · 가용 예산 {p.budget_label}"
            f" · {p.debt_label} · {p.horizon_label} 관점\n"
            "- 이 프로파일에 맞춰 유의점의 강조점만 조정할 것(예: 예산이 작거나 부채 부담이"
            " 있으면 폐업률·경쟁 같은 리스크를 먼저). 프로파일을 근거로 수치를 창작하거나"
            " 특정 상권이 이 예산으로 가능하다고 단정하지 말 것(임대료·권리금 데이터 없음)\n"
            f"- text 첫 문장에 질문자 조건을 그대로 적을 것 — 예: \"{p.risk_label}·예산 {p.budget_label} 기준으로 보면 …\""
            " (2026-09-08 QA: 프로파일이 읽혔는지 사용자가 알 수 없었다)"
        )

    async def _orchestrate_json(self, prompt: str, phase_label: str) -> dict:
        """JSON 강제 호출 + 파싱 1회 재시도.

        소형 모델의 JSON 실패는 확률적이다(첫 재측정 실측 1/120 — MT04 phase2).
        같은 프롬프트 재호출 한 번으로 흡수하고, 두 번째 실패는 호출부의 기존
        오류 경로(폴백·InvalidLLMResponseError)로 그대로 던진다.
        """
        raw = await llm_orchestrator.orchestrate(prompt, format="json")
        try:
            return _parse_llm_json(raw)
        except Exception:
            logger.warning("[chat] %s 파싱 실패 — 1회 재시도: %s", phase_label, raw[:120])
        raw = await llm_orchestrator.orchestrate(prompt, format="json")
        return _parse_llm_json(raw)

    async def _classify_intent(self, prompt: str, history: list[Message]) -> tuple[str, list[str]]:
        try:
            parsed = await self._orchestrate_json(
                f"{INTENT_PROMPT}\n\n{self._history_block(history)}사용자 질문: {prompt}",
                "의도 분류",
            )
        except Exception:
            logger.warning("[chat] 의도 분류 파싱 실패(재시도 포함) → market 폴백")
            return "market", []
        stock_queries = self._normalize_stock_queries(parsed.get("stock_query"))
        intent = parsed.get("intent")
        if intent == "stock" and stock_queries:
            return "stock", stock_queries
        if intent == "stock":
            # 종목 추출 실패 — 상권으로 보내던 기존 오답 대신 뉴스 RAG가 차선
            return "market_news", []
        if intent == "market_news":
            return "market_news", []
        if intent == "general":
            # 도메인 후속 승계(4차 실측 M1 t5·M3 t4) — "거기 경쟁 가게 몇 개?"·"주의
            # 등급이면 하지 말라는 거야?"가 general로 이탈했다. 히스토리는 이미 phase0
            # 프롬프트에 있다 — 7.8B가 안 쓰는 것이라 코드가 승계한다. 지시어 또는
            # 도메인 어휘가 있고 직전 카드가 있을 때만(인사·상식 후속은 그대로 general).
            inherited = self._inherit_intent(prompt, history)
            if inherited is not None:
                return inherited
            return "general", []
        return "market", []  # 미지 라벨 포함 전부 market — 기존 동작 보존

    @staticmethod
    def _normalize_stock_queries(raw) -> list[str]:
        """phase0의 stock_query를 질의 리스트로 정규화한다.

        비교 질문("테슬라랑 애플 중 뭐가 나아?")에서 7.8B가 스키마(단일 문자열) 대신
        리스트나 그 문자열 표기("['테슬라', '애플']")를 반환한 실사례 방어 — str()로
        감싸면 리스트 표기가 심볼 리졸버까지 흘러가 전부 실패한다(2026-08-31 프로덕션).
        세 번째 변형: 쉼표 결합 단일 문자열("테슬라, 애플") — 2026-09-01 배포 검증에서
        실측(리졸버가 통째로 받아 "종목을 찾지 못했습니다: 테슬라, 애플").
        """
        if isinstance(raw, list):
            items = raw
        else:
            text = str(raw or "").strip()
            if text.startswith("[") and text.endswith("]"):
                try:
                    parsed = ast.literal_eval(text)
                    items = list(parsed) if isinstance(parsed, (list, tuple)) else [text]
                except (ValueError, SyntaxError):
                    items = [p.strip(" '\"") for p in text[1:-1].split(",")]
            elif re.search(r"[,·]", text):
                items = re.split(r"\s*[,·]\s*", text)
            elif " " in text and any(
                re.fullmatch(r"[A-Z][A-Z.\-]{0,5}", tok) for tok in text.split()
            ):
                # 네 번째 변형: 공백 결합 + 티커 혼재("테슬라 AAPL 애플" — 골든 재완주
                # SF06 실측). 공백만으로 자르면 "버크셔 해서웨이"가 쪼개지므로, 대문자
                # 티커 꼴 토큰이 섞여 있을 때만 다종목으로 본다.
                items = text.split()
            else:
                items = [text]
        return [q for q in (str(item).strip() for item in items) if q]

    async def _answer_signal_board(
        self, conversation_id: int, prompt: str, on_stage=None,
    ) -> AskResponse:
        """신호 보드 조회 — LLM 없이 워치리스트 최신 신호를 방향별로 답한다(결정론).

        종목 예측 화면의 보드와 같은 자료·정렬이다. 신호는 예측 확정이 아니라 과거 통계
        참고치이므로 지평·표본 유의성을 함께 적고, 매매 지시가 아님을 고지한다.
        """
        self._notify(on_stage, "data", "신호 보드를 읽고 있어요")
        want = "DOWN" if "하락" in prompt or "매도" in prompt else "UP"
        word = "하락" if want == "DOWN" else "상승"
        try:
            board = await self._signals.current_board(limit=50)
        except Exception:
            logger.warning("[chat] 신호 보드 조회 실패", exc_info=True)
            text = answer_guard.ensure_disclaimer(
                "지금 신호 보드를 읽어오지 못했어요. 잠시 뒤 다시 물어보시거나 종목 예측"
                " 화면의 보드를 확인해 주세요."
            )
            await self._conversations.add_message(conversation_id, "assistant", text)
            return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

        rows = [r for r in board.rows if r.direction == want][:_SIGNAL_BOARD_LIMIT]
        horizon = board.horizon_days
        if not rows:
            text = (
                f"지금은 워치리스트에 {horizon}거래일 지평 {word} 신호가 나온 종목이 없어요."
                " 신호는 하루 한 번 갱신되니 내일 다시 물어보셔도 돼요."
            )
        else:
            as_of = max(r.as_of for r in rows)
            lines = [
                f"워치리스트에서 앞으로 {horizon}거래일 지평 {word} 신호가 나온 종목이에요"
                f" (신호 {as_of:%m/%d} 기준, 신호가 뚜렷한 순)."
            ]
            for i, r in enumerate(rows, 1):
                unit = self._currency_unit(r.ticker)
                price = self._price_text(r.price, unit)
                change = f" ({r.change_pct * 100:+.1f}%)" if r.change_pct is not None else ""
                if r.up_rate is None or r.baseline_up_rate is None:
                    stat = "과거 통계 표본 없음"
                else:
                    stat = (
                        f"같은 신호일 때 실제로 {word}한 비율 {r.up_rate * 100:.0f}%"
                        f" · 평소 {r.baseline_up_rate * 100:.0f}%"
                        f" · {'통계적으로 유의' if r.ready else '유의성 미달'}"
                    )
                lines.append(f"{i}. {r.name}({r.ticker}) — {price}{change} · {stat}")
            lines.append(
                f"신호는 오늘 등락이 아니라 앞으로 {horizon}거래일 전망이고, 매매 지시가"
                " 아니에요. 전체 보드는 종목 예측 화면에서 볼 수 있고, 종목명을 말씀하시면"
                " 지표·뉴스 근거를 읽어드릴게요."
            )
            text = "\n".join(lines)
        text = answer_guard.ensure_disclaimer(text)
        await self._conversations.add_message(conversation_id, "assistant", text)
        return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

    @staticmethod
    def _news_detail_text(history: list[Message]) -> str | None:
        """직전 카드의 근거 뉴스를 그대로 나열한다 — 근거 뉴스가 없는 대화면 None(정상 흐름)."""
        for m in reversed(history):
            payload = m.payload or {}
            news = payload.get("news")
            if news:
                lines = ["직전 답변의 근거 뉴스예요 (제목·날짜·라벨만 저장하고 본문은 담지 않아요)."]
                for n in news[:8]:
                    parts = [n.get("publishedAt") or "날짜 미상"]
                    if n.get("ticker"):
                        parts.append(str(n["ticker"]))
                    sentiment = n.get("sentiment")
                    if sentiment is not None:
                        parts.append("호재" if sentiment > 0 else "악재" if sentiment < 0 else "중립")
                    if n.get("eventType"):
                        parts.append(str(n["eventType"]))
                    lines.append(f"- {' · '.join(parts)} — {n.get('title', '')}")
                return "\n".join(lines)
            card = payload.get("stock")
            if card and card.get("headlines"):
                lines = [
                    f"{card.get('symbol', '')} 답변의 근거 헤드라인이에요 (제목만 저장하고"
                    " 본문은 담지 않아요)."
                ]
                lines.extend(f"- {h}" for h in card["headlines"][:8])
                return "\n".join(lines)
        return None

    async def _answer_service_meta(self, conversation_id: int) -> AskResponse:
        """자기 시그널 검증치 질문 — LLM 없이 재적합 리포트로 답한다(결정론).

        이 서비스의 차별점은 "측정해서 미달이면 기각"하는 계측 정직성인데, LLM 경로는
        그걸 모른 채 자기 서비스를 제3자 취급하는 일반론을 지어냈다(2026-08-31 q05).
        수치는 허브 ForecastRefitPort의 최신 리포트에서 읽고, 미주입·조회 실패·미집계는
        방법론 설명만으로 열화한다(무손상 규칙).
        """
        lines = [
            "이 서비스의 방향 신호(상승/하락) 검증 방식은 이렇습니다.",
            "- 적중 기준: 5거래일 뒤 수익률이 그 종목의 평소 변동폭(ATR 기반)의 일정 배수를"
            " 넘어야 적중으로 칩니다 — 오르내림 부호만 세면 '항상 매수'와 구분되지 않아서예요.",
            "- 사용 조건: 표본 100건 이상 + Wilson 95% 신뢰구간 하한이 기준선(평소 상승률)을"
            " 넘는 조합만 쓰고, 매주 재채점해 통과한 조합만 승격합니다.",
        ]
        stats_line = "- 최근 재채점 집계는 준비 중입니다."
        if self._refit is not None:
            try:
                report = await self._refit.latest()
                row = self._gate_row(report) if report else None
                if report is not None and row is not None:
                    verdict = (
                        "검증 게이트 통과" if row.gate_passed
                        else "아직 게이트 미달이라 답변에 단정 문구를 쓰지 않습니다"
                    )
                    rate = f"{row.hit_rate:.0%}" if row.hit_rate is not None else "집계 불가"
                    stats_line = (
                        f"- 현재 활성 조합의 최근 재채점({report.ran_at:%Y-%m-%d} 기준,"
                        f" {report.gate_horizon}거래일 지평): 표본 {row.n}건 중"
                        f" {row.hits}건 적중 (적중률 {rate} · 기준선 {row.baseline:.0%}"
                        f" · Wilson 하한 {row.wilson_lower:.0%}) — {verdict}."
                    )
            except Exception:
                logger.warning("[chat] 재적합 리포트 조회 실패 — 방법론만 답변", exc_info=True)
        lines.append(stats_line)
        lines.append(
            "종목별 과거 통계는 각 종목의 예측 화면에서 표본·신뢰구간과 함께 볼 수 있어요."
            " 이 수치는 과거 채점 결과이며 미래 수익을 보장하지 않습니다."
        )
        text = "\n".join(lines)
        await self._conversations.add_message(conversation_id, "assistant", text)
        return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

    @staticmethod
    def _gate_row(report: RefitReportInfo) -> RefitCandidateRow | None:
        """게이트 판정 지평 보드의 현행 조합 행 — 없으면 None(집계 준비 중 열화)."""
        for board in report.boards:
            if board.horizon_days == report.gate_horizon:
                return board.current
        return None

    async def _answer_general(self, conversation_id: int, prompt: str) -> AskResponse:
        """상권/주식과 무관한 일반 질문 — 허브 GeminiAnswerPort(외부 Gemini API)로 답변.

        정체성 프리앰블(3차 실측 P1): 외부 모델이 "저는 OpenAI에서 개발한…"이라고 자기
        부정하는 것을 막는다 — 메타 가드가 놓친 질문이 이 경로로 낙하할 수 있다.
        """
        framed = (
            "너는 redoceanmap(서울 상권·주식 분석 서비스)의 대화 어시스턴트다. "
            "자신을 OpenAI·구글 등 외부 회사의 모델이라고 소개하지 말 것. 이 서비스의 "
            "신호 적중률·검증 수치를 물으면 지어내지 말고 \"'너희 서비스 적중률 알려줘'"
            "처럼 물어보면 실측 수치로 답한다\"고 안내할 것. 서비스 기능은 다음이 전부다"
            " — 상권 분석 채팅, 종목 분석 채팅, 프로필의 가격 도달 알림(이메일·텔레그램),"
            " 북마크 종목 뉴스·신호 알림, AI 모의투자 화면(/paper — EXAONE이 매일 예측 스냅샷·뉴스를"
            " 읽고 판단한 것을 다음 장 시가에 사후 체결하는 기록, 실제 매매 아님·권유 아님)."
            " 이 목록에 없는 기능(상권 임대료·권리금 알림 등)이나"
            " 화면 사용법(버튼 위치 등)을 지어내서 안내하지 말 것.\n\n질문: "
        )
        try:
            text = (await self._gemini.generate(f"{framed}{prompt}")).answer
        except GeminiAnswerError as exc:
            # 외부 API 실패는 500 대신 안내로 열화 — 대화 흐름을 끊지 않는다.
            logger.warning("[chat] general 분기 Gemini 실패: %s", exc)
            text = "죄송해요, 지금 일반 질문 답변 기능에 일시적인 문제가 있어요. 상권이나 주식 질문은 바로 도와드릴 수 있어요."
        await self._conversations.add_message(conversation_id, "assistant", text)
        return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

    async def _answer_market_news(
        self, conversation_id: int, prompt: str, on_stage=None,
    ) -> AskResponse:
        """종목 무관 시장/업황 질문 — 수집 뉴스 의미 검색(RAG)을 근거로 서술."""
        self._notify(on_stage, "search", "관련 뉴스를 찾고 있어요")
        hits = await self._news.search(prompt, ticker=None, limit=8)
        context = self._format_news_context(prompt, hits)
        self._notify(on_stage, "narrate", "동향을 정리하고 있어요")
        # 최종 서술(최종 사용자 답변) → 오케스트레이터 기본 모델(7.8B)
        text = await llm_orchestrator.orchestrate(f"{MARKET_NEWS_ANSWER_PROMPT}\n\n{context}")
        # 절대 규칙은 프롬프트가 아니라 코드가 지킨다(2026-08-28 골든셋 위반 13건)
        text = answer_guard.strip_dangling_citations(
            answer_guard.normalize_citation_markers(text, answer_guard.allowed_citations(context)),
            answer_guard.allowed_citations(context),
        )
        text = answer_guard.ensure_disclaimer(text)
        # 미지원 축 고지(I-12) — 배당 질의는 종목 미추출 시 이 경로로 낙하한다(q03 실측)
        text = _unsupported_notice(prompt, _STOCK_UNSUPPORTED_NOTICES) + text
        news = [
            NewsCardItem(
                title=h.title,
                publishedAt=f"{h.published_at:%Y-%m-%d}" if h.published_at else None,
                ticker=h.ticker,
                sentiment=h.sentiment,
                eventType=h.event_type,
            )
            for h in hits
        ]
        # 근거 뉴스 카드를 payload로 동반 저장 — 히스토리 재진입 시 카드 복원용(stock 카드와 동일 규칙)
        payload = {"news": [n.model_dump() for n in news]} if news else None
        await self._conversations.add_message(conversation_id, "assistant", text, payload=payload)
        return AskResponse(
            text=text, recommendations=[], conversationId=conversation_id, news=news,
        )

    @staticmethod
    def _format_news_context(prompt: str, hits: list[NewsHit]) -> str:
        if not hits:
            return (
                f"사용자 질문: {prompt}\n\n"
                "[관련 수집 뉴스]\n수집된 관련 뉴스가 없습니다 — 일반적 지식 수준으로만 답하되"
                " 데이터 부재를 안내하세요."
            )
        lines = [f"사용자 질문: {prompt}\n", "[관련 수집 뉴스 — 의미 유사도 상위]"]
        for i, h in enumerate(hits, start=1):
            date_text = f"{h.published_at:%Y-%m-%d}" if h.published_at else "날짜 미상"
            ticker_text = h.ticker or "종목 무관"
            if h.sentiment is None:
                label_text = "감성 라벨 없음"
            else:
                direction = "호재" if h.sentiment > 0 else "악재" if h.sentiment < 0 else "중립"
                label_text = f"감성 {h.sentiment:+.1f}({direction})·{h.event_type or '기타'}"
            # '근거 [n]' 표기가 인용 마커의 단일 정의처 — 채점기(eval_scorer)가 같은 패턴을 읽는다
            lines.append(f"- 근거 [{i}] ({date_text} | {ticker_text} | {label_text}) {h.title}")
        return "\n".join(lines)

    async def _answer_stock_compare(
        self, conversation_id: int, prompt: str, queries: list[str], on_stage=None,
    ) -> AskResponse:
        """종목 2~3개 비교표 — 방향·현재가·과거 같은 신호 상승 비율/평소·RSI·모멘텀·거래량 판정을 나란히. 결론도 코드가 쓴다."""
        self._notify(on_stage, "analyze", f"{len(queries)}개 종목을 나란히 보고 있어요")
        rows, failed = [], []
        for q in queries:
            try:
                a = await self._stocks.analyze(q)
            except StockAnalysisUnavailable as e:
                failed.append(f"{q}({e.detail})")
                continue
            f = None
            if self._forecaster is not None:
                try:
                    f = await self._forecaster.forecast(a.symbol)
                except Exception:
                    f = None
            rows.append((q, a, f))
        if not rows:
            text = "비교할 종목을 찾지 못했어요: " + ", ".join(failed) + " — 정확한 종목명이나 티커로 다시 물어봐 주세요."
            await self._conversations.add_message(conversation_id, "assistant", text)
            return AskResponse(text=text, recommendations=[], conversationId=conversation_id)
        direction_word = {"UP": "상승 신호", "DOWN": "하락 신호", "NEUTRAL": "중립"}
        header = ("| 종목 | 현재가(지연) | 지금 신호 | 과거 같은 신호일 때 상승 비율 / 평소 | RSI | 12-1 모멘텀"
                  " | 거래량(20일 대비) | 뉴스 감성 |\n|---|---|---|---|---|---|---|---|")
        table = [header]
        for q, a, f in rows:
            unit = self._currency_unit(a.symbol)
            price = f"{a.price:,.0f}{unit}" if unit == "원" else f"${a.price:,.2f}"
            if f is not None and f.up_rate is not None and f.baseline_up_rate is not None:
                stat = f"{f.up_rate:.0%} / {f.baseline_up_rate:.0%}(n={f.sample_size}{'' if f.ready else ', 유의성 미달'})"
            else:
                stat = "표본 없음"
            table.append(
                f"| {q}({a.symbol}) | {price} | {direction_word.get(a.direction, a.direction)} | {stat}"
                f" | {a.rsi:.0f} | {a.momentum_12_1:+.1%}"
                f" | {answer_guard.volume_verdict_cell(ma20=a.ma20, ma50=a.ma50, volume_ratio=a.volume_ratio)}"
                f" | {a.sentiment_label} |"
            )
        ups = [q for q, a, _ in rows if a.direction == "UP"]
        downs = [q for q, a, _ in rows if a.direction == "DOWN"]
        if not ups and not downs:
            verdict = "지금은 두 종목 모두 방향 신호가 중립이라, 이 데이터로는 우열을 가르지 않아요."
        else:
            parts = []
            if ups:
                parts.append(f"{'·'.join(ups)}에 상승 참고 신호")
            if downs:
                parts.append(f"{'·'.join(downs)}에 하락 참고 신호")
            verdict = " / ".join(parts) + "가 있어요 — 과거 통계 참고치이지 매매 지시가 아니에요."
        text = (
            "**비교**\n" + "\n".join(table) + f"\n\n**결론** {verdict}"
            + (f"\n(찾지 못함: {', '.join(failed)})" if failed else "")
            + "\n각 종목을 따로 물으면 뉴스·매물대·가치 근거까지 서술해 드려요."
        )
        text = answer_guard.ensure_disclaimer(text)
        # 카드는 싣지 않는다 — 비교 답에 한 종목 카드만 붙으면 그 종목을 고른 것처럼 읽힌다
        await self._conversations.add_message(conversation_id, "assistant", text)
        return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

    async def _answer_stock(
        self, conversation_id: int, prompt: str, stock_queries: list[str], on_stage=None,
        profile: UserProfileSummary | None = None,
    ) -> AskResponse:
        stock_query, extra_queries = stock_queries[0], stock_queries[1:]
        if extra_queries and _COMPARE_RE.search(prompt):
            # 다종목 비교(2026-09-08 QA P07) — 예전엔 첫 종목만 분석하고 "따로 물어봐 주세요"로 끝났다.
            # 비교표는 LLM 없이 코드가 만든다(수치 비교에 서술이 끼면 우열을 지어낸다). 비교 어휘가
            # 없는 다중 질의(분류기가 "PER 낮은 저평가"를 셋으로 쪼갠 경우)는 기존 단일 경로로 둔다.
            return await self._answer_stock_compare(conversation_id, prompt, stock_queries[:3], on_stage)
        compare_notice = (
            f"여러 종목을 한 번에 물으셔서 '{stock_query}'만 분석했어요. "
            f"{', '.join(extra_queries)}은(는) 따로 물어봐 주세요.\n\n"
        ) if extra_queries else ""
        # 미지원 고지는 실패 경로에도 붙는다(3차 실측 P4) — "PER 낮은 5개"가 리졸버에서
        # 죽으면 고지 없이 오류 원문만 나갔다.
        unsupported_note = _unsupported_notice(prompt, _STOCK_UNSUPPORTED_NOTICES)
        self._notify(on_stage, "analyze", "종목 지표를 분석하고 있어요")
        try:
            analysis = await self._stocks.analyze(stock_query)
        except StockAnalysisUnavailable as e:
            text = f"{unsupported_note}{compare_notice}{e.detail} 정확한 종목명이나 티커로 다시 물어봐 주세요."
            await self._conversations.add_message(conversation_id, "assistant", text)
            return AskResponse(text=text, recommendations=[], conversationId=conversation_id)

        # RAG 보강: 해당 종목 뉴스를 의미 검색(라벨 동반). 빈 결과면 섹션 생략 — 기존 출력 무손상
        hits = await self._news.search(prompt, ticker=analysis.symbol, limit=5)

        # 영향 키워드(B2) — 최근 헤드라인 빈도의 결정론 요약. 실패·표본 미달은 빈 리스트로
        # 열화(라인 생략) — forecast·펀더멘털과 같은 무손상 규칙.
        keywords: list[NewsKeyword] = []
        try:
            keywords = await self._news.top_keywords(analysis.symbol)
        except Exception:
            logger.warning("[chat] 키워드 추출 실패: %s", analysis.symbol, exc_info=True)

        # forecast(확률 요약)는 표본이 있어야 강한 결론이 되고, 조회 실패는 표본 없음으로 열화.
        forecast = None
        if self._forecaster is not None:
            try:
                forecast = await self._forecaster.forecast(analysis.symbol)
            except Exception:  # 예측 실패가 종목 답변 자체를 깨지 않게 열화
                logger.warning("[chat] forecast 조회 실패: %s", analysis.symbol, exc_info=True)

        # 가치·체력 — "이 회사 싼가/튼튼한가"(펀더멘털). 미수집·실패면 빈 리스트로 열화.
        value_notes: list[str] = []
        if self._fundamentals is not None:
            try:
                insights = await self._fundamentals.latest_insights(analysis.symbol)
                value_notes = [i.text for i in insights[:2]]
            except Exception:
                logger.warning("[chat] 펀더멘털 조회 실패: %s", analysis.symbol, exc_info=True)

        # 둘 다 서술 '앞'에서 조회한다 — 예전엔 답변을 만든 뒤에 조회해 카드에만 실렸고,
        # 그래서 본문이 밸류에이션·과거 통계를 근거로 말하지 못했다.
        self._notify(on_stage, "narrate", "분석 내용을 정리하고 있어요")
        context = self._format_stock_context(
            prompt, analysis, hits, forecast, value_notes, profile, keywords,
        )
        # 최종 서술(최종 사용자 답변) → 오케스트레이터 기본 모델(7.8B)
        text = await llm_orchestrator.orchestrate(f"{STOCK_ANSWER_PROMPT}\n\n{context}")
        # 절대 규칙은 프롬프트가 아니라 코드가 지킨다(2026-08-28 골든셋 위반 13건).
        # 프롬프트에 이미 두 규칙이 다 적혀 있었다 — 7.8B가 안 지킨 것이라 문구로는 못 막는다.
        text = answer_guard.strip_dangling_citations(
            answer_guard.normalize_citation_markers(text, answer_guard.allowed_citations(context)),
            answer_guard.allowed_citations(context),
        )
        # 거래량 판정(C1 골격)도 같은 이유로 코드가 보장한다 — 압축 뒤 포함률 0.70 → 0.467
        text = answer_guard.ensure_volume_verdict(
            text, ma20=analysis.ma20, ma50=analysis.ma50, volume_ratio=analysis.volume_ratio,
        )
        # 지표 해석 결정론(4차 실측 S2 t3·S9 t4) — RSI 40.3을 "과매수"로 서술하고 직전
        # 턴과 과매도↔과매수를 뒤집었다. 원값과 어긋난 과열 어휘·감성 호악재를 코드가 교정.
        text = answer_guard.enforce_overheat_claim(
            text, rsi=analysis.rsi, bb_percent_b=analysis.bb_percent_b,
        )
        text = answer_guard.enforce_sentiment_claim(text, analysis.sentiment)
        # 매물대 거리 재라벨 금지(I-15, 실측 q09) — 먼 구간을 "근처"라 부르지 못하게 한다
        text = answer_guard.enforce_distance_claim(
            text, price=analysis.price, band_low=analysis.volume_poc_low,
            band_high=analysis.volume_poc_high,
            atr_value=analysis.price * analysis.atr_pct,
        )
        # 매물대 후속 결정론(P4-11, 4차 실측 S9 t4) — "매물대 어디랬지?"에 과매수/수급
        # 서술만 하고 매물대를 답하지 않았다. 물었는데 본문에 없으면 코드가 채운다.
        if "매물대" in prompt:
            if analysis.volume_poc_low is None or analysis.volume_poc_high is None:
                text = (
                    "※ 이 종목은 매물대(거래 밀집 구간)를 산출할 표본이 부족해 값을"
                    " 드릴 수 없어요.\n\n" + text
                )
            elif "매물대" not in text and "밀집 구간" not in text:
                poc_line = self._volume_profile_text(
                    analysis, self._currency_unit(analysis.symbol),
                ).strip().lstrip("- ")
                text = f"{text.rstrip()}\n{poc_line}"
        # 가격 도달 알림 안내([6]) — 중립 답변의 공식 대체재. 방향 단정은 데이터가 아직
        # 허락하지 않으므로(시그널 대개편 결론) 예측 대신 사실 통지(사용자 설정 조건)를 권한다.
        if analysis.direction == "NEUTRAL":
            text = (
                f"{text.rstrip()}\n\n지금은 방향 신호가 중립이에요. 원하시는 가격에 닿으면"
                " 알려드릴 수 있어요 — 프로필의 '가격 도달 알림'에서 조건을 걸어 보세요."
            )
        # 용어 결정론 풀이(I-19) — 질문에 없는 전문용어의 첫 등장에 괄호 설명을 붙인다
        text = answer_guard.attach_glossary(text, prompt)
        text = answer_guard.ensure_disclaimer(text)
        # 미지원 축·확률 고지(I-12·I-17)가 비교 고지(I-18)보다 앞 — 전부 결정론 문두 삽입
        text = unsupported_note + compare_notice + text

        # 결론 한 줄 — 페이지 히어로와 같은 verdict 로직으로 서버가 계산해 카드에 싣는다.
        # detail(표본·신뢰구간)까지 카드에 싣는다 — 배지 밑에 근거가 없으면 판정만 남아
        # "왜?"가 답이 안 된다(2026-08-28 배지 UI).
        headline, basis = verdict_headline(analysis.direction, forecast)
        card = StockCard(
            symbol=analysis.symbol,
            price=analysis.price,
            direction=analysis.direction,
            confidence=analysis.confidence,
            rsi=analysis.rsi,
            ma20=analysis.ma20,
            ma50=analysis.ma50,
            support=analysis.support,
            resistance=analysis.resistance,
            sentimentLabel=analysis.sentiment_label,
            headlines=analysis.headlines,
            atrPct=analysis.atr_pct,
            bbPercentB=analysis.bb_percent_b,
            volumeRatio=analysis.volume_ratio,
            obvSlope=analysis.obv_slope,
            momentum12To1=analysis.momentum_12_1,
            referenceUpSignal=analysis.reference_up_signal,
            headline=headline,
            watch=self._watch_point(
                analysis.price, analysis.support, analysis.resistance,
                self._currency_unit(analysis.symbol),
            ),
            strength=verdict_strength(analysis.score, analysis.up_threshold),
            basis=basis,
            value=value_notes,
            keywords=[k.keyword for k in keywords],
        )
        # 구조화 카드를 payload로 동반 저장 — 히스토리 재진입 시 카드 복원용
        await self._conversations.add_message(
            conversation_id, "assistant", text, payload={"stock": card.model_dump()},
        )
        return AskResponse(
            text=text, recommendations=[], conversationId=conversation_id, stock=card,
        )

    @staticmethod
    def _format_area_articles(hits: list[MarketNewsHit]) -> str:
        lines = ["[관련 지역 기사 — 의미 유사도 상위]"]
        for h in hits:
            date_text = f"{h.published_at:%Y-%m-%d}" if h.published_at else "날짜 미상"
            area_text = h.area_tag or "지역 공통"
            lines.append(f"- ({date_text} | {area_text} | {h.source}) {h.title}")
        return "\n".join(lines)

    @staticmethod
    def _ensure_risk_note(reason: str, st: dict) -> str:
        """추천 이유에 "유의할 점"이 없으면 데이터 기반 유의 문장을 붙인다(C2 리스크 의무).

        붙이는 수치는 폐업률·경쟁 등 phase2 컨텍스트에 이미 있던 것만 쓴다 —
        둘 다 없으면 데이터의 한계(임대료 미보유)를 유의점으로 쓴다.
        """
        if not reason or "유의" in reason:
            return reason
        fact = next(
            (st.get(k) for k in ("closure_text", "rival_text")
             if st.get(k) and st.get(k) != "데이터 없음"),
            None,
        )
        if fact:
            return f"{reason} 유의할 점: {fact} — 창업 전 직접 확인이 필요해요."
        return f"{reason} 유의할 점: 임대료·권리금은 데이터가 없어 별도 확인이 필요해요."

    @staticmethod
    def _score_text(score: AreaScoreInfo) -> str:
        """상권 종합점수 의미 해석 문장 — 컴포넌트마다 서울 평균 대비 방향을 코드가 못박는다.

        2026-08-31 실측(p04): 방향 없이 점수만 주면 7.8B가 47.9점(평균 미달)을 "크게
        상회"로 뒤집어 서술했다. 성장 컴포넌트는 상권/서울 QoQ 실측치를 병기한다.
        """
        parts = []
        for c in score.components:
            side = "상회" if c.score > 50 else ("동률" if c.score == 50 else "미달")
            if c.key in ("sales_growth", "floating_growth"):
                parts.append(
                    f"{c.name} {c.score}점(서울 평균 {side} —"
                    f" 상권 {c.value:+.1f}% vs 서울 {c.benchmark:+.1f}%)"
                )
            else:
                parts.append(f"{c.name} {c.score}점(서울 평균 {side})")
        total_side = "상회" if score.total > 50 else ("동률" if score.total == 50 else "미달")
        return (
            f"종합 {score.total}점·{score.grade} (50점=서울 평균, 이 상권은 평균 {total_side})"
            " — " + ", ".join(parts)
        )

    @staticmethod
    def _trend_text(score: AreaScoreInfo) -> str:
        """분기 추이 한 줄(I-20) — 전문가 질문에만 주입한다(프롬프트 예산 보호).

        최근 6분기만 싣고, 값이 전혀 없는 분기는 건너뛴다(없는 축은 '-'가 아니라 생략).
        """
        points = [t for t in score.trend if t.monthly_sales or t.total_floating_pop][-6:]
        if not points:
            return ""
        parts = []
        for t in points:
            seg = [str(t.year_quarter)]
            if t.monthly_sales:
                qoq = f"{t.sales_qoq:+.1f}%" if t.sales_qoq is not None else "-"
                seg.append(f"매출 {t.monthly_sales / 1e8:.1f}억(QoQ {qoq})")
            if t.total_floating_pop:
                fq = f"{t.floating_qoq:+.1f}%" if t.floating_qoq is not None else "-"
                seg.append(f"유동 {t.total_floating_pop / 10000:.1f}만(QoQ {fq})")
            parts.append(" ".join(seg))
        return "- 분기 추이: " + " / ".join(parts) + "\n"

    @staticmethod
    def _permit_text(churn: PermitChurnInfo | None) -> str:
        """인허가 업소 교체 한 줄 — 없으면 라인 자체를 생략한다(열화 동작).

        개업·폐업을 나란히 줘야 "늘고 있다"가 아니라 "얼마나 갈아치우는 곳인가"가 읽힌다.
        영업중 수는 분기 팩트의 점포 수와 출처가 달라 비교 대상이 아니다 — 프롬프트에서도
        따로 금지한다.
        """
        if churn is None:
            return ""
        return (
            f"- 인허가 업소 교체(최근 {churn.months}개월): "
            f"개업 {churn.opened}곳 · 폐업 {churn.closed}곳 · 현재 영업중 {churn.active}곳\n"
        )

    @classmethod
    def _insight_text(cls, insights: tuple[AreaInsight, ...] | None) -> str:
        """상권 성격 해석 — 우선순위 상위 4개만. 없으면 라인 자체를 생략한다.

        서술자가 최대 9문장까지 만드는데 상권 3곳이면 프롬프트가 1천 자를 넘는다.
        7.8B에 무제한으로 부으면 답변 품질이 떨어져 소비자(chat)가 잘라 쓴다.
        """
        if not insights:
            return ""
        order = {k: i for i, k in enumerate(_INSIGHT_PRIORITY)}
        top = sorted(insights, key=lambda i: order.get(i.key, len(order)))[:4]
        return "- 상권 성격: " + " / ".join(i.text for i in top) + "\n"

    @staticmethod
    def _volatility_text(atr_pct: float) -> str:
        pct = atr_pct * 100
        if pct >= 4.0:
            return f"ATR(14) 종가 대비 {pct:.1f}% — 일 변동성이 큰 편(급등락 주의)"
        if pct >= 2.0:
            return f"ATR(14) 종가 대비 {pct:.1f}% — 보통 수준의 변동성"
        return f"ATR(14) 종가 대비 {pct:.1f}% — 변동성이 낮고 안정적"

    @staticmethod
    def _bollinger_text(percent_b: float) -> str:
        if percent_b < 0.0:
            return f"%B {percent_b:.2f} — 밴드 하단 이탈(단기 과매도 극단)"
        if percent_b <= 0.2:
            return f"%B {percent_b:.2f} — 밴드 하단 부근(단기 과매도권)"
        if percent_b >= 1.0:
            return f"%B {percent_b:.2f} — 밴드 상단 이탈(단기 과열 극단)"
        if percent_b >= 0.8:
            return f"%B {percent_b:.2f} — 밴드 상단 부근(단기 과열권)"
        return f"%B {percent_b:.2f} — 밴드 중간 영역(중립)"

    @staticmethod
    def _volume_text(ratio: float, obv_slope: float) -> str:
        if ratio >= 1.5:
            vol = f"최근 5일 거래량이 20일 평균의 {ratio:.1f}배 — 급증"
        elif ratio <= 0.7:
            vol = f"최근 5일 거래량이 20일 평균의 {ratio:.1f}배 — 한산"
        else:
            vol = f"최근 5일 거래량이 20일 평균의 {ratio:.1f}배 — 평소 수준"
        if obv_slope > 0:
            flow = "수급은 유입 우위(OBV 상승)"
        elif obv_slope < 0:
            flow = "수급은 유출 우위(OBV 하락)"
        else:
            flow = "수급 방향성 중립"
        return f"{vol}, {flow}"

    @staticmethod
    def _momentum_text(momentum: float) -> str:
        if momentum == 0.0:
            return "12-1 모멘텀 중립 (또는 상장 이력 1년 미만으로 산출 불가)"
        pct = momentum * 100
        if momentum >= 0.15:
            return f"12-1 모멘텀 {pct:+.1f}% — 중장기 상승 추세 뚜렷"
        if momentum > 0.0:
            return f"12-1 모멘텀 {pct:+.1f}% — 완만한 중장기 상승"
        return f"12-1 모멘텀 {pct:+.1f}% — 중장기 하락 추세"

    @staticmethod
    def _volume_profile_text(r: StockAnalysisResult, unit: str) -> str:
        """매물대(거래 밀집 구간) 한 줄 — 산출 불가면 라인 자체를 생략한다(열화 동작).

        차트가 화면에 그리는 것과 같은 계산이라 사용자가 본 구간과 같은 값이 나온다.
        **지지/저항으로 부르지 않는다** — 위에 이미 출처가 다른 지지선/저항선이 있어
        섞이면 둘 다 못 믿게 된다. 문구는 화면과 같은 '거래 밀집 구간'으로 통일한다.
        """
        if r.volume_poc_low is None or r.volume_poc_high is None:
            return ""
        where = {"above": "그 위", "below": "그 아래", "inside": "그 안"}.get(
            r.volume_price_position or "", "위치 미상"
        )
        share = f" (전체 거래량의 {r.volume_poc_share:.0%})" if r.volume_poc_share else ""
        return (
            f"- 거래 밀집 구간: {ChatInteractor._price_text(r.volume_poc_low, unit).removesuffix(unit)}"
            f"~{ChatInteractor._price_text(r.volume_poc_high, unit)}"
            f"{share}, 현재가는 {where}"
            " — 과거 거래량이 몰린 가격대일 뿐 지지선·저항선이 아님\n"
        )

    @staticmethod
    def _price_position_text(price: float, support: float, resistance: float) -> str:
        """현재가가 60일 저/고점 구간의 어디쯤인지 — 위치 해석을 안 주면 모델이 '지지선 근처
        안정·저항선 돌파 난항' 같은 근거 없는 템플릿을 지어낸다(중간권인데도)."""
        if resistance <= support:
            return "구간 산출 불가"
        ratio = max(0.0, min(1.0, (price - support) / (resistance - support)))
        pct = round(ratio * 100)
        if ratio <= 0.25:
            zone = "저점권 — 지지선(저점)에 가까움"
        elif ratio >= 0.75:
            zone = "고점권 — 저항선(고점)에 가까움"
        else:
            zone = "중간권 — 지지선·저항선 어디에도 가깝지 않음(근처 안정·돌파 난항 표현 금지)"
        return f"60일 저점~고점 구간의 {pct}% 지점 ({zone})"

    @staticmethod
    def _watch_point(price: float, support: float, resistance: float, unit: str) -> str | None:
        """지켜볼 포인트 — 현재가가 60일 저/고점 구간 어디쯤인지에 따라 관측 지시(조언 아님).
        페이지 히어로 watchPoint와 같은 결. 구간 산출 불가면 None."""
        if not (resistance > support):
            return None
        ratio = max(0.0, min(1.0, (price - support) / (resistance - support)))
        lo = ChatInteractor._price_text(support, unit)
        hi = ChatInteractor._price_text(resistance, unit)
        if ratio <= 0.25:
            return f"저점권입니다. {lo}(60일 저점) 이탈 여부를 지켜보세요."
        if ratio >= 0.75:
            return f"고점권입니다. {hi}(60일 고점) 돌파·유지 여부를 지켜보세요."
        return f"관심 있으면 {lo}(60일 저점) 이탈이나 {hi}(60일 고점) 돌파를 지켜보세요."

    @staticmethod
    def _currency_unit(symbol: str) -> str:
        """티커로 통화를 정한다 — 한국 6자리(거래소 접미 포함)는 원, 그 외는 달러.

        컨텍스트에 단위를 안 주면 모델이 추측해 미국 종목을 '원'으로 서술하는 오답이 났다.
        """
        base = symbol.split(".")[0]
        return "원" if len(base) == 6 and base.isdigit() else "달러"

    @staticmethod
    def _price_text(value: float, unit: str) -> str:
        """가격 표기 — 원화는 정수(호가에 소수점이 없다), 달러는 소수 2자리.

        컨텍스트의 "1,245,729.86원"을 모델이 답변에 그대로 옮겨 적었다(2026-08-31 실측).
        """
        return f"{value:,.0f}{unit}" if unit == "원" else f"{value:,.2f}{unit}"

    @staticmethod
    def _forecast_text(f: StockForecastSummary | None) -> str:
        """과거 통계 한 줄 — 표본·기준선·신뢰구간을 반드시 병기한다.

        확률 단정 금지 규칙(백테스트 결론)은 그대로다. 표본이 유의하지 않으면
        수치를 아예 주지 않는다 — 소형 모델이 '확률'로 단정하는 것을 원천 차단.
        """
        if f is None or f.up_rate is None or f.sample_size <= 0:
            return ""
        if not f.ready:
            return (
                f"- 근거 [2] 과거 통계: 같은 신호가 났던 사례가 {f.sample_size}건뿐이라"
                " 통계적으로 유의하지 않음 — 확률을 말하지 말 것\n"
            )
        base = f" (평소 {f.baseline_up_rate:.0%})" if f.baseline_up_rate is not None else ""
        ci = f", 95% 구간 {f.ci_low:.0%}~{f.ci_high:.0%}" if f.ci_low is not None else ""
        return (
            f"- 근거 [2] 과거 통계: 같은 신호가 났던 과거 {f.sample_size}건 중"
            f" {f.up_rate:.0%}가 상승{base}{ci}."
            " 이는 과거 빈도일 뿐 미래 확률이 아니며, 단정적으로 말하지 말 것\n"
        )

    @classmethod
    def _format_stock_context(
        cls,
        prompt: str,
        r: StockAnalysisResult,
        hits: list[NewsHit] | None = None,
        forecast: StockForecastSummary | None = None,
        value_notes: list[str] | None = None,
        profile: UserProfileSummary | None = None,
        keywords: list[NewsKeyword] | None = None,
    ) -> str:
        headlines = "\n".join(f"- {h}" for h in r.headlines) if r.headlines else "- (없음)"
        unit = cls._currency_unit(r.symbol)
        # 근거 번호는 고정 배정(블록 없으면 결번) — [1] 시세·지표, [2] 과거 통계,
        # [3] 가치·체력, [4] 뉴스 감성·헤드라인, [5]부터 관련 뉴스 개별.
        # '근거 [n]' 표기가 인용 마커의 단일 정의처 — 채점기(eval_scorer)가 같은 패턴을 읽는다.
        lines = (
            f"사용자 질문: {prompt}\n\n"
            f"[{r.symbol} 분석 데이터] — 근거 [1]"
            f" (가격 단위는 모두 {unit} — 다른 통화로 바꿔 쓰지 말 것)\n"
            f"- 현재가: {cls._price_text(r.price, unit)}\n"
            f"- 방향 신호: {r.direction} (확신도 {r.confidence:.2f})\n"
            f"- RSI(14): {r.rsi:.1f} (30↓ 과매도 / 70↑ 과매수)\n"
            f"- 20일 이동평균: {cls._price_text(r.ma20, unit)}"
            f" / 50일 이동평균: {cls._price_text(r.ma50, unit)}\n"
            f"- 지지선: {cls._price_text(r.support, unit)}"
            f" / 저항선: {cls._price_text(r.resistance, unit)}"
            f" (최근 60거래일 저/고점)\n"
            f"- 현재가 위치: {cls._price_position_text(r.price, r.support, r.resistance)}\n"
            f"- 변동성: {cls._volatility_text(r.atr_pct)}\n"
            f"- 볼린저 밴드: {cls._bollinger_text(r.bb_percent_b)}\n"
            f"- 거래량·수급: {cls._volume_text(r.volume_ratio, r.obv_slope)}\n"
            f"- 중장기 추세: {cls._momentum_text(r.momentum_12_1)}\n"
        )
        lines += cls._volume_profile_text(r, unit)
        if r.reference_up_signal:
            # 신호 없음(False)은 라인 자체를 생략 — 소형 모델이 '신호 부재'를 부정 신호로 오독하는 것 차단
            lines += (
                "- 참고 신호: 백테스트 검증(인샘플·홀드아웃 통과)된 '과매도+볼린저 하단' 조건 충족"
                " — 통계적 참고일 뿐 상승 확률이나 매수 근거가 아님\n"
            )
        lines += cls._forecast_text(forecast)
        if value_notes:
            # 가치·체력(펀더멘털) — 예전엔 카드에만 실려 본문이 "싼가/튼튼한가"를 말하지 못했다.
            lines += "- 근거 [3] 가치·체력(펀더멘털):\n"
            lines += "".join(f"  - {n}\n" for n in value_notes)
        if profile is not None:
            # 개인화는 서술의 강조점까지다 — 프로파일을 근거로 한 매매 권유는
            # 투자자문 경계를 넘으므로 규칙을 컨텍스트에 함께 싣는다.
            lines += (
                f"- 질문자 투자 프로파일(참고): {profile.risk_label} · {profile.debt_label}"
                f" · {profile.horizon_label}\n"
                "  → 서술의 강조점만 조정할 것(안정 성향이면 변동성·리스크 지표를 먼저,"
                " 공격 성향이면 추세·모멘텀을 먼저). 프로파일을 이유로 매수/매도 권유나"
                " 특정 상품 추천을 하지 말 것\n"
            )
        if keywords:
            # 영향 키워드(B2) — 헤드라인 단어 빈도라는 관측 팩트. 방향 표기는 동반 감성
            # 라벨 평균이 뚜렷할 때만(±0.15) — 없는 방향을 만들지 않는다.
            parts = []
            for k in keywords:
                tone = ""
                if k.sentiment_avg is not None and k.sentiment_avg > 0.15:
                    tone = "·호재쪽"
                elif k.sentiment_avg is not None and k.sentiment_avg < -0.15:
                    tone = "·악재쪽"
                parts.append(f"{k.keyword}({k.count}건{tone})")
            lines += (
                "- 영향 키워드(근거 [4], 최근 헤드라인 단어 빈도 — 예측 아님): "
                + " · ".join(parts) + "\n"
            )
        lines += (
            f"- 근거 [4] 뉴스 감성: {r.sentiment:+.2f} ({r.sentiment_label})"
            f"\n- 최근 헤드라인(근거 [4]):\n{headlines}"
        )
        related = [h for h in (hits or []) if h.title not in r.headlines]  # 헤드라인과 제목 중복 제거
        if related:
            lines += "\n- 관련 뉴스(감성 라벨):"
            for i, h in enumerate(related, start=5):
                date_text = f"{h.published_at:%Y-%m-%d}" if h.published_at else "날짜 미상"
                if h.sentiment is None:
                    label_text = "감성 라벨 없음"
                else:
                    direction = "호재" if h.sentiment > 0 else "악재" if h.sentiment < 0 else "중립"
                    label_text = f"감성 {h.sentiment:+.1f}({direction})·{h.event_type or '기타'}"
                lines += f"\n  - 근거 [{i}] ({date_text} | {label_text}) {h.title}"
        return lines

    async def list_conversations(self, user_id: int, limit: int = 30) -> list[ConversationSummary]:
        return await self._conversations.list_conversations(user_id, limit)

    async def conversation_messages(self, conversation_id: int, user_id: int) -> list[Message]:
        conversation = await self._conversations.get_conversation(conversation_id)
        # 미존재와 남의 대화를 구분하지 않는다(존재 여부 비노출). user_id 없는 구버전 대화는 허용.
        if conversation is None or conversation.user_id not in (None, user_id):
            raise ConversationNotFoundError(f"대화를 찾지 못했습니다: {conversation_id}")
        return await self._conversations.get_messages(conversation_id, limit=100)

    async def stream_reply(
        self, prompt: str, conversation_id: int | None = None, user_id: int | None = None,
    ):
        if conversation_id is None:
            conversation_id = (await self._conversations.create_conversation(user_id=user_id)).id
        yield {"type": "meta", "conversationId": conversation_id}

        history = await self._conversations.get_messages(conversation_id)
        await self._conversations.add_message(conversation_id, "user", prompt)
        hist_msgs = [{"role": m.role, "content": m.content} for m in history[-8:]]

        parts: list[str] = []
        # 대화 스트리밍(최종 사용자 답변) → 오케스트레이터 기본 모델(7.8B)
        async for chunk in llm_orchestrator.orchestrate_stream(
            prompt, system=STREAM_SYSTEM_PROMPT, history=hist_msgs,
        ):
            parts.append(chunk)
            yield {"type": "delta", "text": chunk}

        await self._conversations.add_message(conversation_id, "assistant", "".join(parts))
        yield {"type": "done"}
