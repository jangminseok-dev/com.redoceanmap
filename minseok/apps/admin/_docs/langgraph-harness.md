# LANGGRAPH-HARNESS — reasoning 분기와 GraphRAG 도입 경계

admin 앱 → [[minseok/apps/admin/_docs/CLAUDE|admin CLAUDE]] ·
랭체인 도입 경계(선행 필독) → [[minseok/apps/admin/_docs/langchain-harness|langchain-harness]] ·
그래프DB 운영 규칙(선행 필독) → [[minseok/apps/admin/_docs/neo4j-harness|neo4j-harness]] ·
도입 순서·단계별 완료 판정 → [[minseok/apps/admin/_docs/langgraph-strategy|langgraph-strategy]] ·
실행 계획 → [[minseok/apps/admin/_docs/langchain-example-strategy|langchain-example-strategy]]

**용도:** 시멘틱 라우터가 **`reasoning`으로 분류한 질문 하나**에 한해 LCEL 선형 체인 대신
랭그래프(StateGraph)를 태우고, 그 그래프가 Neo4j 그래프를 근거로 쓰게 하는 배선을 고정한다.
**이 문서는 기능 설계서가 아니다** — "그래프가 좋다"는 이유로 기존 3분기까지 그래프로 옮기는
것을 막는 것이 목적이다. 지금 저장소에 랭그래프는 **없다**(§0).

---

## 0. 현재 상태 (2026-07-28 기준 사실)

| 항목 | 상태 |
|---|---|
| `langgraph` 패키지 | **미설치.** requirements에 없고, `.importlinter` `framework-isolation` 계약의 `forbidden_modules`에 이름만 선등록돼 있다(app·domain 유입 차단) |
| 랭체인 | `langchain-core==1.5.1` 1개. import 지점 1파일 — `hub/adapter/outbound/langchain_chat_engine_adapter.py` |
| 시멘틱 분류 | `ExaoneSemanticAdapter.classify` — 목적지 **3종(`crud`·`rag`·`gemini`)**, 파싱 실패·미지 값은 `rag` 폴백. **ROM 1.0과 ROM 2.0이 이 분류기를 공유**한다 |
| ROM 2.0 답변 | `LangchainSemanticInteractor` → `LangchainChatEnginePort` → LCEL 체인 2벌(`rag_chain`·`chat_chain`). 근거는 `MarketNewsSearchPort`(상권 뉴스 4건), 근거 0건이면 체인을 태우지 않고 거부 |
| 이력 | `langchain_sessions`·`langchain_turns`(허브 소유 ORM 예외). 최근 10턴을 매 턴 주입 |
| Neo4j | **2026-07-30 갱신** — 서버 기동됨(구 스택 `neo4j:5.26`, `profiles: ["graph"]`, 드라이버 6.2.0 검증) + **투영 완료**(노드 3,582 / 관계 79,188, `scripts/project_graph.py`). 단 **런타임 질의 코드는 여전히 0건** — `hub/adapter/outbound/graph/`는 자리만 예약. `neo4j-graphrag==1.18.0`은 admin PDF 추출기로만 쓰인다 |
| 판정 | **`reasoning` 분기도 GraphRAG도 아직 도입 전이다.** 이 문서는 게이트(§5)를 채우기 전까지 코드를 쓰지 않기 위한 사전 배선이다 |

---

## 1. 왜 선형 체인으로 부족한가 (이 저장소 코드 기준)

랭그래프의 일반론(조건 분기·순환·상태 관리·멀티에이전트)은 맞지만, **일반론은 게이트 통과
사유가 아니다**(langchain-harness §5-1). 지금 코드에서 실제로 막히는 지점만 적는다.

| 랭그래프가 푸는 것 | 지금 코드에서 어디가 막히나 |
|---|---|
| **순환(loop)** | `_respond`는 `market_news.search(prompt, limit=4)`를 **한 번** 부르고 끝이다. 히트가 빈약해도 질의를 바꿔 다시 찾지 않는다 — 0건이면 즉시 거부, 1건이면 그 1건으로 답한다 |
| **조건 분기** | 분기는 `destination` 하나로 끝난다(`crud`/`rag`/`chat`). 답을 만든 뒤 "근거를 벗어났는가"를 보고 되돌아가는 경로가 없다 |
| **상태 관리** | 체인에 실리는 것은 `question`·`history`·`context` 3개뿐이다(`EngineTurn`). 중간 판단·재시도 횟수·부분 근거를 담을 자리가 없어 인터랙터의 지역 변수로 흩어진다 |
| **다단계 추론** | 비교·인과 질문("성수동과 연남동 중 카페는 어디가 낫고 왜?")은 상권 A 근거 · 상권 B 근거 · 비교 축을 각각 모아야 하는데, 1회 검색 + 1회 생성 구조에는 그 자리가 없다 |

