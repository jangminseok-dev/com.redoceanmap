# LANGCHAIN-EXAMPLE-STRATEGY — 3개 사례를 이 프로젝트에 이식하는 실행 계획

admin 앱 → [[minseok/apps/admin/_docs/CLAUDE|admin CLAUDE]] ·
도입 경계(선행 필독) → [[minseok/apps/admin/_docs/langchain-harness|langchain-harness]] ·
로드맵 → [[minseok/_docs/ROADMAP|ROADMAP]]

**전제:** [[minseok/apps/admin/_docs/langchain-harness|langchain-harness]] §5 게이트를 통과한
범위에서만 랭체인을 쓴다. 이 문서는 그 게이트를 **트랙별로 실제로 채운 결과**이며,
랭체인이 값을 못 하는 자리는 "쓰지 않는다"고 명시한다(§1 판정 표).

---

## 0. 사례 → 이 프로젝트 매핑

| 사례 | 원 사례가 한 일 | 이 프로젝트의 대응 자산 | 트랙 |
|---|---|---|---|
| **Morningstar** — 맞춤형 금융 인사이트 | 방대한 재무 보고서 + 시장 데이터를 분석해, 전문가의 복잡한 질문에 정확히 답하는 인텔리전스 엔진 | PDF 요약 파이프라인(`admin_pdf_documents`) + `fundamental_snapshots`·`price_bars`·`news_labels`·`forecast_snapshots` | **A. 리포트 인텔리전스** |
| **Elastic** — 운용 효율성 향상 | 보안 경고 요약 · 워크플로 제안 · 쿼리 생성/변환으로 분석가 지원 | `dataset_freshness.evaluate`(정상/지연/정지 판정) + 데이터소스 11장 + `admin_audit_logs` | **B. 운영 코파일럿** |
| **NCL** — 최적화된 여행 계획 | 고객 선호도·탐색 기록 기반 맞춤 추천, 실시간 요구 변화 대응 | `recommendations`(추천 이력) + `conversations`(대화 이력) + 상권/업종 축(market) | **C. 개인화 추천** |

**우선순위: B → A → C.** B가 가장 급하다 — `dataset_freshness.py` 주석에 남은 사고
(2026-07-25~27 백엔드 PC가 2일 6시간 꺼져 수집 cron 7종이 멈췄는데 아무도 몰랐음)가 바로
Elastic 사례가 푸는 문제이고, **판정 로직은 이미 있으니 요약·제안 계층만 얹으면 된다**.

---

## 1. 랭체인을 어디에 쓰고 어디에 안 쓰는가 (판정)

| 자리 | 랭체인 | 판정 근거 |
|---|---|---|
| 긴 문서 청킹(map-reduce 요약) | **쓴다** — `langchain-text-splitters` | 현재 PDF 요약은 앞 6000자만 본다(`exaone_pdf_summarizer_adapter.py`). 문단·문장 경계를 지키는 재귀 분할기를 직접 짜는 것은 낭비다 |
| 체인 조립(LCEL) | **부분** — `langchain-core` Runnable·프롬프트 | 단계가 5개 이상으로 늘어나는 A·B에서만. 2~3단계 흐름은 인터랙터가 더 읽기 쉽다.<br>⚠️ ROM 2.0은 이 판정의 **예외**다 — 1콜 흐름인데도 LCEL을 썼다(0단계 기반을 실제로 태워보는 목적). 실측상 손해는 없지만(+0.65 ms) **이 판정을 뒤집은 것은 아니다**. 짧은 흐름에 체인을 더 얹지 않는다 |
| 구조화 출력 파싱 | **쓴다** — `JsonOutputParser` + 재시도 | 지금은 어댑터마다 `json.loads` + try/except를 반복한다(`exaone_semantic_adapter.py` 선례) |
| LLM 호출 | **안 쓴다** — `ChatOllama` 금지 | LLM 추론은 `llm_orchestrator` 수렴 규칙. 대신 오케스트레이터를 감싼 **자체 Runnable**을 만든다(§2) |
| 벡터 검색 | **안 쓴다** | pgvector + `bge-m3` + 앱별 `*SearchPort`가 이미 동작한다. 리트리버 추상은 순수 중복 |
| SQL 생성 에이전트 | **안 쓴다** | 운영 DB에 LLM이 만든 임의 SQL을 던지지 않는다. B의 "쿼리 생성"은 **화이트리스트 템플릿 채우기**로 구현(§4-4) |
| 에이전트/툴 루프 | **안 쓴다** | 자율 루프는 지연·비용·비결정성이 모두 나쁘다. 세 트랙 다 결정적 파이프라인으로 충분 |

