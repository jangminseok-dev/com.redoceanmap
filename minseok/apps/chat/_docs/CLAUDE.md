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
| `UserProfilePort` | recommendation (`UserProfileGateway`) | 투자·창업 프로파일(개인화 ⓪ — 서술 관점 조정) |
| `AreaFinancePort` | market (`AreaFinanceGateway`) | 창업 재무 계산(BEP·부족 자금·runway) — 첫 줄은 코드 |
| `AreaFitnessPort` | market (`AreaFitnessGateway`) | 입지 적합도(업종×상권 4축·진단·객단가) — 비교표 전용(2026-09-17) |
| `AreaBacktestReportPort` | market (`AreaBacktestReportGateway`) | 상권 점수 백테스트 리포트(등급별 t+1 실측·컴포넌트 예측력) — 비교표 전용 |
| `AreaGraphPort` | market (`AreaGraphNeo4jAdapter`) | Neo4j 투영 관계(행정 계층·같은 동 상권·업종 연결·기사 연결) — 비교표 전용, 그래프 장애 시 행만 비움 |

## 의도 라우팅 — phase0 (4분류)

`ask()`는 먼저 질문 의도를 분류한다(EXAONE 7.8B — 단일 모델 정책):
- **`stock`** — 특정 종목 질문. 종목 질의를 추출(한국 종목명 그대로, 해외는 티커 정규화:
  테슬라 → TSLA)해 허브 `StockAnalysisPort`로 분석 + `NewsSearchPort`로 해당 종목 뉴스를
  의미 검색(감성 라벨 동반)해 7.8B가 서술한다(text + `stock` 카드). 컨텍스트에는 지표 원값과
  함께 **의미 해석 문장**(변동성/볼린저 %B/거래량·수급/12-1 모멘텀 — `_format_stats` 스타일
  헬퍼 4종)을 주입하고, 백테스트 검증 참고 신호(`reference_up_signal`)는 **True일 때만** 언급
  (False면 라인 생략 — 소형 모델 오독 차단).
  **매물대**(거래 밀집 구간 — 허브 `StockAnalysisResult.volume_poc_*`)도 한 줄 주입한다
  (2026-08-05). 프론트 차트가 그리던 것과 **같은 계산**(stock `volume_profile` 도메인 서비스가
  `volumeProfile.ts`를 이식)이라 사용자가 화면에서 본 구간과 값이 같다. 산출 불가(표본 부족·
  가격 범위 없음)면 라인 생략. 프롬프트가 **지지선·저항선으로 바꿔 부르는 것을 금지**한다 —
  바로 위에 출처가 다른 지지선/저항선이 있어 섞이면 둘 다 신뢰를 잃는다.
  **과거 통계(forecast)와 가치·체력(펀더멘털)도 서술 컨텍스트에 들어간다**(2026-07-27) —
  예전엔 답변을 만든 뒤에 조회해 카드에만 실렸고, 본문이 밸류에이션·통계를 근거로 말하지
  못했다. 과거 통계는 `ready=False`(표본 미달)면 **수치를 아예 주지 않는다**(확률 단정 금지 유지).
- **`market_news`** — 종목 무관 업종·시장 동향 질문("반도체 업황 어때?"). `NewsSearchPort`로
  코퍼스 횡단 의미 검색(limit 8) → 발행일·감성 라벨 병기 컨텍스트 → 7.8B 서술.
  검색 히트는 **뉴스 근거 카드**(`AskResponse.news`, `NewsCardItem`)로 응답·payload에 동반
  (프론트 렌더링·히스토리 복원). 히트 없으면 데이터 부재 안내(열화 동작, 카드·payload 없음).