**단, 위 넷은 `reasoning` 질문에서만 발생한다.** `rag`(단일 상권 사실 질의)·`gemini`(일상 대화)·
`crud`(감지만)는 지금 구조로 충분하고, 여기에 그래프를 얹는 것은 순수 비용이다(§8).

> **멀티에이전트는 이 문서의 근거가 아니다.** langchain-harness §8이 "LangGraph 멀티에이전트는
> 별도 포트폴리오 저장소(A2A·MCP)의 주제"로 범위 밖에 뒀고, **그 판정은 유지된다.**
> 여기서 도입하려는 것은 역할이 다른 에이전트 여럿이 아니라 **단일 그래프의 결정적 제어 흐름**
> 하나다. 노드를 "에이전트"로 부르기 시작하면 그 순간 범위 밖으로 넘어간 것이다.

---

## 2. 만들 것 — `reasoning` 분기 하나

### 2-1. 분류기에 4번째 목적지를 추가한다

```
{"destination": "crud" | "rag" | "gemini" | "reasoning", "entities": [...]}

- "reasoning": 비교·인과·다단계 판단이 필요한 질문
  (예: "성수동이랑 연남동 중 카페 창업은 어디가 낫고 왜?", "이 지역 폐업률이 오른 이유가 뭐야?")
```

**분류기는 ROM 1.0과 공유물이다 — 이 프롬프트를 고치는 것은 ROM 1.0의 동작 변경이다.**

- ROM 1.0(`SemanticInteractor._DESTINATIONS`)에는 `reasoning`을 **넣지 않는다.** 미지 값 →
  `rag` 폴백이 그대로 걸려 기존 동작이 유지되고, ROM 1.0은 계속 비교군으로 남는다
  (langchain-harness §8의 병행 운영 규칙).
- 다만 카테고리 추가는 `rag`↔`gemini` 경계도 흔든다. **프롬프트를 고치는 커밋은 고정 질문
  세트(각 목적지 10문항 이상)의 분류 결과를 변경 전/후로 비교한 표를 함께 남긴다.** 기존
  3분기 판정이 바뀌면 그건 회귀다.

### 2-2. 그래프 모양 (노드·엣지·상한)

```
                 ┌──────────────► compose ──► verify ──► END
                 │                   ▲          │ (근거 이탈, 1회 한정)
plan ──► retrieve ──► grade ─────────┘          └──────► compose
           ▲            │ (근거 부족, 최대 2회전)
           └── refine ◄─┘
```

| 노드 | 하는 일 | LLM |
|---|---|---|
| `plan` | 질문을 하위 질의 1~3개로 쪼갠다(비교 질문이면 대상별로). 출력은 JSON 배열 | 1회 |
| `retrieve` | 하위 질의별로 `MarketNewsSearchPort`(pgvector) + `GraphExpandPort`(Neo4j 이웃) 조회 | 0회 |
| `grade` | 모인 근거가 질문에 답하기 충분한지 판정(JSON `{"sufficient": bool, "missing": "..."}`) | 1회/회전 |
| `refine` | 부족한 축을 반영해 하위 질의를 다시 쓴다 → `retrieve`로 되돌아감 | 1회/회전 |
| `compose` | 모인 근거만으로 답을 쓴다(`_RAG_SYSTEM` 계열 컨텍스트 한정 프롬프트 재사용) | 1회 |
| `verify` | 답의 주장들이 근거 안에 있는지 확인. 이탈이면 `compose` 1회 재실행 | 1회 |

**상한은 코드 상수로 고정한다 — 자율 종료에 맡기지 않는다.**

