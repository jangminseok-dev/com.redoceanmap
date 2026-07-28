# LANGCHAIN-HARNESS — 랭체인 이해와 도입 경계

admin 앱 → [[minseok/apps/admin/_docs/CLAUDE|admin CLAUDE]] · 구조 하네스 → [[_docs/harness|harness]] ·
그래프DB 하네스 → [[minseok/apps/admin/_docs/neo4j-harness|neo4j-harness]]

**용도:** 에이전트(Claude 등)가 "랭체인으로 해라 / 랭체인은 왜 안 쓰나"를 만났을 때 추측하지
않도록, **랭체인이 무엇인지 · 이 저장소가 그 자리를 이미 무엇으로 채우고 있는지 · 어떤
조건에서만 도입하는지**를 고정한다. 지금 이 저장소에 랭체인은 **없다**(§0).

---

## 0. 현재 상태 — `langchain-core` 1개만 도입 (2026-07-28 사실)

도입 범위는 **`langchain-core==1.5.1` 하나**다(`langchain` 메타패키지 · `langchain-ollama` ·
`langgraph`는 없다. `langsmith`는 core의 전이 의존으로 설치되나 추적은 비활성 — §6).
쓰는 곳도 **한 파일**이다: `hub/adapter/outbound/langchain_chat_engine_adapter.py`
(랭체인 시멘틱 게이트웨이 ROM 2.0 — `/langchain-semantic/ask`). 그 밖의 자리는 아래 표대로
자체 구현이 계속 맡는다.

§5 게이트 답안(도입 근거):
1. **구체 작업** — 이력 포함 멀티턴 프롬프트 조립 + 체인 분기(근거/일반). `MessagesPlaceholder`
   없이 직접 짜면 이력 직렬화·이스케이프를 매 슬라이스마다 다시 만든다.
2. **범위** — `langchain-core` 1개. 메타패키지·프로바이더 패키지 없음.
3. **지연** — 체인 오버헤드는 프롬프트 조립·파싱뿐이고 모델 호출은 기존 경로 그대로다
   (7.8B 추론 수 초 대비 무시 가능). 실측 대조는 ROM 1.0 `/semantic/ask`가 같은 분류기를
   써서 그대로 비교군이 된다.
4. **제거 계획** — `langchain_chat_engine_adapter.py`의 체인을 `llm_orchestrator.orchestrate`
   직접 호출로 바꾸고 requirements 한 줄을 지우면 끝. 포트(`LangchainChatEnginePort`) 계약은
   랭체인을 노출하지 않으므로 app·domain·라우터는 손대지 않는다.

같은 역할을 이미 자체 구현이 맡고 있다(랭체인으로 옮기지 않는다 — §8).

| 랭체인이 맡는 자리 | 이 저장소의 대응물 |
|---|---|
| LLM 클라이언트 추상(ChatModel) | `core/llm/llm_orchestrator.py` — 단일 오케스트레이터, 기본 모델 EXAONE 7.8B |
| 프롬프트 템플릿 | 어댑터 상수 (`_ROUTING_SYSTEM` · `_GROUNDED_SYSTEM` · `_SUMMARY_SYSTEM` 등) |
| 체인/파이프라인(LCEL) | 유스케이스 인터랙터 — 포트를 순서대로 호출하는 것이 곧 체인이다 |
| 문서 로더 / 스플리터 | 필요한 것만 어댑터로 (예: PDF는 neo4j-graphrag `PdfLoader`) |
| 벡터스토어 / 리트리버 | pgvector + `bge-m3` 임베딩, 앱별 `*SearchPort` |
| 임베딩 | `llm_orchestrator.embed` / `embed_many` |
| 에이전트 / 툴 호출 | 허브 시멘틱 게이트웨이의 분류 → 목적지 라우팅 |
| 관찰성(LangSmith) | 표준 로깅 + `admin_audit_logs` |

