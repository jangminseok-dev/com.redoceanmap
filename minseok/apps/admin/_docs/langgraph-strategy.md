# LANGGRAPH-STRATEGY — 오케스트레이션과 데이터 계층을 **따로** 옮기는 순서 전략

admin 앱 → [[minseok/apps/admin/_docs/CLAUDE|admin CLAUDE]] ·
도입 경계(선행 필독) → [[minseok/apps/admin/_docs/langgraph-harness|langgraph-harness]] ·
그래프 운영 규칙 → [[minseok/apps/admin/_docs/neo4j-harness|neo4j-harness]] ·
서버 기동 → [[minseok/apps/admin/_docs/neo4j-strategy|neo4j-strategy]] ·
랭체인 경계 → [[minseok/apps/admin/_docs/langchain-harness|langchain-harness]]

**역할 분담:** *무엇을 어떤 모양으로 만들 수 있는가*는 langgraph-harness, *그래프에 무엇을 담아도
되는가*는 neo4j-harness, *컨테이너를 어떻게 올리는가*는 neo4j-strategy가 정한다.
**이 문서는 "어떤 순서로 · 각 단계를 무엇으로 끝났다고 판정하는가" 하나만** 다룬다.

**이 문서의 전제 한 줄:** 지금 하려는 것은 **하나의 마이그레이션이 아니라 서로 무관한 두 개의 변경**이다.

| 변경 | 무엇이 바뀌나 | 안 건드리는 것 |
|---|---|---|
| `langchain` → `langgraph` | **오케스트레이션** (선형 체인 → 상태 머신) | 데이터 계층 (pgvector·bge-m3·PG 정본) |
| `pgvector` → `+neo4j` | **검색/데이터 계층** (벡터 유사도 → 관계 탐색 추가) | 그래프 제어 흐름 (노드·엣지·상한) |

두 변경을 한 커밋에 넣으면 지연이 늘거나 답변 품질이 떨어졌을 때 **원인이 오케스트레이션인지
검색인지 가릴 수 없다.** 그래서 순서가 이 문서의 내용 전부다.

---

## 0. 주신 전략 ↔ 이 저장소 사실의 차이 (2026-07-30 실측 교정)

일반 전략은 맞지만, 이 저장소에 그대로 얹으면 어긋나는 지점이 5개다. **아래 교정이 §3~§6의 근거다.**

| # | 일반 전략의 전제 | 이 저장소의 사실 | 교정 |
|---|---|---|---|
| 1 | "langchain + pgvector로 되어 있다" | `langchain-core==1.5.1` **1개**뿐이고 체인은 LCEL 2벌(`rag_chain`·`chat_chain`, `hub/adapter/outbound/langchain_chat_engine_adapter.py`). **pgvector는 랭체인 리트리버가 아니다** — `MarketNewsSearchPort`(bge-m3 + pgvector, market 스포크 구현) 자체 포트다 | 1단계의 `existing_retriever.invoke(...)`는 **존재하지 않는다.** 노드가 감싸는 것은 랭체인 리트리버가 아니라 **허브 포트 호출**이다(§3-2) |
| 2 | "`ConversationBufferMemory`를 쓰고 있었다면 이 시점에 버린다" | 랭체인 메모리 API는 **애초에 쓰지 않는다**(`grep ConversationBufferMemory` 0건). 이력 소유자는 `langchain_sessions`·`langchain_turns`이고 인터랙터가 최근 10턴을 매 턴 주입한다 | **버릴 것이 없다.** 따라서 아래 3번이 따라온다 |
| 3 | "1단계의 실질 이득은 체크포인터(`PostgresSaver`)다" | 이 저장소에서 그 이득은 **성립하지 않는다** — 대체될 메모리가 없고, 체크포인터를 넣으면 이력이 `langchain_turns`와 체크포인트 테이블로 **이원화**된다. 게다가 `langgraph-checkpoint-postgres`는 **추가 패키지**라 langchain-harness §5 게이트를 다시 통과해야 한다 | **체크포인터 미채택**(langgraph-harness §2-3 유지). 1단계의 이득은 체크포인터가 아니라 **루프·재시도·부분 근거를 담을 상태 자리**다(§3-1) |
| 4 | "기존 체인의 각 조각을 그대로 노드로 감싼다" | 동작하는 LCEL 2벌을 그래프로 옮기는 것은 langchain-harness §8·langgraph-harness §8이 **순수 비용으로 배제**한 항목이다 | **전면 이관하지 않는다.** 그래프는 신규 목적지 `reasoning` **하나**에만 붙고, `rag`·`gemini`·`crud`는 지금 경로 그대로다(§3-3) |
| 5 | "3단계에서 Neo4j 노드를 추가한다" | Neo4j 서버는 **아직 떠 있지 않다**(로컬 이미지 없음, 볼륨은 `please_change`로 굳음, 서비스가 실운영 스택에 없음 — neo4j-strategy §0 함정 3개) | 3단계 앞에 **neo4j-strategy 0·1단계(서버 기동 + 투영)가 선행**한다. 3단계는 "코드를 쓰는 단계"이지 "DB를 만드는 단계"가 아니다 |

