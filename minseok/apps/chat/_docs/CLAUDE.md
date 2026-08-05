# CLAUDE.md — chat 앱

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]]

**대화형 분석 어시스턴트**(ChatGPT·Gemini·Claude 형). 사용자와 멀티턴으로 소통하며
상권 데이터에 근거한 창업/입지 추천과 주식 분석(허브 경유)을 답한다.

---

## 데이터 접근 — 허브 포트만 사용

chat은 다른 스포크를 **직접 import하지 않는다**. 허브 `hub`가 공개한 포트
(→ hub CLAUDE)만 의존하고, 구현은 각 스포크가 제공,
`main.py`가 주입한다(스타 토폴로지).

| 포트 | 구현 스포크 | 용도 |
|------|------------|------|
| `CommercialDataPort` | market (`CommercialDataGateway`) | 상권 데이터 조회 |
| `RecommendationRecordPort` | recommendation (`RecommendationRecordGateway`) | 추천 기록 |
| `StockAnalysisPort` | stock (`StockAnalysisGateway`) | 주식 분석 |
| `NewsSearchPort` | stock (`NewsSearchGateway`) | 수집 뉴스 의미 검색(RAG, bge-m3+pgvector) |
| `MarketNewsSearchPort` | market (`MarketNewsSearchGateway`) | 상권 뉴스 의미 검색(지역 기사 근거) |
| `GeminiAnswerPort` | hub 자체 구현 (`GeminiApiAdapter`) | 일반 질문(general) 외부 Gemini 답변 |

## 의도 라우팅 — phase0 (4분류)

`ask()`는 먼저 질문 의도를 분류한다(EXAONE 7.8B — 단일 모델 정책):
- **`stock`** — 특정 종목 질문. 종목 질의를 추출(한국 종목명 그대로, 해외는 티커 정규화:
  테슬라 → TSLA)해 허브 `StockAnalysisPort`로 분석 + `NewsSearchPort`로 해당 종목 뉴스를
  의미 검색(감성 라벨 동반)해 7.8B가 서술한다(text + `stock` 카드). 컨텍스트에는 지표 원값과
  함께 **의미 해석 문장**(변동성/볼린저 %B/거래량·수급/12-1 모멘텀 — `_format_stats` 스타일
  헬퍼 4종)을 주입하고, 백테스트 검증 참고 신호(`reference_up_signal`)는 **True일 때만** 언급
  (False면 라인 생략 — 소형 모델 오독 차단).
  **과거 통계(forecast)와 가치·체력(펀더멘털)도 서술 컨텍스트에 들어간다**(2026-07-27) —
  예전엔 답변을 만든 뒤에 조회해 카드에만 실렸고, 본문이 밸류에이션·통계를 근거로 말하지
  못했다. 과거 통계는 `ready=False`(표본 미달)면 **수치를 아예 주지 않는다**(확률 단정 금지 유지).
- **`market_news`** — 종목 무관 업종·시장 동향 질문("반도체 업황 어때?"). `NewsSearchPort`로
  코퍼스 횡단 의미 검색(limit 8) → 발행일·감성 라벨 병기 컨텍스트 → 7.8B 서술.
  검색 히트는 **뉴스 근거 카드**(`AskResponse.news`, `NewsCardItem`)로 응답·payload에 동반
  (프론트 렌더링·히스토리 복원). 히트 없으면 데이터 부재 안내(열화 동작, 카드·payload 없음).
- **`market`** — 상권/창업 질문. 기존 2단계 추론(무손상). phase2 컨텍스트에 상권별
  **서울 평균 대비 종합점수**(허브 `get_area_scores`, M3 스코어링)를 의미 해석 문장
  (`_score_text` — 성장 컴포넌트는 상권/서울 QoQ 병기)으로 주입, 산출 불가 상권은 라인 생략.
  추가로 **관련 지역 기사**(허브 `MarketNewsSearchPort`, 상권 뉴스 RAG)를 발행일·지역 병기
  블록으로 주입 — 히트 없으면 블록 생략(열화 동작).
  **인허가 업소 교체**(허브 `get_area_permit_churn` — 최근 12개월 개업·폐업·영업중 수)도
  한 줄로 주입한다(2026-08-05). 분기 팩트가 "얼마나 있나"만 답하는 자리에 "지금 늘고 있나"를
  더한다. 인허가가 붙은 업소가 없는 상권은 라인 생략(열화 동작). 프롬프트가 **영업중 수를
  점포 수와 비교·검산하는 것을 금지**한다 — 출처가 달라 어느 쪽이 맞다고 말할 수 없다.
  **상권 성격**(허브 `get_area_insights` — 고객층·배후 수요·소비력·객단가)도 주입한다.
  서술자가 최대 9문장을 만들지만 프롬프트 예산상 `_INSIGHT_PRIORITY` 순 **상위 4개만**
  쓴다(오피스형/주거형 → 객단가 → 연령 → 피크). 문장 없는 상권은 라인 생략.