- **`market`** — 상권/창업 질문. 기존 2단계 추론(무손상). phase2 컨텍스트에 상권별
  **서울 중앙 상권 대비 종합점수 v2**(허브 `get_area_scores` — 향후 1년 폐업률을 가르는 3축)를 의미 해석 문장
  (`_score_text` — 컴포넌트마다 상권 실측치 vs 서울 중앙값을 단위와 함께 병기)으로 주입, 산출 불가 상권은 라인 생략.
  추가로 **관련 지역 기사**(허브 `MarketNewsSearchPort`, 상권 뉴스 RAG)를 발행일·지역 병기
  블록으로 주입 — 히트 없으면 블록 생략(열화 동작).
  **인허가 업소 교체**(허브 `get_area_permit_churn` — 최근 12개월 개업·폐업·영업중 수)도
  한 줄로 주입한다(2026-08-05). 분기 팩트가 "얼마나 있나"만 답하는 자리에 "지금 늘고 있나"를
  더한다. 인허가가 붙은 업소가 없는 상권은 라인 생략(열화 동작). 프롬프트가 **영업중 수를
  점포 수와 비교·검산하는 것을 금지**한다 — 출처가 달라 어느 쪽이 맞다고 말할 수 없다.
  **상권 성격**(허브 `get_area_insights` — 고객층·배후 수요·소비력·객단가)도 주입한다.
  서술자가 최대 9문장을 만들지만 프롬프트 예산상 `_INSIGHT_PRIORITY` 순 **상위 4개만**
  쓴다(오피스형/주거형 → 객단가 → 연령 → 피크). 문장 없는 상권은 라인 생략.
  **재무 질문**(자기자본·보증금·월세·대출·버틸·손익 어휘 또는 라벨 금액 2개 이상)이면 1순위 상권·확정 업종으로
  허브 `AreaFinancePort`를 불러 **첫 줄을 코드가 쓴다**(값·출처 병기). 입력은 결정론 파서
  (`domain/services/amount_parser.py`) → 직전 finance 카드 승계 → 프로파일 예산 밴드(자기자본만) 순으로 채우고,
  자기자본이 끝내 없을 때만 되묻는다. phase2 컨텍스트에 `[재무 계산 — 코드가 정함]` 블록 + 재계산·대출 권유 금지 규칙.
  카드 payload `finance`가 다음 턴 승계 키다. 포트가 배선되면 임대료 미지원 고지(I-12)는 붙지 않는다.
- **`general`** — 상권/주식과 무관한 질문(인사·상식·인물 등). 허브 `GeminiAnswerPort`
  (외부 Gemini API)로 답변. Gemini 실패 시 안내 문구로 열화(500 방지).
분류 파싱 실패·미지 라벨 → market 폴백(기존 동일), stock인데 종목 추출 실패 → market_news.
주식 서술 규칙: 매수/매도 지시·확률 단정 금지, 책임 고지 포함(백테스트 결론 — 확률 근거 부족).

**출처 인용(R4, 2026-08-23)**: stock·market_news 컨텍스트의 근거 블록에 `근거 [n]` 번호를
부여하고(stock은 고정 배정 — [1] 시세·지표 / [2] 과거 통계 / [3] 가치·체력 / [4] 감성·헤드라인 /
[5]+ 관련 뉴스, 결번 허용) 프롬프트가 수치·사실 문장 말미 `[n]` 마커를 의무화한다(고지 제외).
`근거 [n]` 표기가 단일 정의처 — `eval_scorer`가 같은 패턴으로 `citation_coverage`를 재고
없는 번호 인용은 `dangling_citation` 절대 규칙으로 잡는다. 프론트는 마커를 배지로 렌더하고
근거 뉴스 목록에 같은 번호를 병기한다. phase2(market)는 미도입 — 기사 근거가 카드로
노출되지 않아 앵커 불성립(ROADMAP R4 판정).

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
- **지시어 가드(2026-08-05)** — 질문에 지시어(`DEICTIC_TOKENS`: "그 중"·"거기"·"방금" 등)가
  있고 직전 추천 payload가 있으면 phase1이 무엇을 골랐든 **직전 추천으로 후보를 제한**한다.
  첫 baseline 실측에서 "그 중에서" 질문 10건 전부 모델이 이웃 상권을 섞었다(집중률 0%) —
  프롬프트 부탁이 아니라 코드로 자른다. 지역명이 함께 언급되면 지역 가드가 우선.
- `POST /chat/stream` — SSE(`text/event-stream`)로 `meta → delta* → done` 스트리밍.
- `POST /chat/ask/progress`(2026-08-05) — `/ask`와 같은 일을 하되 **진행 단계를 SSE로**
  흘린다(`stage`* → `result`|`error`). phase 왕복(p95 실측 ~1.5분) 동안 화면이 침묵하지
  않게 하는 표면 — 인터랙터는 `on_stage` 콜백(선택 인자)만 안다(통지 실패는 삼킴).
  오류도 본문 이벤트로 전달(SSE는 이미 200). 프론트 ROM 1.0 경로가 이걸 소비한다.

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