```python
MAX_RETRIEVE_ROUNDS = 2   # plan 포함 최대 2회전
MAX_REGENERATE     = 1    # verify 실패 시 재작성 1회
MAX_LLM_CALLS      = 8    # 안전망 — 초과 시 그래프 중단, 지금까지의 근거로 rag 체인 폴백
```

- 근거: langchain-harness §4-1이 이미 선을 그어놨다 — 계층 오버헤드(+0.65 ms)는 무시할 수
  있지만 **LLM을 여러 번 부르는 추상은 곱해지는 것이 추론 횟수라 예측이 다시 유효**하다.
  로컬 7.8B 1콜이 종단 3.8초였으므로(맥 로컬 실측), 최악 8콜은 **분 단위에 근접**한다.
- 그래서 이 분기는 **동기 응답으로만 쓰지 않는다**: `reasoning` 응답이 §5-3 허용선을 넘으면
  도입을 보류하거나 스트리밍/비동기 표면으로 분리한다. 사용자를 30초 세워두는 화면은 만들지 않는다.

### 2-3. 상태(State)는 그래프 안에서만 산다

```python
class ReasoningState(TypedDict):     # adapter 계층 전용 — app·domain은 이 타입을 모른다
    question: str
    history: list[tuple[str, str]]   # 인터랙터가 주입 (langchain_turns에서 온 것)
    subqueries: list[str]
    evidence: list[Evidence]         # 출처(뉴스 id / 그래프 노드 external_id) 필수
    rounds: int
    regenerated: int
    answer: str
    degraded: list[str]              # 예: ["graph_unavailable"] — 응답에 그대로 실어 보낸다
```

| 규칙 | 내용 |
|---|---|
| **체크포인터 금지** | LangGraph의 `Postgres/SqliteSaver`를 쓰지 않는다. 대화 이력의 소유자는 `langchain_sessions`·`langchain_turns`이고, 체크포인터를 넣으면 이력이 이원화된다(랭체인 메모리를 안 쓴 것과 같은 이유 — langchain-harness §8) |
| **상태는 1턴짜리** | `ReasoningState`는 한 번의 `ask` 안에서 생겼다 사라진다. 턴 간에 실어 나르는 것은 지금처럼 인터랙터가 조회한 최근 10턴뿐이다 |
| **근거에 출처 필수** | `Evidence`는 본문과 함께 원본 키를 갖는다. 출처 없는 문자열을 근거로 넣지 않는다(verify 노드가 판정할 대상이 사라진다) |
| **열화는 상태로 표현** | 그래프·검색 실패는 예외로 터뜨리지 않고 `degraded`에 남기고 진행한다(neo4j-harness §4 장애 격리) |

### 2-4. 인터랙터는 여전히 대장이다

```
LangchainSemanticInteractor.ask
  ├─ classify                     … 지금과 동일 (공유 분류기)
  ├─ destination == "reasoning"   … ReasoningGraphPort.reason(ReasoningTurn) → ReasoningAnswer
  ├─ destination == "rag"         … 지금과 동일 (LCEL rag_chain)
  ├─ destination == "gemini"      … 지금과 동일 (LCEL chat_chain)
  └─ destination == "crud"        … 지금과 동일 (감지만, 체인 없음)
```

- **가드레일은 그래프로 내려보내지 않는다.** "근거 0건이면 거부"·"crud 미실행"은 인터랙터에
  남는다. 그래프가 스스로 거부를 판단하기 시작하면 정책이 두 군데로 갈라진다.
- 응답 스키마는 그대로 쓴다 — `chain` 필드에 `"reasoning_graph"`를 실어 프론트(`/rom`)가
  어떤 경로였는지 보게 한다. 새 필드·새 엔드포인트를 만들지 않는다.
- **폴백 경로는 필수**: 그래프가 상한 초과·예외·Neo4j 부재로 답을 못 내면 기존 `rag_chain`으로
  떨어진다. `reasoning`이 새 장애 지점이 되어서는 안 된다.

---

## 3. GraphRAG — Neo4j를 무엇에만 쓰는가

`retrieve` 노드가 벡터 검색과 **그래프 이웃 확장**을 함께 쓰는 것이 GraphRAG의 실체다.
neo4j-harness의 소유·모델링 규칙이 전부 그대로 적용되고, 아래는 그 위에 얹는 제한이다.

### 3-1. 역할 분담 — 벡터는 pgvector, 그래프는 관계 확장