즉 **랭체인이 실제로 맡는 일은 프롬프트 조립·출력 파싱 한 칸뿐이고, 나머지는 여전히 얇게
직접 하고 있다**가 정확한 상태다. 특히 ChatModel 자리는 바뀌지 않았다 —
`ExaoneChatModel`은 `llm_orchestrator`를 감싼 껍데기이며 Ollama를 직접 부르지 않는다(§6).

---

## 1. 랭체인의 주요 기능 (설명 + 이 저장소 대응)

### 1-1. 다양한 데이터 소스와의 통합
데이터베이스·API·파일 시스템 등 여러 소스의 데이터를 실시간으로 끌어와 LLM 응답의 근거로
쓰게 해준다. 금융의 실시간 시세 분석, 의료의 환자 기록 조회처럼 **정확성과 관련성**이 데이터
신선도에 달린 응용에서 필수적이다.
→ *여기서는*: 상권·주가·뉴스·펀더멘털 수집 cron이 PG에 적재하고 스포크가 허브 포트로 노출한다.
통합 계층이 랭체인이 아니라 **허브 포트**라는 점만 다르다.

### 1-2. 유연한 프롬프팅 및 컨텍스트 관리
프롬프트 템플릿과 대화 컨텍스트(히스토리) 관리 도구를 제공해, 복잡한 대화 흐름에서도 일관된
맥락을 유지하며 맞춤형 응답을 만들게 한다. 챗봇·학습 도우미의 사용자 경험이 여기서 갈린다.
→ *여기서는*: `orchestrate(prompt, system=..., history=[...])`가 그 자리다. 템플릿 엔진 없이
시스템 프롬프트 상수 + f-string으로 처리한다.

### 1-3. 파인튜닝 및 커스터마이징
특정 도메인 용어·업무에 맞게 모델을 조정하고, 모델을 쉽게 교체·최적화할 수 있는 유연성을 준다.
→ *사실 정정*: **랭체인 자체는 가중치를 학습시키지 않는다.** 여기서 말하는 "파인튜닝"은 실무적으로
(a) 이미 파인튜닝된 모델을 **연결**하는 것, (b) 프롬프트·퓨샷·출력 파서 커스터마이징을 뜻한다.
실제 가중치 학습은 별도 스택(PEFT/QLoRA)의 몫이며 이 저장소도 그렇게 분리돼 있다.

### 1-4. 데이터 반응형 애플리케이션 구축
입력과 실시간 데이터에 즉각 반응하는 시스템을 만든다 — 시세 변화에 맞춰 전략을 조정하는 금융
앱, 사용자 입력에 따라 콘텐츠가 바뀌는 교육 플랫폼 같은 것.
→ *여기서는*: cron 수집 → 스냅샷·채점 → 어드민 분석 화면이 같은 형태의 반응 루프다.

---

## 2. 코드에서 랭체인을 알아보는 법 (읽기용 지도)

| 패키지 | 무엇 | 흔한 신호 |
|---|---|---|
| `langchain-core` | 최소 추상 — Runnable·프롬프트·메시지·출력 파서 | `prompt \| model \| parser` 파이프(LCEL) |
| `langchain` | 체인·에이전트 등 상위 조립 | `create_retrieval_chain` · `AgentExecutor` |
| `langchain-community` | 서드파티 통합 모음(로더·벡터스토어 등) | `from langchain_community...` |
| `langchain-<provider>` | 모델 제공자별 어댑터 | `langchain-openai` · `langchain-ollama` |
| `langgraph` | 상태·분기·루프가 있는 그래프형 에이전트 | `StateGraph`, 노드/엣지 정의 |
| `langsmith` | 추적·평가(관찰성 SaaS) | `LANGCHAIN_TRACING_V2` 환경변수 |

핵심 관용구는 **LCEL의 `|` 파이프**다. `프롬프트 | 모델 | 파서`가 보이면 랭체인 체인이다.

---

## 3. 장점 (설명 + 이 저장소에서의 값어치)