**도입 의존성 (전량 핀 고정 · 메타패키지 `langchain` 설치 금지)**

```
langchain-core==1.5.1            # ✅ 설치됨 (2026-07-28, 허브 랭체인 게이트웨이 ROM 2.0)
langchain-text-splitters==<도입 시점 최신>   # 아직 없음 — 트랙 A 착수 시 게이트 재통과 후 추가
```

---

## 2. 0단계 — 공통 기반 (모든 트랙의 선행) — ✅ 완료 (2026-07-28)

랭체인 체인이 우리 모델을 부르되 오케스트레이터 수렴 규칙을 깨지 않게 하는 **얇은 어댑터** 하나.
계획은 `ExaoneRunnable`이었으나, 실제로는 프롬프트 템플릿·`StrOutputParser`와 `|`로 이어지도록
**`BaseChatModel` 구현**으로 만들었다(`Runnable[str, str]`이면 메시지 목록을 받지 못해 체인
중간에 끼울 수 없다). 위치도 트랙별 어댑터가 공유하도록 슬라이스 어댑터 안에 두었다.

```
apps/hub/adapter/outbound/langchain_chat_engine_adapter.py   # 허브 소유
  class ExaoneChatModel(BaseChatModel):
      async def _agenerate(self, messages, ...) -> ChatResult:
          system, history, prompt = _split(messages)      # 랭체인 메시지 → 오케스트레이터 인자
          text = await llm_orchestrator.orchestrate(prompt, system=system, history=history)
```

- 위치가 허브인 이유: LLM은 특정 스포크의 것이 아니다(그래프 어댑터와 같은 원칙 →
  [[minseok/apps/admin/_docs/neo4j-harness|neo4j-harness]] §4).
- 이 파일과 각 트랙의 어댑터 **밖에는** `langchain*` import가 없어야 하고,
  app·domain 계층에는 **절대** 없어야 한다.
- ✅ 완료 조건 충족: `.importlinter`의 `framework-isolation` 계약 `forbidden_modules`에
  `langchain_core`·`langchain`·`langgraph` 추가, 5계약 통과.
  트랙 A 착수로 `langchain-text-splitters`를 넣을 때 `langchain_text_splitters`도 같이 추가한다.
- **다른 트랙은 이 ChatModel을 재사용한다** — 트랙마다 새 Runnable을 만들지 않는다.

---

## 3. 트랙 B — 운영 코파일럿 (Elastic형) · **최우선**

**목표:** 데이터소스 11장을 눈으로 훑는 대신 **경고 요약 → 원인 가설 → 조치 워크플로**를 한 번에
받는다. Elastic이 보안 경고에 한 일을 수집 파이프라인 경고에 그대로 한다.

**단계**

1. **경고 수집(비-LLM)** — 기존 `dataset_freshness.evaluate` 결과에서 `LATE`·`STALE`·`UNKNOWN`만
   추린다. 여기까지는 순수 도메인이라 랭체인과 무관하다.
2. **요약** — 경고 목록 + 기대 주기 + 마지막 적재 시각을 넣어 "무엇이 언제부터 멈췄는가"를 3문장으로.
3. **워크플로 제안** — `JsonOutputParser`로 구조화:
   `{"severity": "...", "steps": [{"action": "...", "command": "...", "why": "..."}]}`.
   명령은 **화이트리스트에서만** 고르게 한다(`crontab -l` 확인 · `collect_news.py` 수동 실행 ·
   컨테이너 상태 확인 등). 자유 형식 셸 명령 생성은 금지하고, 목록 밖 값은 파싱 단계에서 버린다.
4. **쿼리 생성/변환** — "최근 24시간 news_articles 적재 추이" 같은 요청은 **사전 정의된 파라미터화
   쿼리 템플릿 + LLM이 고른 인자**로 조립한다. LLM이 SQL 문자열을 직접 쓰지 않는다.