| 자리 | 채택 | 이유 |
|---|---|---|
| 의미 검색 | **pgvector + bge-m3 유지** | 이미 동작한다. Neo4j 벡터 인덱스로 옮기는 것은 임베딩 이중화(langchain-example-strategy §1 "벡터 검색은 안 쓴다"와 동일 판정) |
| 관계 확장(멀티홉) | **Neo4j** | "이 상권과 같은 지역·같은 업종의 다른 상권", "이 기사가 언급한 상권에 걸린 다른 이벤트" — PG 조인으로 2홉을 넘어가면 쿼리가 답이 아니라 문제가 되는 지점 |
| 정본 | **PG** | 그래프는 파생본. 그래프에만 있는 사실을 만들지 않는다(neo4j-harness §4) |

즉 검색은 **`entities`(분류기가 이미 뽑아준다) → 그래프 노드 매칭 → 이웃 확장 → 그 키로 PG
본문 조회** 순서다. 그래프는 *무엇을 더 읽을지*를 정하고, 읽는 것은 PG다.

### 3-2. 스키마는 고정 — LLM에게 라벨을 만들게 하지 않는다

`LLMGraphTransformer`류로 엔티티·관계를 자유 추출하면 라벨이 무한 증식한다
(neo4j-harness §2-4 자유 속성 금지의 그래프판). 허용 목록을 먼저 적고 그 안에서만 쓴다.

**아래 표는 2026-07-30 투영으로 실측 확정됐다**(실행 결과·개수 → neo4j-strategy §4 1단계).

| 라벨 | 속성 | 출처 | 실적 |
|---|---|---|---|
| `Area`(상권) | `external_id`(trdar_code) · `name` | PG 결정적 투영 — LLM 없음 | 1,650 |
| `Region`(지역) | `external_id` · `name` | PG 결정적 투영 | 425 |
| `Industry`(업종) | `external_id`(service_code) · `name` | PG 결정적 투영 | 100 |
| `Article`(기사) | `external_id`(news id) · `title` · `published_at` | PG 결정적 투영 | 1,377 |
| `Topic`(주제/이벤트) | `external_id`(`area:` 접두 슬러그) · `name` | **결정적 투영으로 시작**(`area_tag` 30종). LLM 추출은 비정형 본문에서만 — 같은 라벨에 접두어로 공존 | 30 |

```cypher
(:Area)-[:IN_REGION]->(:Region)        // 1,650
(:Region)-[:IN_REGION]->(:Region)      //   424 — parent_code 계층(동→구→시). 아래 ★
(:Area)-[:HAS_INDUSTRY]->(:Industry)   // 75,985 — 최신 분기(store) 조합
(:Article)-[:ABOUT]->(:Topic)          // 1,129 — area_tag 매칭
(:Article)-[:MENTIONS]->(:Area)        //     0 — 만들지 않았다. 아래 ☆
```

- **★ `Region`→`Region` 추가 이유:** 이 관계가 없으면 "같은 **동**의 다른 상권"(2홉)까지만 되고
  "같은 **구**"(4홉)가 막힌다 — 멀티홉이라는 도입 근거의 절반이 여기 걸려 있다. 새 라벨·새 관계
  타입이 아니라 기존 타입 재사용이라 §3-2의 고정 목록을 넓히는 것은 아니다.
- **☆ `MENTIONS`를 만들지 않은 이유:** `area_tag`는 코드가 아니라 검색 키워드(`"성수"`·`"강남역"`)라
  상권과 이으려면 상권명 문자열 추측이 필요하다. 실측 `"영등포"` → **19개 상권** 부분일치.
  그대로 이으면 *"이 기사가 이 상권을 언급했다"*는 **정본에 없는 사실**이 그래프에 생긴다
  (neo4j-harness §4 위반). 선행 조건은 문자열 추측이 아니라 **태그↔상권 매핑 테이블(PG)**이다.
- 제약·인덱스 Cypher는 `scripts/graph_constraints.cypher`(라벨별 `external_id` 유니크 5 +
  `Article.published_at` 인덱스). 적재는 `MERGE` 멱등 — 2회 연속 실행 회귀 통과.