**그대로 채택하는 판정 3개** — ① 순서를 나눈다(오케스트레이션 → 그래프), ② pgvector를 버리지 않고
**노드 하나로 남긴다**, ③ 4단계에서 숫자로 확인한 뒤에만 다음 결정을 한다.

---

## 1. 목표 아키텍처 — 도착 지점

```
                                  ┌──────────────────────────────┐
 ask ──► classify(공유 분류기)     │  reasoning 그래프 (StateGraph) │
        ├─ crud     … 감지만 (지금과 동일)                        │
        ├─ rag      … LCEL rag_chain (지금과 동일)                │
        ├─ gemini   … LCEL chat_chain (지금과 동일)               │
        └─ reasoning ──► plan ──► retrieve ──┬─ pgvector 노드  ← bge-m3 (그대로)
                          ▲          │       └─ graph 노드     ← Neo4j 이웃 확장
                          │        grade ──► refine (최대 2회전)
                          └──────────┘
                                     compose ──► verify ──► END
                                        ▲──────────┘ (근거 이탈 1회)
```

**핵심은 pgvector를 버리는 게 아니라 노드 하나로 남긴다는 것이다.** 벡터 유사도는 여전히
pgvector(+bge-m3)가 잘하고, Neo4j는 "A와 B가 어떻게 연결돼 있나"만 담당한다
(langgraph-harness §3-1 역할 분담 표 그대로 — 정본은 PG, 그래프는 파생본).

---

## 2. 단계 요약 — 각 단계는 단독 배포·단독 롤백 가능

| 단계 | 내용 | 새 인프라 | 새 패키지 | 코드량 | 소요 |
|---|---|---|---|---|---|
| **1** | `reasoning` 분기를 LangGraph로 만든다 (근거는 pgvector만) | 없음 | `langgraph` 1개 | 중 | 중 |
| **2** | 질문 명세서 10개 + 그래프 스키마 확정 | 없음 | 없음 | **0줄** | **최대** |
| **3** | Neo4j `retrieve` 노드 **추가**(교체 아님) | neo4j 컨테이너 + 투영 배치 | 없음(`neo4j-graphrag` 기설치) | 소 | 중 |
| **4** | 1단계 질문 세트로 before/after 평가 → 통합 여부 결정 | 없음 | 없음 | 0줄 | 소 |

**2단계가 코드는 제일 적고 시간은 제일 많이 든다.** 여기를 건너뛰면 3단계에서 라벨이 증식한
그래프를 마주한다(neo4j-harness §2 명명 규칙이 사후에는 강제되지 않는다).

---

## 3. 1단계 — LangGraph로 `reasoning` 분기만 만든다 (데이터 계층 무변경)

가장 위험이 낮고 먼저 해야 하는 단계다. **이 단계에 Neo4j는 등장하지 않는다.**

### 3-1. 이 단계에서 실제로 얻는 것

체크포인터가 아니라(§0-3) **상태 자리**다. 지금 `_respond`는 `market_news.search(prompt, limit=4)`를
한 번 부르고 끝이라 재검색·재작성·부분 근거를 담을 데가 없고 인터랙터 지역 변수로 흩어진다
(langgraph-harness §1). 노드·엣지·상한이 코드에 그대로 보이는 것은 부수 효과이며, **그것만으로는
게이트 통과 사유가 아니다**(langchain-harness §5-1이 배제한 가독성 논거).

