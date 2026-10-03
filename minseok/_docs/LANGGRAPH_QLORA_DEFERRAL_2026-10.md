# LangGraph · QLoRA 미도입 결정 기록 (2026-10-03 정리)

로드맵 → [[minseok/_docs/ROADMAP|ROADMAP]] ·
LangGraph 도입 경계 → [[minseok/apps/admin/_docs/langgraph-harness|langgraph-harness]] ·
도입 순서 → [[minseok/apps/admin/_docs/langgraph-strategy|langgraph-strategy]] ·
Neo4j 게이트 판정 → [[minseok/apps/admin/_docs/neo4j-e4-handoff|neo4j-e4-handoff]] ·
LLM 교체 평가 → [[minseok/_docs/LLM_SWAP_EVAL_2026-09-14|LLM_SWAP_EVAL]]

**한 줄 결론:** 둘 다 "안 한 것"이 아니라 **게이트를 세워 판정했고 결과가 보류·폐기로 나온 것**이다.
LangGraph는 쓸 자리(`reasoning` 분기)에 실수요가 없었고, QLoRA는 학습 대상 모델이 라이선스
때문에 교체 예정이었으며 GPU 예산도 한계치였다. 2026-10-03 기준 재판정해도 결론은 같다 —
이유는 §3에 적는다.

---

## 0. 현재 상태 (2026-10-03 실측)

| 항목 | 상태 |
|---|---|
| `langgraph` 패키지 | **미설치.** `requirements.txt`에 `langchain-core==1.5.1` 1개뿐. `.importlinter` `framework-isolation`에 이름만 선등록(app·domain 유입 차단) |
| chat 오케스트레이션 | `apps/chat/app/use_cases/chat_interactor.py` **3,947줄 · 메서드 80개 · 답변 분기 약 15개**. 라우팅은 `_route_domain` 결정론 규칙, LLM 분류는 보조 |
| 순환(loop) | **0개.** JSON 파싱 실패 시 1회 재시도만 있다. 재검색·근거 재평가 루프 없음. 되묻기(`_answer_market_clarify`)는 LLM 없이 즉시 반환 |
| LLM 호출 지점 | 인터랙터 안 7곳 |
| 생성 모델 | Gemma 4 e4b QAT (Ollama 6.1GB, Apache 2.0). 생성 슬롯 1개(`OLLAMA_NUM_PARALLEL=1`), 정상 질문 p95 약 1.5분, FIFO 대기열 |
| QLoRA 학습 환경 | **폐기됨(2026-09-15).** EXAONE fp16 가중치 30GB·학습용 `.venv`(torch·peft·bitsandbytes·trl) 삭제. 학습 스크립트는 `scripts/train_moderation_v1.py`(유해분류 소형 모델)만 남음 |
| 실사용 질문 | `messages` 사용자 턴 294건 · 대화 169건 |
| 뉴스 라벨 | `news_labels` Gemma 141,537건 · EXAONE 105,402건(재라벨 진행 중, 완료 뒤 삭제 예정) |
| 골든셋 | `apps/chat/tests/eval/golden_set.jsonl` — baseline 134건(평가용) |
| GPU | RTX 3050 8GB (WSL2). Ollama가 keep_alive 24h로 상주 |

---

## 1. LangGraph — 왜 안 썼나

### 1-1. 결정 경위

| 시점 | 내용 |
|---|---|
| 2026-07-28 | langgraph-harness 작성. **용도를 `reasoning` 분기 하나로 한정** — 기존 `crud`·`rag`·`gemini` 3분기는 동작하는 LCEL 체인 2벌이라 그래프로 옮기는 것을 "순수 비용"으로 배제 |
| 2026-07-30 | langgraph-strategy 작성. 일반 전략 대비 이 저장소의 차이 5개 교정(§1-2). 순서 확정: `reasoning` 분기(pgvector 근거만) → 멀티홉 수요 로그 확인 → Neo4j 노드 추가 |
| 2026-08-24 | E4 Neo4j 게이트 판정. 실 질문 코퍼스 129건 전수 → **graph-only 0/10**. 3단계(질의 코드) 보류 확정 |
| 2026-10-03 | 재판정(이 문서 §3-1). 결론 유지 |

### 1-2. 보류 사유 (langgraph-harness §5 게이트 기준)

| # | 게이트 항목 | 판정 | 근거 |
|---|---|---|---|
| 1 | 랭그래프 없이는 과도하게 비싼 구체 작업 | **약하게 채워짐** | 재검색·재작성 루프 2개 정도는 `while` + 상태 dict로 된다. LangGraph의 값은 "노드·엣지가 코드에 보인다"인데 이건 **가독성 논거**라 하네스가 도입 사유로 인정하지 않는다. "루프 3개 이상이면 재판정" — 현재 **0개** |
| 2 | 도입 범위 최소화 | 설계만 완료 | `langgraph` 1개(`checkpoint*`·`prebuilt` 미사용, 메타패키지 금지) |
| 3 | 지연·메모리 실측과 허용선 | **미측정** | 허용선은 정했다: `reasoning` 종단 p95 ≤ 25초 · 그래프 계층 오버헤드 ≤ 추론 시간 1% |
| 4 | 제거 계획 | 완료 | `ReasoningGraphPort`가 랭그래프를 노출하지 않으므로 while 구현으로 교체 또는 `reasoning`→`rag` 되돌림 |