- **정형 데이터에는 LLM을 쓰지 않는다.** 상권·업종·지역은 PG에 이미 관계가 있다 — 그것을
  LLM으로 다시 추출하는 것은 비용을 내고 정확도를 낮추는 일이다. LLM 추출은 `Topic` 한 칸뿐이고,
  그마저 허용 목록(사전 정의된 주제 슬러그)에 매칭되지 않으면 버린다.

### 3-3. Text-to-Cypher는 쓰지 않는다

`GraphCypherQAChain`처럼 **LLM이 Cypher 문자열을 만들어 실행하는 경로는 채택하지 않는다.**
langchain-example-strategy §8의 "LLM이 생성한 SQL 직접 실행 금지"와 같은 판정이다.

대신 **파라미터화 Cypher 템플릿 화이트리스트**를 쓴다 — LLM은 템플릿 이름과 인자만 고른다.

```python
GRAPH_QUERIES = {                      # 이 dict 밖의 Cypher는 실행 경로가 없다
    "area_neighbors":  "MATCH (a:Area {external_id:$id})-[:IN_REGION]->(:Region)"
                       "<-[:IN_REGION]-(b:Area) RETURN b.external_id, b.name LIMIT $limit",
    "area_articles":   "MATCH (ar:Article)-[:MENTIONS]->(a:Area {external_id:$id}) "
                       "RETURN ar.external_id, ar.title ORDER BY ar.published_at DESC LIMIT $limit",
}
```

- 세션은 **읽기 전용**(`default_access_mode=READ`)으로 연다. `reasoning` 경로에 쓰기는 없다.
- 모든 조회에 `LIMIT`과 타임아웃을 건다. 상한 없는 가변 길이 경로(`-[*]->`)를 템플릿에 넣지 않는다.
- 어드민이 그래프에 **쓰기**를 하게 되면 그때는 `AuditLogPort` 대상이다(neo4j-harness §4).

---

## 4. 계층·소유 경계

```
apps/hub/
├── app/ports/output/reasoning_graph_port.py      # reason(ReasoningTurn) -> ReasoningAnswer  ← langgraph 미노출
├── app/ports/output/graph_expand_port.py         # 그래프 이웃 확장 (Cypher 미노출)
├── app/dtos/langchain_semantic_dto.py            # ReasoningTurn·ReasoningAnswer 추가 (기존 모듈 재사용)
├── adapter/outbound/langgraph_reasoning_adapter.py   # ★ langgraph import는 이 파일에만
└── adapter/outbound/graph/neo4j_graph_adapter.py     # ★ neo4j 드라이버는 이 파일에만 (허브 소유 전역 인프라)
```

| 규칙 | 내용 |
|---|---|
| import 지점 | `langgraph` 1파일 · `neo4j` 1파일. 늘어나면 §5 게이트를 다시 통과해야 한다 |
| 린트 | `framework-isolation` 계약에 `langgraph`가 이미 있다 — app·domain 유입은 계약 위반으로 잡힌다. `neo4j`·`neo4j_graphrag`도 같은 계약에 **추가한다**(현재 미등록) |
| 노드의 의존 | 그래프 노드는 드라이버·Cypher를 직접 잡지 않고 **주입받은 포트**(`MarketNewsSearchPort`·`GraphExpandPort`)를 부른다. 어댑터 안이라도 포트를 경유해야 노드 단위 테스트가 스텁으로 가능하다 |
| LLM 수렴 | 노드의 모든 추론은 `ExaoneChatModel`(=`llm_orchestrator`) 재사용. 노드마다 새 ChatModel·`ChatOllama`를 만들지 않는다 |
| 스포크 | 스포크는 Bolt에도 그래프 포트에도 직접 붙지 않는다. 그래프는 허브 소유(neo4j-harness §4) |
| 단일 모델 | 노드별로 다른 모델을 쓰고 싶어지면 그건 단일 모델 정책 변경 안건이지 랭그래프 도입의 부속물이 아니다 |

---

## 5. 도입 게이트 — 현재 답안 (미완)

langchain-harness §5(패키지 4문항) + neo4j-harness §5-5(그래프 4조건)를 **둘 다** 채워야 한다.
"이미 랭체인을 쓰고 있으니까"는 통과 사유가 아니다.

### 5-1. 패키지 게이트 (`langgraph`)