### 3-2. 무엇을 노드로 감싸는가 (교정된 형태)

```python
# hub/adapter/outbound/langgraph_reasoning_adapter.py  ← langgraph import는 이 파일에만
class ReasoningState(TypedDict):        # 상세 필드는 langgraph-harness §2-3
    question: str
    history: list[tuple[str, str]]      # 인터랙터가 langchain_turns에서 조회해 주입
    subqueries: list[str]
    evidence: list[Evidence]            # 출처(뉴스 id) 필수
    rounds: int
    regenerated: int
    answer: str
    degraded: list[str]

async def retrieve_vector(state):                      # ← 랭체인 리트리버가 아니다
    hits = []
    for q in state["subqueries"]:
        hits += await self._market_news.search(q, limit=4)   # 주입받은 허브 포트
    return {"evidence": _to_evidence(hits)}            # 부분 업데이트만 리턴
```

- 노드는 드라이버·SQL·Cypher를 직접 잡지 않고 **주입받은 포트**를 부른다(langgraph-harness §4)
  — 어댑터 안이라도 포트 경유여야 노드 단위 테스트를 스텁으로 할 수 있다.
- 노드의 모든 추론은 `ExaoneChatModel`(=`llm_orchestrator`) 재사용. 노드마다 `ChatOllama`를
  만들지 않는다(단일 모델 정책).
- 상한은 코드 상수(`MAX_RETRIEVE_ROUNDS=2` · `MAX_REGENERATE=1` · `MAX_LLM_CALLS=8`).
  자율 종료에 맡기지 않는다.

### 3-3. 건드리지 않는 것

| 대상 | 처분 |
|---|---|
| LCEL `rag_chain`·`chat_chain` | **그대로 둔다.** 그래프로 재작성하지 않는다(§0-4) |
| `langchain_sessions`·`langchain_turns` | 이력 소유자 유지. **체크포인터를 붙이지 않는다** |
| 분류기 프롬프트(ROM 1.0 공유물) | `reasoning` 추가는 ROM 1.0 동작 변경이다 — 목적지별 10문항 고정 세트의 분류 결과를 변경 전/후 표로 남긴다(langgraph-harness §2-1) |
| 응답 스키마 | `chain` 필드에 `"reasoning_graph"`만 실어 보낸다. 새 엔드포인트·새 필드 없음 |
| 가드레일 | "근거 0건이면 거부"·"crud 미실행"은 인터랙터에 남는다. 그래프가 거부를 판단하면 정책이 두 군데로 갈라진다 |

### 3-4. 완료 판정 (전부 통과해야 2단계로 간다)

- [ ] **선행:** 기존 `langchain_turns` 질문을 훑어 비교·인과형 비율을 센다 — 비율이 낮으면
      이 문서 전체가 과설계다(langgraph-harness §9 첫 항목). **이 계수 결과가 착수 근거다**
- [ ] `reasoning` 종단 **p95 ≤ 25초** 실측 (넘으면 도입 보류 또는 비동기/스트리밍 표면 분리)
- [ ] 그래프 **계층 자체의 오버헤드**(모델 호출 스텁 고정)가 추론 시간의 1% 이내
- [ ] 노드별 소요·LLM 호출 수를 표준 로깅으로 남기고 첫 실측치를 이 문서에 기록
- [ ] 분류기 회귀 표 — `reasoning` 추가 전/후로 기존 3분기 판정이 **안 바뀜**
- [ ] 상한 초과·예외 시 `rag_chain` 폴백 동작 테스트 (그래프가 새 장애 지점이 되지 않음)
- [ ] `lint-imports` 5계약 통과 · `langgraph` import 지점 1파일 · `pytest` 전체 통과
- [ ] **배포 후 안정화 기간을 둔다.** 이 단계가 운영에서 조용해진 뒤에 2단계를 시작한다

**롤백:** `ReasoningGraphPort` 계약이 langgraph를 노출하지 않으므로 어댑터를 while 루프 구현으로
갈아끼우거나 `reasoning`을 `rag`로 되돌리고 requirements 한 줄을 지우면 끝난다.

---

## 4. 2단계 — 질문 명세서와 스키마 (코드 0줄, 시간 최대)

### 4-1. 산출물 ①: 질문 10개 (그래프 스키마의 명세서)