## 답변 후처리 가드 (2026-08-28)

절대 규칙은 **프롬프트가 아니라 코드가** 지킨다 — `domain/services/answer_guard.py`.
골든셋 실측에서 위반 13건이 나왔는데(유령 인용 11 · 고지 누락 2) 두 규칙 모두
`STOCK_ANSWER_PROMPT`에 이미 적혀 있었다. 7.8B가 안 지킨 것이라 문구를 더 써도 못 막는다.

- `allowed_citations(context)` — 컨텍스트의 `근거 [n]` 표기가 배정한 번호 집합(블록 생략 시 결번)
- `strip_dangling_citations` — 배정 밖 번호 마커만 제거(문장은 남긴다)
- `ensure_disclaimer` — 꼬리 150자에 책임 고지가 없으면 붙인다(멱등)
- `suppress_recommendation` + `grade_caution_notice`(2026-09-01, 1-1) — '주의'/'위험' 등급
  상권의 추천 어휘를 검토로 치환하고 등급 고지를 답변 문두에 삽입. 채점기 `grade_caution`
  절대 규칙과 같은 어휘.
- `strip_unsupported_metric` / `enforce_distance_claim`(2026-09-01, I-15) — 데이터 없는
  지표명("폐업률") 문장 제거(유의 문장은 `_ensure_risk_note`가 재충전) / 매물대 거리가
  ATR 2배를 넘으면 '근처'류를 "(현재가보다 N% 아래/위)"로 교체(매물대·밀집 문장만).
- `attach_glossary`(2026-09-01, I-19) — 질문에 없는 전문용어(모멘텀·수급·%B·ATR·정/역배열)
  첫 등장에 괄호 풀이. 질문자가 쓴 용어·기존 괄호("ATR(14)")는 건드리지 않는다.

인터랙터 측 결정론 삽입(가드와 같은 원칙, 2026-09-01): `_unsupported_notice`(I-12·I-17 —
임대료·정확 매출·배당·PER비교·확률을 물으면 "없다/단정 안 한다"를 문두에),
조건 질의 랭킹 라우팅(I-14 — 지역 미언급+조건 어휘면 허브 `get_area_ranking`을 코드로 정렬,
LLM 미사용), `_trend_text`+산출 방식 블록(I-20 — 추이·산출근거 요청 시에만 주입).

2026-09-03 추가(4차 페르소나 잔여): **신호 보드 조회**(`_SIGNAL_BOARD_RE` — "상승/하락 신호
나온 종목"이면 phase0 전에 허브 `StockSignalBoardPort.current_board`를 읽어 방향별 상위 5종목을
코드로 서술. 종목 하나를 묻는 "삼성전자 신호 어때?"는 잡지 않는다 — stock 경로) ·
**뉴스 상세 후속**(`_NEWS_DETAIL_RE` — "그 뉴스가 뭔데?"류는 직전 payload의 `news`/`stock.headlines`를
그대로 나열, 근거 뉴스가 없는 대화면 정상 흐름) · **phase1 표 판정 축 2열**(I-11 —
`폐업률(%)|점포당월매출(만원)`을 허브 `get_area_ranking` 집계에서 잇는다. 조회 실패는 열 전체
'-'로 열화, 표는 유지. 행 상한 80은 **줄이지 않는다** — 60으로 줄인 재완주에서 어간 가드가 못
잡는 괄호 별칭 지명("발산역(마곡)")을 phase1이 표에서 읽던 경로가 끊겨 MR20이 강남으로 튀었다.
그 별칭은 이제 `_area_mentioned_in`이 직접 본다).

판정 정규식은 채점기 `eval_scorer`와 **같은 것을 쓴다**. 갈라지면 가드를 통과한 답변이
채점에서 떨어진다. stock·market_news 두 답변 경로 모두에 적용된다.

**컨텍스트 창**: phase1 프롬프트는 최대 약 5,000토큰이다(2026-09-03 I-11 2열 추가 후 문자
5,177→6,238, 골든셋 MT08). `core/llm/llm_orchestrator.NUM_CTX`
(8,192)가 이를 담는데, 표 행이나 열을 늘리면 다시 창에 접근한다 — 초과하면 Ollama가
**앞부분을 조용히 버려** 지시문이 사라진다(2026-08-24~28 실장애, ROADMAP I-10).
프롬프트를 키우는 변경은 `prompt_eval_count` 경고 로그를 확인한다.

