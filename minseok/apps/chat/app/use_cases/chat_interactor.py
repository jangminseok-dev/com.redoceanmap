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
    NoValidAreaError,
)
from chat.app.dtos.area_stat_dto import AreaStatDto
from chat.app.ports.input.chat_use_case import ChatUseCase
from chat.app.ports.output.conversation_repository import ConversationRepository
from chat.domain.entities.conversation_entity import ConversationSummary, Message
from chat.domain.services.verdict import strength as verdict_strength
from chat.domain.services.verdict import verdict as verdict_headline
from core.llm.llm_orchestrator import llm_orchestrator
from hub.app.dtos.commercial_data_dto import (
    AreaInfo,
    AreaInsight,
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
from hub.app.ports.output.fundamental_read_port import FundamentalReadPort
from hub.app.ports.output.stock_analysis_port import StockAnalysisPort, StockAnalysisUnavailable
from hub.app.ports.output.stock_forecast_port import StockForecastPort
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
- 질문이 "작년 대비"·"성장"·"매출 오른"을 물으면 '매출전년동분기대비(%)' 열이 큰 상권을 우선 선택 ('-'는 산출 불가)"""

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
DEICTIC_TOKENS = (
    "그 중", "그중", "거기", "그곳", "방금", "아까", "그 상권", "그 동네", "이 중",
)


def _has_deixis(prompt: str) -> bool:
    return any(token in prompt for token in DEICTIC_TOKENS)


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
    ) -> None:
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

    def _history_block(self, history: list[Message]) -> str:
        if not history:
            return ""
        turns = "\n".join(f"{m.role}: {m.content[:200]}" for m in history[-6:])
        return f"이전 대화(맥락 참고용):\n{turns}\n\n"

    @staticmethod
    def _place_stem(name: str) -> str:
        """지명 어간 — 선행 한글 구간에서 행정 접미(구·동·가·로 등)를 뗀다 (예: 성수1가1동 → 성수)."""
        match = re.match(r"^[가-힣]+", name or "")
        stem = match.group() if match else ""
        while len(stem) > 2 and stem[-1] in "구동가로읍면리":
            stem = stem[:-1]
        return stem

    def _mentioned_codes(self, summary: AreaSummary, prompt: str) -> set[int]:
        """질문에 지역(자치구·행정동·상권명 어간)이 언급된 상권 코드 집합."""
        codes: set[int] = set()
        for a in summary.areas:
            for name in (a.district_name, a.adm_dong_name, a.trdar_name):
                stem = self._place_stem(name)
                # "건대입구역"은 "건대입구 쪽"과 어긋난다(첫 재측정 실측) — '역'을 뗀
                # 변형도 본다. 단 뗀 결과가 3자 이상일 때만: "서울역→서울"처럼 흔한
                # 지명이 되면 서울이 들어간 모든 질문에 걸린다.
                variants = {stem}
                if stem.endswith("역") and len(stem) >= 4:
                    variants.add(stem[:-1])
                if any(len(v) >= 2 and v in prompt for v in variants):
                    codes.add(a.trdar_code)
                    break
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
            recs = (m.payload or {}).get("recommendations")
            if not recs:
                continue
            codes = [int(r["id"]) for r in recs if str(r.get("id", "")).isdigit()]
            valid = [c for c in codes if c in area_map]
            if valid:
                return valid
        return []

    def _build_area_context(
        self, summary: AreaSummary, prompt: str = "", limit: int = 80
    ) -> str:
        # 상권 1650개 전체를 넣으면 모델 컨텍스트를 초과한다.
        # 질문에 언급된 지역(자치구·행정동·상권명 어간)을 우선 포함하고,
        # 나머지는 월매출 상위로 상한까지 채운다. 언급 상권은 ★로 표시해 phase1 선택을 유도한다.
        def sales_of(a) -> int:
            return summary.sales_by_code.get(a.trdar_code) or 0

        all_mentioned = self._mentioned_codes(summary, prompt)
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
        lines = ["상권코드|상권명|자치구|행정동|상권전체월매출합계(만원)|매출전년동분기대비(%)|질문지역"]
        for a in picked:
            sales = summary.sales_by_code.get(a.trdar_code)
            wan = round(sales / 10000) if sales else None
            yoy = summary.yoy_by_code.get(a.trdar_code)
            lines.append(
                f"{a.trdar_code}|{a.trdar_name}|{a.district_name}|{a.adm_dong_name}"
                f"|{wan if wan is not None else '데이터없음'}"
                f"|{f'{yoy:+.1f}' if yoy is not None else '-'}"
                f"|{'★' if a.trdar_code in mentioned_codes else ''}"
            )
        return "\n".join(lines)

    def _format_stats(
        self, raw_stats: dict[int, AreaRawStat], quarter: int,
    ) -> dict[int, AreaStatDto]:
        quarter_label = f"{str(quarter)[:4]}년 {str(quarter)[4]}분기"

        result: dict[int, AreaStatDto] = {}
        for code, raw in raw_stats.items():
            has_data = raw.has_sales or raw.has_store or raw.has_fp

            if raw.has_sales and raw.has_store and raw.store_count and raw.store_count > 0:
                sales_wan = round(raw.monthly_sales_amount / 10000)
                per_store_wan = round(sales_wan / raw.store_count)
                revenue_text = f"점포당 월평균 {per_store_wan:,}만원"
                revenue_source = f"업종 월 총매출 {sales_wan / 10000:.1f}억원 ÷ {raw.store_count}개 점포로 계산"
            elif raw.has_sales:
                sales_wan = round(raw.monthly_sales_amount / 10000)
                revenue_text = f"업종 월 총매출 {sales_wan:,}만원 (점포수 미집계)"
                revenue_source = "점포당 매출 계산 불가 (점포수 데이터 없음)"
            else:
                revenue_text = "매출 데이터 없음"
                revenue_source = "해당 분기 데이터 미수집"

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
                op_text = (
                    f"이 상권 평균 {op_months}개월 영업 (지역 평균 {region_op}개월)"
                    if op_months else "데이터 없음"
                )
                # 생존 중 점포의 영업개월만으론 "얼마 만에 닫는가"를 알 수 없다.
                if raw.closure_months_avg:
                    op_text += (
                        f", 폐업 점포는 평균 {raw.closure_months_avg}개월 만에 닫음"
                        f" (지역 평균 {raw.region_closure_months_avg}개월)"
                    )
            else:
                change_text = "데이터 없음"
                op_text = "데이터 없음"

            result[code] = {
                "revenue_text": revenue_text,
                "revenue_source": revenue_source,
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

        # phase0(의도 분류 = 도메인 판단) — 단일 모델(7.8B) 정책
        self._notify(on_stage, "intent", "질문 의도를 파악하고 있어요")
        intent, stock_query = await self._classify_intent(prompt, history)
        # 프로파일은 데이터 근거 서술(stock·market)에만 주입한다 — 미작성·실패는 None(무손상)
        profile = await self._load_profile(user_id) if intent in ("stock", "market") else None
        if intent == "stock":
            return await self._answer_stock(conversation_id, prompt, stock_query, on_stage, profile)
        if intent == "market_news":
            return await self._answer_market_news(conversation_id, prompt, on_stage)
        if intent == "general":
            self._notify(on_stage, "answer", "답변을 만들고 있어요")
            return await self._answer_general(conversation_id, prompt)

        summary = await self._market.get_area_summary()
        quarter = summary.latest_quarter
        if not quarter:
            raise CommercialDataUnavailableError("상권 데이터가 없습니다.")

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

        # 반경 질의 가드(I-10) — 중심 상권을 좌표로 특정할 수 있으면 반경 안 상권 집합을
        # 만들어 phase1 결과를 자르고, 못 하면 "미적용"을 답변 문두에 결정론으로 명시한다.
        radius_m = self._parse_radius_m(prompt)
        radius_codes: set[int] | None = None
        radius_note = ""
        if radius_m is not None:
            center = self._radius_center(summary, prompt)
            if center is None:
                radius_note = (
                    f"※ 반경 {radius_m:,}m 조건은 기준 지점을 좌표로 특정하지 못해 적용하지"
                    " 못했어요. 아래 추천은 지역명 기준이에요.\n\n"
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
        area_context = self._build_area_context(summary, prompt)

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
        trdar_codes: list[int] = [int(c) for c in p1.get("trdar_codes", []) if str(c).isdigit()]
        valid_codes = [c for c in trdar_codes if c in area_map]

        # 결정론적 지역 가드 — 질문에 지역이 언급되면 그 지역 상권으로 보정.
        # 모델이 ★ 지시를 무시하고 유명 상권(홍대 등)으로 쏠리는 경우를 코드로 방지한다.
        mentioned_codes = self._mentioned_codes(summary, prompt)
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
            if previous and _has_deixis(prompt):
                # 지시어 후속 질문("그 중에서/거기") — 직전 추천으로 후보를 **제한**한다.
                # 첫 baseline 실측: 이 케이스에서 모델이 10건 전부 이웃 상권을 섞었다(집중률 0%).
                # "그 중"이라 물었는데 새 후보를 더하는 건 오답이므로 코드로 자른다.
                kept = [c for c in valid_codes if c in previous]
                valid_codes = kept or previous
            elif not valid_codes:
                # 지역 미언급 후속 질문 — 직전 추천 상권을 이어받아 맥락을 유지한다.
                # (phase1 LLM이 이전 대화에서 상권을 못 이어받아 후보가 빈 경우만 보정)
                valid_codes = previous
        if radius_codes is not None:
            # 지역·지시어 가드를 거친 후보를 반경으로 자른다. 반경 안 후보가 하나도 없으면
            # 반경 안 매출 상위로 대체한다(중심 상권 자신이 항상 포함되므로 공집합이 아니다).
            kept = [c for c in valid_codes if c in radius_codes]
            valid_codes = kept or sorted(
                radius_codes, key=lambda c: summary.sales_by_code.get(c) or 0, reverse=True,
            )[:3]
        if not valid_codes:
            raise NoValidAreaError("유효한 상권을 찾지 못했습니다.")
        # 분량 상한 — 가드를 **전부 통과한 뒤**에 자른다. 앞에서 자르면 지역·지시어·반경 가드가
        # 되돌리려던 상권이 이미 사라져 region_hit_rate가 깎인다.
        valid_codes = valid_codes[:MAX_AREAS]

        self._notify(on_stage, "data", "공공데이터를 분석하고 있어요")
        raw_stats = await self._market.get_area_raw_stats(valid_codes, service_code, quarter)
        real_stats = self._format_stats(raw_stats, quarter)
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
        stats_context_lines = [f"사용자 질문: {prompt}\n업종: {service_name}\n기준: {quarter_label}\n"]
        for code in valid_codes:
            area = area_map[code]
            st = real_stats.get(code, {})
            score = area_scores.get(code)
            score_line = f"- 서울 평균 대비: {self._score_text(score)}\n" if score else ""
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
                f"{score_line}{permit_line}{insight_line}"
            )
        if area_articles:
            stats_context_lines.append(self._format_area_articles(area_articles))
        if profile is not None:
            stats_context_lines.append(self._profile_market_block(profile))

        # phase2(최종 서술 = 최종 사용자 답변) → 오케스트레이터 기본 모델(7.8B)
        self._notify(on_stage, "narrate", "추천 이유를 정리하고 있어요")
        try:
            p2 = await self._orchestrate_json(
                f"{PHASE2_PROMPT}\n\n" + "\n".join(stats_context_lines), "Phase2",
            )
        except Exception:
            logger.error("[chat] Phase2 파싱 실패(재시도 포함)")
            raise InvalidLLMResponseError("AI 서술 생성 실패")

        # 모델이 trdar_code를 문자열("3110131")로 되돌리는 일이 잦다 — int로 정규화하지
        # 않으면 조회가 전부 빗나가 reason이 빈 채 나간다(3차 실측: reason 69%가 빈 문자열).
        reason_map = {
            int(item["trdar_code"]): item["reason"]
            for item in p2.get("areas", [])
            if str(item.get("trdar_code", "")).isdigit()
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

        text = radius_note + p2.get("text", "")
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
            " 특정 상권이 이 예산으로 가능하다고 단정하지 말 것(임대료·권리금 데이터 없음)"
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

    async def _classify_intent(self, prompt: str, history: list[Message]) -> tuple[str, str]:
        try:
            parsed = await self._orchestrate_json(
                f"{INTENT_PROMPT}\n\n{self._history_block(history)}사용자 질문: {prompt}",
                "의도 분류",
            )
        except Exception:
            logger.warning("[chat] 의도 분류 파싱 실패(재시도 포함) → market 폴백")
            return "market", ""
        stock_query = str(parsed.get("stock_query") or "").strip()
        intent = parsed.get("intent")
        if intent == "stock" and stock_query:
            return "stock", stock_query
        if intent == "stock":
            # 종목 추출 실패 — 상권으로 보내던 기존 오답 대신 뉴스 RAG가 차선
            return "market_news", ""
        if intent == "market_news":
            return "market_news", ""
        if intent == "general":
            return "general", ""
        return "market", ""  # 미지 라벨 포함 전부 market — 기존 동작 보존

    async def _answer_general(self, conversation_id: int, prompt: str) -> AskResponse:
        """상권/주식과 무관한 일반 질문 — 허브 GeminiAnswerPort(외부 Gemini API)로 답변."""
        try:
            text = (await self._gemini.generate(prompt)).answer
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

    async def _answer_stock(
        self, conversation_id: int, prompt: str, stock_query: str, on_stage=None,
        profile: UserProfileSummary | None = None,
    ) -> AskResponse:
        self._notify(on_stage, "analyze", "종목 지표를 분석하고 있어요")
        try:
            analysis = await self._stocks.analyze(stock_query)
        except StockAnalysisUnavailable as e:
            text = f"{e.detail} 정확한 종목명이나 티커로 다시 물어봐 주세요."
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

        # 결론 한 줄 — 페이지 히어로와 같은 verdict 로직으로 서버가 계산해 카드에 싣는다.
        headline, _detail = verdict_headline(analysis.direction, forecast)
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
        """상권 종합점수 의미 해석 문장 — 성장 컴포넌트는 상권/서울 QoQ를 병기한다."""
        parts = []
        for c in score.components:
            if c.key in ("sales_growth", "floating_growth"):
                parts.append(
                    f"{c.name} {c.score}점(상권 {c.value:+.1f}% vs 서울 {c.benchmark:+.1f}%)"
                )
            else:
                parts.append(f"{c.name} {c.score}점")
        return f"종합 {score.total}점·{score.grade} (50점=서울 평균 수준) — " + ", ".join(parts)

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
            f"- 거래 밀집 구간: {r.volume_poc_low:,.2f}~{r.volume_poc_high:,.2f}{unit}"
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
        lo = f"{support:,.2f}{unit}"
        hi = f"{resistance:,.2f}{unit}"
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
            f"- 현재가: {r.price:,.2f}{unit}\n"
            f"- 방향 신호: {r.direction} (확신도 {r.confidence:.2f})\n"
            f"- RSI(14): {r.rsi:.1f} (30↓ 과매도 / 70↑ 과매수)\n"
            f"- 20일 이동평균: {r.ma20:,.2f}{unit} / 50일 이동평균: {r.ma50:,.2f}{unit}\n"
            f"- 지지선: {r.support:,.2f}{unit} / 저항선: {r.resistance:,.2f}{unit}"
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