**먼저 답할 질문: 지금 pgvector로 안 풀리는 질문이 무엇인가.** 1단계 로그(`reasoning`으로 분류된
실제 질문)에서 뽑아 **10개를 문서 파일로 적는다** — 추측으로 만들지 않는다.

```sql
-- 0단계(수요 계수) — reasoning 목적지가 아직 없으니 rag로 흘러간 질문을 손으로 훑는다
SELECT t.content AS question, t.created_at
FROM langchain_turns t
WHERE t.role = 'user' AND t.destination = 'rag'
ORDER BY t.created_at DESC LIMIT 200;

-- 2단계(명세서 작성) — 1단계 배포 후, reasoning으로 분류된 실물 목록
SELECT t.content AS question, t.created_at
FROM langchain_turns t
WHERE t.role = 'user' AND t.destination = 'reasoning'
ORDER BY t.created_at DESC LIMIT 200;
```

> `langchain_turns`는 `role`·`content`·`destination`(nullable)을 갖고, 인터랙터가 **user·assistant
> 양쪽 턴에 같은 destination을 기록**한다(`langchain_semantic_interactor.py:48,51`) — 그래서
> `role='user'` 조건이 필요하다. 질문 컬럼 이름은 `question`이 아니라 `content`다.

각 질문에 **판정 라벨**을 붙인다. 이 분류가 3단계 착수 여부를 정한다.

| 라벨 | 뜻 | 처분 |
|---|---|---|
| `vector-ok` | 단일 상권 사실 질의 — 지금 검색으로 답이 나온다 | 그래프 근거 아님 |
| `pg-join` | 2홉 이내라 **PG 조인으로 된다** (예: "같은 지역·같은 업종의 다른 상권 3곳") | **그래프 근거 아님 — PG로 푼다** |
| `graph-only` | 3홉 이상 (예: 상권→기사→주제→다른 상권) | 그래프 근거 ✅ |

**착수 조건: `graph-only`가 10개 중 3개 이상.** 미만이면 3단계를 보류하고 1단계에서 멈춘다
(neo4j-harness §5-5 1항 "PG 조인으로 답이 되면 PG를 쓴다"의 구체화).

### 4-2. 산출물 ②: 스키마는 손으로 정한다

라벨·관계·속성 목록은 이미 langgraph-harness §3-2에 있다(`Area`·`Region`·`Industry`·`Article`·
`Topic`). 2단계가 추가로 확정할 것은 **제약 Cypher와 투영 경로**다.

| 원칙 | 내용 |
|---|---|
| **LLM에 라벨을 만들게 하지 않는다** | 자유 추출하면 `사람`/`인물`/`담당자`가 각각 노드가 되고 그래프가 쓰레기가 된다. 허용 목록 밖은 버린다 |
| **정형 데이터에 LLM을 쓰지 않는다** | 상권·업종·지역·기사는 PG에 이미 관계가 있다 → **결정적 투영**. LLM으로 다시 추출하는 것은 비용을 내고 정확도를 낮추는 일이다 |
| **LLM 추출 허용 구간은 `Topic` 한 칸** | 비정형 본문에서만. 사전 정의된 주제 슬러그에 매칭되지 않으면 버린다 |
| **추출기 선택은 §4-2-1에서** | `LLMGraphTransformer`는 이 저장소에서 **세 번째 선택지**다. 이유는 아래 표(실측) |

### 4-2-1. `Topic` 추출기 3안 비교 (2026-07-30 실측)

**LLM 추출이 필요한 라벨이 몇 개인가**로 갈린다 — 그 답은 §4-1 명세서에서 나온다.
`LLMGraphTransformer`가 틀린 도구라는 뜻이 아니라, **이 저장소에서는 세 번째 선택지**라는 뜻이다.