1. **다양한 LLM 통합** — GPT-4·Hugging Face 등 여러 모델을 같은 인터페이스로 갈아끼우고,
   확장·조정이 쉽다.
   → 여기서는 값어치가 **낮다**. 단일 모델 정책(EXAONE 7.8B 하나)이라 갈아끼울 대상이 없다.
2. **높은 커스터마이징 유연성** — 프롬프팅·컨텍스트·파인튜닝 연결을 세밀히 조정해 산업별 맞춤
   솔루션을 만든다.
   → 이미 시스템 프롬프트 교체(동적 프롬프팅)로 같은 일을 한다. 중복 이득.
3. **활발한 오픈소스 커뮤니티** — 통합 어댑터가 계속 늘고, 문제 해결 리소스와 업데이트가 빠르다.
   → **여기서 가장 실질적인 이점.** 새 소스(문서 로더·리트리버)를 직접 짜는 대신 가져올 수 있다.

## 4. 단점 (설명 + 이 환경에서의 무게)

1. **성능 최적화 필요** — 외부 소스를 많이 물릴수록 추상 계층의 연산·지연이 쌓여, 대규모 처리나
   실시간 응답에서는 하드웨어 증설이나 코드 최적화가 필요해진다.
   → 이 환경은 **로컬 GPU 1장(RTX 3050 8GB)에서 7.8B를 돌린다.** 병목이 이미 LLM 추론이라
     계층이 더 얹히면 체감 지연이 커진다. 무게 **높음**.
2. **러닝 커브** — 기능·옵션이 많아 제대로 쓰려면 학습 시간이 든다. 초보자·소규모 프로젝트에는
   부담이 될 수 있다.
   → 1인 운영 저장소라 학습·유지 비용을 온전히 혼자 진다. 무게 **높음**.
3. **모든 유즈케이스에 맞지는 않음** — 고도로 특화된 기능은 결국 직접 만들어야 하고, 성능·비용·
   복잡도 때문에 다른 솔루션이 더 나을 때가 있다.
   → 현재 필요한 흐름(분류 → 검색 → 근거 답변, PDF 추출 → 요약)은 **인터랙터 수십 줄**로 끝난다.
     체인 프레임워크를 얹어야 풀리는 문제가 아직 없다.

---

## 5. 도입 판단 하네스 — 게이트 (패키지를 **더** 추가할 때마다 다시 통과)

`langchain-core` 1개는 통과했다(답안 → §0). 게이트는 여기서 끝난 것이 아니라 **패키지마다**
적용된다 — `langchain-community`·`langchain-text-splitters`·`langgraph` 등을 추가하려면
아래 4개를 그 패키지에 대해 다시 적고 나서 넣는다. "이미 랭체인을 쓰고 있으니까"는 통과 사유가
아니다(§0의 도입 범위가 한 줄로 유지되는 이유).

1. 랭체인 **없이는 과도하게 비싼** 구체 작업 1개 이상(예: 다포맷 로더 + 스플리터 + 리랭커 조합).
   "체계가 잡힌다" 같은 이유는 게이트 통과가 아니다.
2. 도입 범위를 **패키지 단위로 최소화**한 목록(예: `langchain-text-splitters`만).
   `langchain` 메타패키지 통째 설치는 게이트 실패로 본다.
3. 추가 지연·메모리 **실측치**와 허용선(로컬 7.8B 추론 시간 대비 몇 %인지).
4. 제거 계획 — 맞지 않을 때 어디까지 되돌리면 되는지.

하나라도 비면 그 패키지는 넣지 않는다.

## 6. 지켜야 할 경계 (도입 후 — 현재 적용 중)