- **`general`** — 상권/주식과 무관한 질문(인사·상식·인물 등). 허브 `GeminiAnswerPort`
  (외부 Gemini API)로 답변. Gemini 실패 시 안내 문구로 열화(500 방지).
분류 파싱 실패·미지 라벨 → market 폴백(기존 동일), stock인데 종목 추출 실패 → market_news.
주식 서술 규칙: 매수/매도 지시·확률 단정 금지, 책임 고지 포함(백테스트 결론 — 확률 근거 부족).

## 추천 기록 — 허브 포트 경유

`ask()`는 phase2 추천을 만든 뒤 허브 `RecommendationRecordPort`(구현: recommendation의
`RecommendationRecordGateway`)로 기록한다. recommendation을 직접 import하지 않고
허브 포트만 의존한다(스타 토폴로지). `stream_reply()`는 구조화 추천이 없어 기록하지 않는다.

## 단계별 추론 — 모델 계층 분리

| 단계 | 역할 | 모델 |
|------|------|------|
| **phase0** | 의도 분류(상권 vs 주식) + 종목 질의 추출 | EXAONE **7.8B** |
| **phase1** | 질문 → 업종 코드 + 후보 상권 선택 (도메인 판단) | EXAONE **7.8B** |
| **phase2** | 후보의 원시 통계 → 최종 서술·추천 (**최종 사용자 답변**) | EXAONE **7.8B** (오케스트레이터 기본) |

- 두 단계 모두 `orchestrate(..., format="json")`으로 유효 JSON 출력을 강제한다(소형 모델 견고화).
- `_build_area_context`는 1650개 상권 전체 대신 **질문에 언급된 자치구 우선 + 월매출 상위 80개**로
  상한을 둔다(모델 컨텍스트 초과 방지).
- 모델 계층 바인딩 원칙 상세 → hub CLAUDE / 오케스트레이터.

## 멀티턴 · 스트리밍

- `conversations` / `messages` 테이블로 대화 맥락 보존. `ask(prompt, conversation_id)`가
  직전 대화를 phase1 컨텍스트에 주입한다("그 중 …" 같은 지시 해소).
- `POST /chat/stream` — SSE(`text/event-stream`)로 `meta → delta* → done` 스트리밍.

## 대화 히스토리 (프론트 지난 대화)

- `conversations.user_id`(nullable, FK 없음 — auth와 DB 결합 회피)로 소유자를 기록하고,
  답변의 구조화 카드는 `messages.payload`(JSONB)로 동반 저장한다 — 재진입 시 카드 복원용.
  카드는 추천 상권(`recommendations`)·종목(`stock`)·뉴스 근거(`news`) 3종.
  텍스트만인 답변(뉴스 히트 없는 market_news 등)은 NULL.
- `GET /chat/conversations?limit=` — 내 대화 목록(최신순, 제목=첫 user 메시지 40자).
- `GET /chat/conversations/{id}/messages` — 메시지 전체(payload 포함). 미존재와 남의 대화는
  같은 404(존재 비노출), user_id NULL인 구버전 대화는 인증 사용자에게 허용.

## 레이어

```
apps/chat/
├── app/use_cases/chat_interactor.py   # 대장 — 허브 포트 소비 + 2단계 오케스트레이션
├── adapter/outbound/
│   ├── orm/conversation_orm.py        # conversations · messages (user_id · payload)
│   └── pg/conversation_pg_repository.py
├── adapter/inbound/api/v1/chat_router.py  # /chat/ask · /chat/stream · /chat/conversations*
└── dependencies/chat_provider.py
```