| 안 | 도구 | 신규 패키지 | 채택 조건 |
|---|---|---|---|
| **A0 (현재)** | **LLM 없음** — `area_tag` 30종을 결정적으로 `Topic`에 투영(2026-07-30 완료) | **0** | 지금 상태. 추출기가 아직 **필요하지 않다** — 비정형 본문에서 주제를 뽑아야 할 이유가 생기기 전까지 A~C 논의는 보류다 |
| **A** | 기존 `ExaoneChatModel` + JSON 프롬프트 + 허용 슬러그 화이트리스트 | **0** | 본문 기반 주제가 필요해지고, 그 대상이 `Topic` **한 칸**일 때 |
| **B** | `neo4j-graphrag`의 `LLMEntityRelationExtractor` (+`SchemaBuilder`) — **이미 설치돼 있다**(1.18.0, PDF 추출기로 사용 중) | **0** | 라벨·관계가 여러 개로 늘어 스키마 지정 추출이 필요해질 때. `LLMInterface` 구현체로 `llm_orchestrator`를 감싸 단일 모델 정책 유지(내장 `OllamaLLM` 직결은 수렴 규칙 위반이라 쓰지 않는다) |
| **C** | `langchain_experimental.graph_transformers.LLMGraphTransformer` | **14** | A·B가 부족하다는 **실측**이 나온 뒤, langchain-harness §5 게이트 재통과 후 |

**C의 비용 — `pip install --dry-run` 실측 14개 패키지:**

```
langchain-experimental 0.4.2
  └─ langchain-community 0.4.2 → langchain-classic 1.0.8   ← 1.x에서 개명된 구 langchain 메타패키지
     + langchain-text-splitters · pydantic-settings · aiohttp · yarl · multidict · attrs · ...
```

- `requirements.txt:32`가 명시한 **"langchain 메타패키지는 넣지 않는다"를 전이 의존으로 우회**하는 형태가 된다.
  버전 호환 자체는 문제없다(`langchain-core<2.0.0,>=1.4.0` ↔ 우리 1.5.1).
- **기본 추출 경로를 우리 모델로는 탈 수 없다.** `LLMGraphTransformer`의 기본 경로는
  `with_structured_output`(=tool calling)을 요구하는데, `ExaoneChatModel`은 `_generate`/`_agenerate`만
  구현하고 `bind_tools`가 없다 → `NotImplementedError`. 프롬프트+JSON 폴백 경로로만 쓸 수 있고,
  **그것은 A안과 같은 것**이다. `allowed_nodes`·`strict_mode`의 값어치가 여기서 대부분 깎인다.
- 따라서 C를 논의할 자리는 "추출이 안 된다"가 아니라 **"B의 스키마 지정 추출로도 라벨 품질이
  안 나온다"**는 실측이 나왔을 때다.

### 4-3. 예상해야 할 비용 2개

| 비용 | 내용 | 이 저장소의 처분 |
|---|---|---|
| **엔티티 해소** | "성수동"·"성수1가"·`trdar_code=3110001`을 한 노드로 합치는 작업. 자동화가 잘 안 된다 | **PG의 코드값을 `external_id`로 삼아 애초에 발생시키지 않는다** — 정형 투영이라 표기 변형이 그래프에 들어올 자리가 없다. 라벨별 `external_id` 유니크 제약으로 못 박고, 텍스트 표기는 `name` 속성일 뿐 식별자가 아니다. 해소 문제는 `Topic` 한 칸에서만 남는다 |
| **추출 비용** | 문서 전체를 LLM으로 돌리면 청크당 호출이 발생한다. 로컬 7.8B에서 1콜 ≈ 3.8초 | **전체 코퍼스에 돌리지 않는다.** `Topic` 추출 대상은 `graph-only` 질문이 실제로 걸리는 부분집합(예: 최근 N일 상권 뉴스)으로 한정하고, 야간 배치로 분리한다 |

### 4-4. 완료 판정

- [ ] 질문 10개 + 라벨 판정 표가 문서로 존재하고 `graph-only` ≥ 3 — **미완. 남은 핵심 작업이다**
- [x] 라벨·관계·속성 목록 + **제약/인덱스 `.cypher` 파일** → `scripts/graph_constraints.cypher`
      (제약 5 + 인덱스 1, 전부 `IF NOT EXISTS`)
- [x] `scripts/project_graph.py` 투영 범위·멱등 방식 확정 → 단방향 `MERGE`, 2회 회귀 통과.
      ⚠️ **"언제"는 미정** — 수동 실행 상태. cron 등록은 이미지 재빌드가 선행
- [ ] 그래프가 죽었을 때의 응답 — 설계만 있고 코드 없음. 질의 경로와 함께 만든다
- [x] `framework-isolation` 계약에 `neo4j`·`neo4j_graphrag` 추가 완료