| 규칙 | 내용 |
|---|---|
| 계층 | `langchain*` import는 **adapter 계층에만**. app·domain은 포트만 본다. 현재 유일한 import 지점은 `hub/adapter/outbound/langchain_chat_engine_adapter.py` |
| 린트 | ✅ 적용됨 — `minseok/.importlinter`의 **프레임워크 격리 계약** `forbidden_modules`에 `langchain_core`·`langchain`·`langgraph`가 들어 있다(app·domain 유입 시 계약 위반). 문서가 아니라 린트로 강제 |
| LLM 수렴 | 랭체인 ChatModel로 Ollama를 **직접** 부르지 않는다(`langchain-ollama` 미설치). 체인에 꽂히는 `ExaoneChatModel`은 `llm_orchestrator.orchestrate`를 감싼 껍데기이며, 랭체인은 추론 앞뒤(조립·파싱)만 맡는다 |
| 단일 모델 | 모델 교체가 쉬워졌다는 이유로 두 번째 모델을 들이지 않는다(단일 모델 정책은 별도 결정 사항) |
| 버전 | requirements 전량 핀 고정 관행대로 `==`로 고정. 랭체인은 마이너 릴리스가 잦아 미고정 시 조용히 깨진다 |
| 비밀값 | 키는 `core/key/secret_manager.py` 경유. 랭체인이 암묵적으로 읽는 `OPENAI_API_KEY` 류 환경변수에 의존하지 않는다 |
| 관찰성 | LangSmith 추적은 기본 **비활성**. `langsmith`가 `langchain-core`의 전이 의존으로 설치돼 있지만 `LANGCHAIN_TRACING_V2`를 켜지 않는 한 아무것도 나가지 않는다. 프롬프트·문서 본문이 외부 SaaS로 나가므로 켜려면 별도 판단이 필요하다 |

## 7. 검증 명령

```bash
# 계층 경계 — app/domain으로 랭체인이 샜는지
grep -rn --include="*.py" "^from langchain\|^import langchain" minseok/apps \
  | grep -E "/(app|domain)/"        # 0줄이어야 한다

# import 지점이 한 파일인지 (늘어났다면 §6 계층 규칙 재확인)
grep -rln --include="*.py" "langchain_core" minseok/apps

# 구조 계약 (forbidden_modules에 langchain_core·langchain·langgraph 포함)
cd minseok && PYTHONPATH=apps lint-imports --config .importlinter

# 회귀 (호스트에 파이썬 개발환경 없음 — 일회성 컨테이너로 실행)
docker run --rm -v /home/host/projects/com.redoceanmap:/work -w /work \
  -e PYTHONPATH=/work/minseok:/work/minseok/apps \
  minseok97/redoceanmap-backend:latest python -m pytest minseok/apps -q
```

## 8. 범위 밖 — 하지 않는다

| 항목 | 사유 |
|---|---|
| 기존 인터랙터를 LCEL 체인으로 재작성 | 동작하는 코드를 프레임워크로 옮기는 것은 순수 비용. 헥사고날에서 체인의 자리는 이미 인터랙터다. ROM 2.0도 인터랙터가 흐름을 통제하고 체인은 답변 생성 한 칸만 맡는다 |
| ROM 1.0(`/semantic/ask`)을 ROM 2.0으로 대체 | 두 버전을 **병행 운영**한다. 같은 분류기를 공유하므로 랭체인 도입의 효과를 같은 조건에서 대조할 수 있는 비교군이다 |
| 랭체인 메모리(`ConversationBufferMemory` 등)로 대화 이력 대체 | 이력은 자체 소유 테이블(chat `conversations`, 허브 `langchain_turns`)에 있고 계약이 명확하다. 체인에는 조회한 이력을 `MessagesPlaceholder`로 넣기만 한다 |
| LangGraph 멀티에이전트 | 멀티에이전트는 별도 포트폴리오 저장소(A2A·MCP)의 주제 — 이 저장소 범위 밖 |
| LangSmith 상시 추적 | 프롬프트·문서 본문의 외부 유출. 필요하면 로컬 로깅으로 먼저 해결 |
| 랭체인으로 파인튜닝 | 애초에 랭체인의 기능이 아니다(§1-3). 가중치 학습은 PEFT/QLoRA 스택의 몫 |