| # | 항목 | 현재 답 |
|---|---|---|
| 1 | 랭그래프 없이는 과도하게 비싼 구체 작업 | **약하게 채워짐.** §1의 순환(근거 부족 시 재검색)·재작성 루프는 직접 짜면 while 루프 + 상태 dict로도 된다. 랭그래프의 값은 "노드/엣지가 코드에 그대로 보이는 것"인데 **그건 가독성 논거라 §5-1이 배제한 사유에 가깝다.** 실측(3)이 통과하고 루프가 3개 이상으로 늘어날 때 다시 판정한다 |
| 2 | 도입 범위 최소화 | `langgraph` 1개(`langgraph-checkpoint*`·`langgraph-prebuilt` 미사용, 메타패키지 금지). 핀 고정 `==` |
| 3 | 지연·메모리 실측치와 허용선 | ❌ **미측정.** 허용선을 먼저 정한다: **`reasoning` 종단 p95 ≤ 25초**, 그리고 **그래프 계층 자체의 오버헤드(모델 호출 스텁 고정)는 추론 시간의 1% 이내**(langchain-harness §0-3이 정한 선 그대로). 둘 중 하나라도 넘으면 도입 보류 |
| 4 | 제거 계획 | `ReasoningGraphPort` 계약이 랭그래프를 노출하지 않으므로, 어댑터를 while 루프 구현으로 갈아끼우거나 `reasoning`을 `rag`로 되돌리고 requirements 한 줄을 지우면 끝이다 |

### 5-2. 그래프 게이트 (Neo4j)

| # | 항목 | 현재 답 |
|---|---|---|
| 1 | 그래프로만 답할 수 있는 질문 | ⚠️ **절반 남음.** 4홉 질의가 **실동작함은 확인됐다**(2026-07-30 — "같은 구의 다른 상권" 54곳 · 업종 공유 상권 구별 집계, PG로는 4단 조인). 남은 것은 *사용자가 그런 질문을 실제로 하는가* — 계수 방법은 langgraph-strategy §4-1. 이 계수가 여전히 그래프 **질의 코드** 도입의 선행 조건이다 |
| 2 | 라벨·관계·속성 + 제약 Cypher | ✅ **완료** — §3-2 표 실측 확정 + `scripts/graph_constraints.cypher`(제약 5 + 인덱스 1) |
| 3 | PG→그래프 투영 경로 | ✅ **완료** — `scripts/project_graph.py`(단방향·`MERGE` 멱등, 2회 회귀 통과, 노드 3,582/관계 79,188). ⚠️ "언제"는 아직 수동 — cron 등록은 이미지 재빌드가 선행 |
| 4 | 그래프가 죽었을 때 | ⚠️ **설계만 있다.** §2-3 `degraded` + §2-4 rag 폴백 — 그래프 부재는 `reasoning`을 더 얕게 만들 뿐 500이 되지 않는다. **코드는 질의 경로와 함께 만든다** |

**결론: 데이터는 들어갔고 질의 코드는 아직이다.** 2·3은 채워졌고 1·4가 남았다 —
**투영(데이터 적재)과 질의 경로(런타임 코드)는 다른 게이트**이며, 데이터가 있다는 것이 코드를
써도 된다는 뜻이 아니다. 순서는 그대로다: **`reasoning` 분기(pgvector 근거만) → 로그로 멀티홉
수요 확인 → graph 노드 추가.** 두 개를 한 커밋에 넣지 않는다 — 그러면 느려졌을 때 원인이
랭그래프인지 Neo4j인지 가릴 수 없다.

---

## 6. 지켜야 할 경계 (도입 후)

| 규칙 | 내용 |
|---|---|
| 분기 확대 금지 | 그래프를 타는 목적지는 `reasoning` **하나**다. `rag`·`gemini`를 그래프로 옮기지 않는다 |
| 상한 고정 | 회전·재작성·총 LLM 호출 상한을 상수로 둔다. "모델이 알아서 멈춘다"에 의존하지 않는다 |
| 결정성 | 노드 순서와 분기 조건은 코드가 정한다. 다음에 어느 노드로 갈지를 LLM이 고르게 하면 그건 에이전트 루프이고 범위 밖(§8) |
| 체크포인터 금지 | 이력·상태의 소유자는 `langchain_turns`(§2-3) |
| Cypher 생성 금지 | 화이트리스트 템플릿 + 읽기 전용 세션(§3-3) |
| 관찰성 | LangSmith 비활성 유지. 노드별 소요·호출 수는 표준 로깅으로 남긴다(실측 4항의 근거가 된다) |
| 비밀값 | `NEO4J_*`는 `core/key/secret_manager.py` 경유(neo4j-harness §5-1). 랭그래프가 읽는 환경변수에 의존하지 않는다 |
| 버전 | `==` 핀 고정. 랭그래프는 `langchain-core`와 버전 궁합이 있어 둘을 함께 올린다 |