> **투영이 스키마 설계를 앞질렀다.** 원래 순서는 §4-1(질문 10개) → §4-2(스키마) → 투영인데,
> 2026-07-30에 요청으로 **투영을 먼저 실행**했다. 라벨·관계가 이미 §3-2에 고정돼 있어 결과물은
> 같지만, **`graph-only` 질문 명세서(§4-1)는 여전히 비어 있다** — 그것이 3단계(질의 코드)의
> 선행 조건이라는 판정은 유효하다. 데이터가 있다는 것이 코드를 써도 된다는 뜻이 아니다.
> 실측 결과 → neo4j-strategy §4 1단계.

---

## 5. 3단계 — Neo4j 노드를 **추가**한다 (교체 아님)

### 5-1. 선행 — 인프라가 먼저다

neo4j-strategy **0단계**(구 스택 compose에 서비스 정의 · 굳은 볼륨 폐기 · 힙/캐시 고정 ·
드라이버 6.2.0 ↔ 서버 5.26 스모크) → **1단계**(제약 + 투영 배치 2회 멱등 확인)를 통과한 뒤에
파이썬 코드를 쓴다. `neo4j-graphrag`의 **requirements 반영 + 이미지 재빌드**도 여기 포함된다
(지금은 실행 중 컨테이너에 수동 설치만 된 상태 — 컨테이너 재생성 시 사라진다).

### 5-2. 코드 — 노드 하나와 조건부 엣지

```python
async def retrieve_graph(state):        # graph 노드 — Cypher는 화이트리스트에서만
    rows = await self._graph.expand("area_articles", id=state["entity"], limit=5)
    return {"evidence": _to_evidence(rows)}
```

- **Text-to-Cypher는 쓰지 않는다.** `GraphCypherQAChain`처럼 LLM이 Cypher 문자열을 만들어
  실행하는 경로는 채택하지 않는다 — 잘못된 Cypher·전체 스캔의 대가가 운영 DB에서 발생한다
  (langchain-example-strategy §8 "LLM 생성 SQL 직접 실행 금지"와 같은 판정).
- 대신 **파라미터화 템플릿 딕셔너리**(langgraph-harness §3-3)를 쓰고 **LLM은 템플릿 이름과 인자만**
  고른다. 세션은 읽기 전용, 모든 조회에 `LIMIT` + 타임아웃(서버측 `db.transaction.timeout=5s`).
- 검색 순서는 **`entities`(분류기가 이미 뽑아준다) → 그래프 노드 매칭 → 이웃 확장 → 그 키로 PG
  본문 조회**다. 그래프는 *무엇을 더 읽을지*만 정하고, 읽는 것은 PG다.
- 라우팅은 `retrieve` 안에서 `vector` / `graph` / `both`로 갈린다. **목적지(`destination`)를
  늘리지 않는다** — `rag`·`gemini`를 그래프로 옮기지 않는다.

### 5-3. 완료 판정

- [ ] `graph-only` 질문 3개 이상이 그래프 근거로 답이 나온다(§4-1 명세서 기준)
- [ ] Neo4j 컨테이너를 **죽인 상태에서** 같은 질문이 500이 아니라 `degraded` + 얕은 답을 낸다
- [ ] 화이트리스트 밖 Cypher가 실행되는 경로 0건 (거부 테스트 포함)
- [ ] `reasoning` p95가 1단계 실측 대비 허용선(25초) 안에 유지
- [ ] `GraphDatabase` import 지점 1파일 · 허브 밖 0건 · `lint-imports` 통과
- [ ] EXAONE 추론 지연이 그래프 기동 전/후로 변하지 않음(같은 질문 재실행 비교)

---

## 6. 4단계 — 평가하고 나서 통합 여부 결정

1·2단계에서 만든 **질문 10개로 before/after를 비교한다.** 그래프가 실제로 이겼는지 숫자로 확인한
뒤에야 다음 결정을 한다.

| 지표 | 측정 방법 |
|---|---|
| 정답 근거 포함률 | 질문 10개 × (1단계 답 / 3단계 답) 수동 채점 — 근거에 실재하는 사실만 인정 |
| 근거 0건 거부율 | 그래프 추가로 줄었는가 |
| 종단 지연 p50/p95 | 같은 질문 세트로 두 경로 비교 |
| LLM 호출 수 | 노드 로그 합계 — 회전이 늘었으면 지연의 원인이 여기다 |