### 1-3. 일반 도입 논거가 이 저장소에서 성립하지 않는 이유

| 일반 논거 | 이 저장소의 사실 |
|---|---|
| "체크포인터(`PostgresSaver`)가 1단계의 실질 이득" | 대체할 `ConversationBufferMemory`가 **애초에 없다**(0건). 이력 소유자는 `langchain_sessions`·`langchain_turns`이고 인터랙터가 최근 10턴을 매 턴 주입한다. 체크포인터를 넣으면 이력이 **이원화**되고, `langgraph-checkpoint-postgres`는 추가 패키지라 게이트를 다시 통과해야 한다 |
| "기존 리트리버를 노드로 감싼다" | pgvector는 랭체인 리트리버가 아니라 `MarketNewsSearchPort` **자체 포트**다. `existing_retriever.invoke(...)`는 존재하지 않는다 |
| "기존 체인을 그대로 노드로 옮긴다" | 동작하는 LCEL 2벌의 이관은 하네스가 **순수 비용으로 배제**한 항목 |
| "Neo4j 노드를 추가한다" | 데이터 투영은 완료(노드 3,582 / 관계 79,188, cron 02:15)됐지만 **질의 코드는 0줄**. 투영과 질의는 다른 게이트 — 데이터가 있다는 것이 코드를 써도 된다는 뜻이 아니다 |

### 1-4. 결정적 요인 — 수요 0

`reasoning` 분기가 노리던 질문은 비교·인과형 다단계 추론("성수동과 연남동 중 카페는 어디가 낫고 왜?")이다.
2026-08-24 E4 판정에서 실 질문 129건을 전수 분류한 결과 **그래프로만 답할 질문이 0건**이었다
(`vector-ok` 5 · `pg-join` 5 · `graph-only` 0). 후속 단계(GraphRAG)의 수요가 0이면 그 단계를 위한
선행 단계(LangGraph `reasoning` 분기)도 착수 조건을 잃는다.

---

## 2. QLoRA — 왜 안 썼나

### 2-1. 결정 경위 — 환경까지 만들었다가 폐기

| 시점 | 내용 |
|---|---|
| 2026-07-15 | **단일 모델 전략 확정.** EXAONE 3.5 7.8B fp16 원본 하나만 유지(AWQ 2종·2.4B 삭제). bnb-QLoRA backward 검증 완료 — NF4 + double quant + bf16, r=16 all-linear, seq 512, batch 1: trainable 0.53%(42M), base 6.49GiB, **peak 7.69GiB / 8GB**. `modeling_exaone.py` 로컬 수정 2건 필요(transformers 5.13 `create_causal_mask` 시그니처) |
| 2026-08-17 | **E5 라이선스 실사.** EXAONE 3.5 = "EXAONE AI Model License Agreement 1.1 - NC" — 연구 전용, 상용 금지(모델·파생물·**Output까지**). **파인튜닝 투자 보류 명시**(NC 파생물도 NC). 공개 서비스 전 모델 교체 확정 |
| 2026-09-15 | Gemma 4 e4b QAT로 교체(③-M5②). EXAONE 가중치 30GB·학습용 `.venv` 삭제 → **QLoRA 환경 폐기** |
| 2026-10-03 | Gemma 기준 재판정(§3-2). 학습 목표 부재로 보류 유지 |

### 2-2. 보류 사유 (2026-07~09)

| # | 사유 | 상세 |
|---|---|---|
| 1 | **라이선스** | NC 모델의 파생물은 NC. 공개 서비스 전 교체가 확정된 모델에 학습을 투자할 이유가 없었다. 교체 후보 제약(중국 모델·중국 베이스 파인튜닝 배제)도 함께 걸려 있었다 |
| 2 | **GPU 예산** | peak 7.69GiB / 8GB — batch 1 고정 + gradient accumulation, seq ≤ 512, paged_adamw_8bit, gradient checkpointing, **학습 중 Ollama 종료**가 전부 필요한 한계치. OOM 시 target_modules 축소(q/k/v/o) 또는 r=8까지 내려가야 했다 |
| 3 | **멀티태스크 SFT 필수** | 한 모델이 인텐트 분류 + 최종 답변을 맡는 구조라 인텐트 데이터만 학습하면 대화 능력이 파괴된다. 일반 한국어 instruction 데이터 혼합이 필요 — 이 예산으로는 현실성이 낮았다 |
| 4 | **서빙 경로 미해결** | LoRA merge(fp16) → GGUF 변환 → Ollama 등록 경로가 구축되지 않았다. 학습이 끝나도 운영에 올릴 길이 없었다 |
| 5 | **로드맵 방향** | ROADMAP 자체 모델 경로는 유해분류 v1(완료) → v2 → 뉴스 감성 한국어 경량 모델(KcELECTRA 파인튜닝). **자체 LLM 사전학습 금지**. LLM 파인튜닝은 경로에 없다 |