**산출**: `GET /admin/ops-copilot` (권한 `datasources:read` 재사용) — 경고 요약 · 조치 스텝 ·
조회 결과. **제안만 하고 실행하지 않는다.**

**성공 기준**
- [ ] cron 하나를 의도적으로 멈춘 재현 환경에서 그 데이터셋을 정확히 지목
- [ ] 화이트리스트 밖 명령이 응답에 나오는 경우 0건(거부 테스트 포함)
- [ ] 정상 상태에서는 "이상 없음"을 반환하고 **LLM을 호출하지 않는다**(무경고 시 비용 0)
- [ ] 경고 5건 기준 응답 5초 이내 실측

**리스크**: LLM이 없는 사실을 지어내면 운영자가 잘못된 조치를 한다. 요약은 **판정 결과를 문장으로
바꾸는 것**까지만 허용하고, 원인 추정에는 "가설" 라벨을 붙여 출력한다.

---

## 4. 트랙 A — 리포트 인텔리전스 (Morningstar형)

**목표:** "이 리포트가 말하는 종목의 실제 수치·뉴스·예측은 어땠는가"를 한 화면에서 답한다.
리포트 텍스트(정성)와 수집 데이터(정량)를 **같은 근거 묶음**으로 제시하는 것이 핵심이다.

**단계**

1. **전문 요약(현 한계 해소)** — `admin_pdf_documents.extracted_text`를
   `RecursiveCharacterTextSplitter`로 분할 → 조각별 요약 → 재요약(map-reduce).
   현재의 "앞 6000자만 요약" 표기를 없앨 수 있는지가 판정 기준.
2. **종목 추출** — 요약문에서 티커·기업명을 `JsonOutputParser`로 구조화
   (`{"tickers": [...], "themes": [...]}`). 실패 시 빈 배열 폴백(semantic 어댑터 선례).
3. **정량 근거 조인** — 허브 포트로 종목별 수치를 모은다:
   `FundamentalReadPort`(PER/PBR 등) · `StockAnalysisPort`·`PriceBarStoragePort`(가격 추이) ·
   `NewsSearchPort` + `news_labels`(뉴스 톤) · `ForecastSnapshotPort`(예측·채점 이력).
4. **인사이트 합성** — 리포트 요약 + 정량 근거를 한 프롬프트에 넣어 "리포트 주장 ↔ 데이터" 대조
   코멘트를 만든다. 근거 밖 수치를 못 만들게 `_GROUNDED_SYSTEM` 패턴(컨텍스트 한정)을 재사용한다.

**산출**: `POST /admin/pdf-documents/{id}/deep-summary`(전문 요약, `documents:write`) +
`GET /admin/pdf-documents/{id}/insight`(요약·추출 종목·수치 카드·대조 코멘트, `documents:read`).

**슬라이스**: 기존 `pdf_loader`와 같은 컨벤션으로 `report_insight` 신설
(schema/dto/ports/interactor/provider/test). **기존 PDF 파이프라인은 수정하지 않고 소비만** 한다.

**성공 기준**
- [ ] 5만 자 이상 PDF에서 절단 표기 없는 요약 생성 + 소요 시간 실측 기록
- [ ] 손으로 고른 리포트 5건에서 종목 오검출 0건
- [ ] 인사이트의 모든 수치가 조인된 근거에 실재(할루시네이션 0건) — 5건 수동 검수
- [ ] `pytest` 전체 통과 · `lint-imports` 5계약 유지

**리스크**: map-reduce는 LLM 호출이 N+1회다. 로컬 7.8B에서 조각당 수 초 → 수십 조각이면 분 단위.
**업로드 응답을 막지 않는다** — 업로드 시점 요약은 현행(단발) 유지하고, 전문 요약은 별도
엔드포인트로 분리 실행해 결과를 컬럼에 저장한다.

---

## 5. 트랙 C — 개인화 추천 (NCL형)

**목표:** **탐색 기록**(추천 이력·대화 이력)에서 선호 프로파일을 만들고, 상권/업종 추천을 그
프로파일에 맞춰 재정렬한다. NCL이 크루즈 선호도로 한 일을 상권 선호도로 한다.