**기본값은 3단계에서 멈추는 것이다.** Neo4j에도 네이티브 벡터 인덱스가 있어 `Neo4jVector`로
임베딩까지 옮기면 DB를 하나로 줄일 수 있지만, **pgvector + bge-m3가 이미 잘 돌고 있다.**
옮기면 임베딩이 이중화되고 운영 부담(백업·튜닝·재색인)만 늘어난다 — langgraph-harness §8의
"Neo4j 벡터 인덱스로 pgvector 대체" 금지와 같은 판정이며, **이 문서도 그 기본값을 유지한다.**

---

## 7. 커밋 단위

| 순서 | 커밋 | 완료 판정 |
|---|---|---|
| 0 | `reasoning` 수요 계수 (코드 0줄, 문서만) | 비교·인과형 비율 기록 → 착수 여부 결정 |
| 1 | `langgraph` 추가 + `ReasoningGraphPort` + 어댑터 + 분류기 4번째 목적지 | §3-4 체크리스트 |
| 2 | 질문 명세서 + 스키마·제약 `.cypher` + 투영 스크립트 (그래프 접속 코드 없음) | §4-4 체크리스트 |
| 3 | neo4j 서버 기동 + 투영 배치 (neo4j-strategy 0·1단계) | 멱등 2회 · 스모크 · 자원 상한 |
| 4 | `GraphExpandPort` + graph 노드 + 조건부 라우팅 | §5-3 체크리스트 |
| 5 | 평가 리포트 (문서만) | §6 지표 4개 표 |

각 커밋은 **단독 배포 가능**해야 하고, 기존 엔드포인트 동작을 바꾸지 않는다.
**1과 4를 한 커밋에 넣지 않는다** — 이 문서 전체의 이유가 그것이다.

---

## 8. 흔한 실패 지점

| 실패 | 이 저장소에서 어떻게 나타나나 | 방어 |
|---|---|---|
| **전부 그래프로 만들기** | 대부분의 질문은 여전히 단순 벡터 검색이다(`rag`). 그래프는 다중 홉 보조 무기다 | 목적지 확대 금지(§5-2) · `pg-join` 라벨로 걸러내기(§4-1) |
| **스키마 없이 시작** | 2단계를 건너뛰면 3단계에서 라벨이 증식한 그래프를 마주한다 | 허용 목록 + `external_id` 유니크 제약(§4-2) |
| **한 번에 다 바꾸기** | 느려졌을 때 랭그래프 탓인지 Neo4j 탓인지 못 가린다 | §7 커밋 분리 · 각 단계 지연 실측 기록 |
| **동작하는 코드를 옮기기** | LCEL 2벌을 그래프로 재작성 → 순수 비용 | §3-3 건드리지 않는 것 표 |
| **이력을 이원화하기** | 체크포인터 도입 → `langchain_turns`와 체크포인트가 각자 이력을 갖는다 | 체크포인터 미채택(§0-3) |
| **정형 데이터를 LLM으로 추출** | 상권·업종 관계를 LLM이 다시 뽑아 정확도만 떨어진다 | 결정적 투영, LLM은 `Topic` 한 칸(§4-2) |
| **노드를 "에이전트"라 부르기 시작** | 그 순간 범위 밖(멀티에이전트 = 별도 포트폴리오 저장소 주제) | 단일 그래프의 **결정적** 제어 흐름만 |

---

## 9. 검증 명령