## LLM 경로 감시 (2026-08-28 신설)

`scripts/check_llm_health.py` — 호스트 cron 매일 **09:30**(신선도 09:00 뒤). 알림 창구는
check_freshness와 같다(n8n 웹훅 → 메일). 세 축을 본다:

| 축 | 잡는 것 |
|---|---|
| **계약 카나리아** | phase1과 같은 모양·같은 크기(80행)의 프롬프트로 실제 추론 1회 → `trdar_codes` 스키마 준수와 프롬프트 토큰을 확인 |
| **런타임 경고 수거** | 백엔드 컨테이너 로그에서 오케스트레이터의 컨텍스트 근접 경고를 24시간치 걷어온다 — 카나리아는 합성이라 **실제 프롬프트가 창에 닿았는지는 이 로그만 안다** |
| **호스트 자원** | Ollama 생존 · 최근 24시간 커널 OOM · 여유 메모리(<2GiB면 경보) |

**왜 지표가 아니라 계약을 보는가**: 2026-08-24 사고에서 phase1은 완전히 죽었는데
`region_hit_rate`는 1.0이었다 — 결정론 지역 가드가 대신 채웠기 때문이다. 품질 지표는
폴백이 가려주지만 **형식 계약은 못 가린다**. 그래서 카나리아는 정확도가 아니라
"JSON 스키마가 돌아오는가"만 본다.

## 비교 바구니 — 상권·종목 비교는 대화 상태다 (2026-09-17)

실대화 289("길음역과 비교해봐" → 단독 추천, "그래서 어디야" → 제3의 상권, "둘이 비교해줘" → 답 반복)의
원인은 비교가 매 턴 새 추천이었던 것. 이제 비교 답의 payload에 `compareSet`(`kind` area|stock, `items`,
업종)을 남기고 다음 턴이 이어받는다 — 새 지역·종목을 말하면 열이 늘고, 제외 어휘("길음 빼고")면 빠지고,
"새로/따로/처음부터"면 바구니를 버린다(최대 4). 표·결론은 `domain/services/compare.py`(순수)가 만든다:
결론이 **항상 첫 줄**. 상권 1순위는 **점수 v2 등급이 한 단계 이상 높을 때만**(같은 등급이면 "1순위 없음",
2026-09-17 개정 — 이전 축별 다수결은 건강 점수와 그 구성요소를 이중으로 세고 미검증 축이 같은 한 표였다).
나머지 축은 "참고 지표별 비교"로만 보여준다. 판정용 폐업률은 최근 4분기 점포 가중(`closure_rate_4q`). 종목은 "데이터상 우위"까지만(권유 금지).
"그래서 어디야/뭐가 나아"는 결론+축별 판정만, 그 외는 전체 표(★ = 축 우위)·업종 공통 창업비용 블록·
못 쓴 데이터 목록(왜 못 썼는지)까지. 상권 표는 분기 팩트·건강 점수(컴포넌트마다 백테스트 예측력 병기)·
서울 순위·인허가·재무(자기자본이 있을 때 월세·공실률·손익분기)·입지 적합도·그래프·기사를 전부 싣는다.
백테스트 행은 점수 v2 이후 "이 등급의 다음 1년 폐업률(실측)"이다.

## 첫 질문 되묻기·창업 의도 보정 (2026-09-17)

- 서울 상권 언급·서울 외 지역·조건 축·업종 감지·성격 단서(`_AREA_TRAIT_HINT_RE` — 직장인·20대·대학·주말·지명 토큰 등)·
  제외 어휘·직전 상권 카드가 **전부 없으면** phase1이 임의로 고르지 않고 `_answer_market_clarify`가 "동네+업종"을 되묻는다
  (예산을 말했으면 공정위 창업비용 고지를 앞에 — 점포 없는 가맹업 `_NON_STOREFRONT_INDUSTRIES` 제외).
- phase0가 general이어도 창업 어휘(`_STARTUP_INTENT_RE`)면 market으로 보정 — 같은 질문이 시각에 따라 인사말로 빠졌다.
- 판정 문구: 종목 참고 신호 배지는 겹침 보정 재검증 미달로 노출 중단, 모의투자 표시명 "AI 판단"(9/15부터 Gemma).