---

## 3. 2026-10-03 재판정 — 지금 도입하면

### 3-1. LangGraph — 여전히 아니다

| 관점 | 판단 |
|---|---|
| 아픈 곳 | **오케스트레이션이 아니라 파일 크기**다. `chat_interactor.py` 3,947줄·분기 15개가 한 클래스에 있다. 이건 핸들러 분해로 풀 리팩터링 과제고, LangGraph로 감싸면 3,947줄이 노드 15개로 재배치될 뿐이다 |
| 루프 | **0개.** 하네스 재판정 기준(3개 이상)에 닿지 않는다 |
| 생성 슬롯 1개 | 그래프를 깔면 plan → retrieve → grade → refine처럼 호출이 늘어나는데, 슬롯이 하나라 **질문당 호출 수가 곧 뒤 사람의 대기 시간**이다. 현재 p95 1.5분이 2~3배가 된다 |
| 수요 | 8월 129건 → 10월 294건. 다단계 추론 질문 비율이 뒤집힐 규모가 아니다 |
| 대안 | 인터랙터를 분기별 핸들러로 분해(프레임워크 없이). 끝나면 LangGraph가 필요한지 자연히 드러난다 — 필요 없다는 결론이 날 확률이 높다 |
| 포트폴리오 목적이면 | 별도 저장소(A2A·MCP 포트폴리오 계획)가 맞는 자리. 이 서비스 코드에 넣지 않는다 |

### 3-2. QLoRA — 가능해졌지만 학습시킬 데이터가 없다

7월 대비 좋아진 것: Gemma 4 e4b는 **Apache 2.0**(파생물 제약 없음), 모델도 EXAONE 7.8B보다 작다.
8GB에서 QLoRA가 7월처럼 한계치가 아닐 가능성이 있다. 그러나 학습 목표가 비어 있다.

| 후보 | 데이터 | 판정 |
|---|---|---|
| 뉴스 라벨링 | Gemma 라벨 14.1만 건 | **의미 없음.** 교사 모델의 출력을 같은 모델에 되먹이는 것. 이 데이터의 정답 용도는 ROADMAP의 **KcELECTRA 경량 분류기 증류**이고, 그건 QLoRA가 아니다 |
| 채팅 답변 품질 | 골든셋 134건 | **두 자릿수 부족.** 평가용이지 SFT 데이터가 아니다. 현재 품질은 프롬프트·결정론 가드·AnswerSkeleton으로 관리 중 — 모델을 바꾸면 가드 전부 재검증 |
| 의도 분류 | 실 질문 294건 | **부족.** 라벨링해도 SFT 규모가 안 된다 |

운영 제약도 그대로다: 학습 중 Ollama를 내려야 하는데 **라이브 사용자가 있고 큐가 1슬롯**이다.
QAT 체크포인트 위에 LoRA를 얹은 뒤 재양자화해 Ollama에 올리는 경로는 7월에도 미해결로 남긴 과제다.

---

## 4. 재판정 조건 — 이것이 채워지면 다시 본다

| 대상 | 조건 | 측정 방법 |
|---|---|---|
| LangGraph | ① 인터랙터 핸들러 분해가 끝난 뒤 ② 분해된 핸들러 안에 **진짜 순환이 3개 이상** 생길 때 ③ `/admin/questions`에서 다단계 추론 질문이 graph-only ≥ 3/10 | langgraph-strategy §4-1 계수 방법. langgraph-harness §5-1 게이트 4문항 전부 재통과 |
| QLoRA | ① 실사용 질문 **수천 건** ② 실패 사례에 "왜 틀렸는지" 라벨이 붙기 시작 ③ Gemma e4b 기준 8GB QLoRA 실측(peak 메모리·학습 시간) ④ LoRA → GGUF → Ollama 등록 경로 구축 | 학습은 `models/<이름>/v<n>/` + 지표 JSON + git 태그(ROADMAP 학습 파이프라인 규칙). MLflow/DVC 금지 유지 |

**지금 할 가치가 있는 것**은 둘의 대체물이다.

- LangGraph 대신 → `chat_interactor.py` 핸들러 분해(프레임워크 없이, 분기 하나씩).
- QLoRA 대신 → KcELECTRA 감성 경량 모델. RTX 3050으로 충분하고 Ollama를 멈추지 않으며 ROADMAP E3(2026-10 감성 재채점)와 맞물린다.