```bash
# 1단계 — 계층 경계: langgraph가 app/domain으로 샜는지 (0줄이어야 한다)
grep -rn --include="*.py" "langgraph" minseok/apps | grep -E "/(app|domain)/"
grep -rln --include="*.py" "langgraph" minseok/apps      # 1줄 (langgraph_reasoning_adapter.py)

# 2·3단계 — 그래프 접속 코드가 허브 밖으로 샜는지 (0줄)
grep -rn --include="*.py" "GraphDatabase\|neo4j_graphrag" minseok/apps | grep -v "apps/hub/"

# 구조 계약 (framework-isolation에 neo4j·neo4j_graphrag 추가 후 함께 확인)
cd minseok && PYTHONPATH=apps lint-imports --config .importlinter

# 체크포인터 미도입 회귀 — 0줄이어야 한다
grep -rn --include="*.py" "PostgresSaver\|SqliteSaver\|checkpointer" minseok/apps
grep -rn "langgraph-checkpoint" minseok/requirements.txt

# Text-to-Cypher 미도입 회귀 — 0줄이어야 한다 (영구 금지)
grep -rn --include="*.py" "GraphCypherQAChain" minseok/apps

# 추출기 — A·B안이면 0줄. 값이 나오면 §4-2-1 C안 게이트 통과 기록이 있어야 한다
grep -rn --include="*.py" "LLMGraphTransformer" minseok/apps
grep -n "langchain-experimental\|langchain-community\|langchain-classic" minseok/requirements.txt

# 회귀 (호스트에 파이썬 개발환경 없음 — 전부 도커 경유)
docker run --rm -v /home/host/projects/com.redoceanmap:/work -w /work \
  -e PYTHONPATH=/work/minseok:/work/minseok/apps \
  minseok97/redoceanmap-backend:latest python -m pytest minseok/apps -q

# 3단계 인프라 — 구 스택에서 실행 (neo4j-strategy §6)
cd /home/host/projects/redoceanmap && docker compose --profile graph ps neo4j
```

---

## 10. 범위 밖 — 이 문서가 하지 않는 것

| 항목 | 사유 |
|---|---|
| LangGraph 체크포인터 도입 | 이력 소유 이원화(§0-3) + 추가 패키지 게이트 |
| 기존 LCEL 체인의 그래프 재작성 | 동작하는 코드를 프레임워크로 옮기는 것은 순수 비용(§0-4) |
| Neo4j 벡터 인덱스로 pgvector 대체 | 임베딩 이중화. 그래프 지분은 관계 확장뿐(§6) |
| Text-to-Cypher / LLM 생성 Cypher 실행 | 화이트리스트 템플릿 + 읽기 전용 세션(§5-2) |
| `langchain-experimental`(`LLMGraphTransformer`) 선(先)도입 | 전이 의존 **14개**(`langchain-community`·`langchain-classic` 포함)를 끌고 오고, 기본 경로는 우리 모델의 tool calling 부재로 못 탄다 — A·B안 실측 후 재논의(§4-2-1) |
| 멀티에이전트·A2A·자율 툴 루프 | 별도 포트폴리오 저장소 주제(langchain-harness §8 유지) |
| 그래프 전용 어드민 페이지 | neo4j-harness §7 — 필요하면 기존 data_source 카드 한 장 |
| 그래프 백업 크론 | 파생본이라 복구 대상이 아니다. 재투영이 복구 절차(neo4j-strategy §5) |

## 11. 미해결 — 착수 전 확인할 것

- **0단계(수요 계수)가 아직 안 돌았다.** `reasoning`형 질문 비율이 낮으면 §3 이후 전체가 과설계다.
  이 문서의 유일한 무조건 선행 작업이다.
- **`destination`이 nullable이다** — ROM 2.0 이전에 쌓인 턴은 값이 비어 있을 수 있어 §4-1 SQL의
  모집단이 실제 이력 전체보다 작다. 0단계 계수에서 `destination IS NULL`인 턴 수를 함께 세고,
  비율이 크면 그 구간은 손으로 표본을 뜬다.
- **노드별 지연 실측 부재** — 짧은 JSON 노드(`plan`·`grade`)가 얼마나 싼지 모른 채 8콜 상한을
  잡아뒀다. 1단계 첫 커밋은 노드 1개 벤치부터다.
- **`graph-only` 3개 기준은 임의값이다** — §4-1 판정 표를 처음 채울 때 근거와 함께 재확정한다.
- ~~드라이버 6.2.0 ↔ 서버 5.26 실연결 미검증~~ → **2026-07-30 해소.** neo4j-strategy 0단계 완료
  (서버 5.26.28 기동 · 드라이버 왕복 성공 · EXAONE 추론 지연 회귀 없음). 3단계의 인프라 전제는
  충족됐고, 남은 선행은 §4-4(스키마·투영) + `neo4j-graphrag` 이미지 반영이다.