## 7. 검증 명령

```bash
# 계층 경계 — 랭그래프·Neo4j가 app/domain으로 샜는지
grep -rn --include="*.py" "langgraph\|from neo4j\|GraphDatabase" minseok/apps \
  | grep -E "/(app|domain)/"                 # 0줄이어야 한다

# import 지점이 각각 1파일인지
grep -rln --include="*.py" "langgraph" minseok/apps      # 1줄 (langgraph_reasoning_adapter.py)
grep -rln --include="*.py" "GraphDatabase" minseok/apps  # 1줄 (adapter/outbound/graph/)

# 구조 계약 (framework-isolation에 langgraph 포함 — neo4j 추가 후 함께 확인)
cd minseok && PYTHONPATH=apps lint-imports --config .importlinter

# 분류기 회귀 — reasoning 추가 전/후 3분기 판정이 안 바뀌었는지 (§2-1)
docker exec redoceanmap-backend-1 python scripts/eval_semantic_routing.py   # 착수 시 신설

# 회귀 (호스트에 파이썬 개발환경 없음)
docker run --rm -v /home/host/projects/com.redoceanmap:/work -w /work \
  -e PYTHONPATH=/work/minseok:/work/minseok/apps \
  minseok97/redoceanmap-backend:latest python -m pytest minseok/apps -q
```

## 8. 범위 밖 — 하지 않는다

| 항목 | 사유 |
|---|---|
| 멀티에이전트(역할 노드 협업·A2A) | langchain-harness §8 유지 — 별도 포트폴리오 저장소의 주제. 여기서는 단일 그래프의 제어 흐름만 |
| 자율 툴 호출 루프(`create_react_agent` 등) | 다음 노드를 LLM이 고르는 순간 지연·비용·비결정성이 모두 나빠진다(langchain-example-strategy §1과 동일 판정) |
| Human-in-the-loop 인터럽트 | 운영자가 대화 중간에 승인하는 화면이 없다. `crud`는 지금처럼 감지만 한다 |
| 기존 인터랙터·LCEL 체인의 그래프 재작성 | 동작하는 코드를 프레임워크로 옮기는 것은 순수 비용(langchain-harness §8) |
| LangGraph 체크포인터로 대화 이력 대체 | 이력 소유 이원화(§2-3) |
| Text-to-Cypher / LLM 생성 Cypher 실행 | §3-3 |
| Neo4j 벡터 인덱스로 pgvector 대체 | 임베딩 이중화. 그래프의 지분은 관계 확장뿐(§3-1) |
| 그래프 전용 어드민 페이지 신설 | neo4j-harness §7 그대로 — 필요하면 기존 data_source 카드 한 장 |

## 9. 미해결 — 착수 전 확인할 것

- **`reasoning` 질문이 실제로 얼마나 오는가.** 분기를 만들기 전에 기존 `langchain_turns`의
  질문을 훑어 비교·인과형 비율을 센다. 비율이 낮으면 이 문서 전체가 과설계다.
- **노드별 지연 실측 부재**(§5-1 3항). 짧은 JSON 노드(`plan`·`grade`)가 실제로 얼마나 싼지
  모른 채 8콜 상한을 잡아뒀다 — 착수 첫 커밋은 노드 1개 벤치부터다.
- **`framework-isolation`에 `neo4j`·`neo4j_graphrag` 미등록** — 랭체인과 달리 그래프 클라이언트는
  아직 계약에 없다. §4 표대로 추가하는 것이 그래프 첫 커밋의 선행 작업이다.
- **Neo4j 버전 조합 미검증**(neo4j-harness §8) — 이미지 `neo4j:5` 부동 태그 ↔ 드라이버 6.2.0.
  스모크 통과 후 태그 고정이 그래프 도입의 전제다.