**단계**

1. **프로파일 추출** — `recommendations` + `conversations`의 사용자별 최근 N건을 모아
   `JsonOutputParser`로 `{"regions": [...], "industries": [...], "budget_hint": "...",
   "risk_tone": "..."}` 생성. 갱신은 로그인 시 또는 야간 배치.
2. **후보 생성(비-LLM)** — 기존 market 점수·비교·밀도 로직으로 후보를 뽑는다.
   **LLM이 후보를 만들지 않는다** — 순위의 근거는 계속 데이터여야 한다.
3. **재정렬·설명** — 프로파일 + 후보를 함께 넣어 상위 N개를 고르고 **선정 이유 한 줄**을 붙인다.
4. **실시간 반영** — 대화 중 새 선호("역세권 말고 주택가")가 감지되면 세션 단위로 프로파일을
   덮어쓰고 재정렬한다. 영속 프로파일은 배치 때만 갱신.

**산출**: 기존 추천 응답에 `profile_reason` 필드 추가(신규 엔드포인트 없음) +
어드민 열람 `GET /admin/members/{id}/profile`(권한 `members:read`).

**성공 기준**
- [ ] 프로파일 JSON 스키마 위반 0건(파서 재시도 포함)
- [ ] 재정렬이 후보 **집합**을 바꾸지 않음(순서만 변경) — 근거 보존 회귀 테스트
- [ ] 프로파일에 원문 대화가 저장되지 않음(추출 키워드만) — 개인정보 경계

**리스크**: 사용자 수가 적으면 개인화 이득이 보이지 않는다. **A·B 완료 후 착수**한다.

---

## 6. 실행 순서와 커밋 단위

| 순서 | 내용 | 완료 판정 |
|---|---|---|
| 0 | 공통 Runnable + 의존성 2종 + importlinter 갱신 | `lint-imports` 5계약 · `pytest` 전체 통과 |
| 1 | 트랙 B 운영 코파일럿 | §3 성공 기준 4개 |
| 2 | 트랙 A-1 전문 map-reduce 요약(분리 실행) | 절단 표기 제거 + 시간 실측 |
| 3 | 트랙 A-2 정량 근거 조인 + 인사이트 | §4 성공 기준 4개 |
| 4 | 트랙 C 개인화 | §5 성공 기준 3개 |

각 커밋은 **단독 배포 가능**해야 한다(기존 엔드포인트 동작 유지). 배포 시 alembic 선행 규칙
(admin CLAUDE의 배포 순서 주의)을 그대로 적용한다.

## 7. 롤백 계획

- 랭체인 사용처는 **공통 Runnable 1개 + 트랙별 어댑터**로 국한된다. 되돌릴 때는 해당 어댑터를
  기존 방식(f-string 프롬프트 + `json.loads`)으로 교체하고 의존성 2줄을 지운다.
- 분할기만 남기고 싶으면 `langchain-core`만 빼는 부분 롤백도 가능하다 —
  메타패키지를 설치하지 않는 이유가 이것이다.
- 저장된 산출물(요약·프로파일)의 스키마는 랭체인과 무관하므로 롤백해도 데이터는 남는다.

## 8. 범위 밖 — 하지 않는다

| 항목 | 사유 |
|---|---|
| 자율 에이전트 루프(툴 호출 반복) | 지연·비용·비결정성. 세 트랙 모두 결정적 파이프라인으로 충분 |
| LLM이 생성한 SQL 직접 실행 | 운영 DB 보호. 파라미터화 템플릿만 사용(§3-4) |
| 코파일럿의 조치 자동 실행 | 제안까지만 — 실행은 사람이 한다 |
| 외부 상용 LLM 전환 | 단일 모델 정책(EXAONE 7.8B) 유지. 랭체인 도입이 모델 정책을 바꾸는 근거가 되지 않는다 |
| LangSmith 추적 | 프롬프트·리포트 본문의 외부 유출 |
| 프론트 신규 페이지 다수 신설 | admin 6페이지 전면 구현은 ROADMAP 과설계 목록. 기존 화면에 카드·섹션으로 붙인다 |
