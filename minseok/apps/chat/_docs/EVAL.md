# chat 품질 평가 시스템 (EVAL)

phase0(의도 분류) → phase1(상권·업종 선택) → phase2(최종 서술) 파이프라인의 품질을
**결정론 지표**로 재고, 프롬프트·모델 변경 시 회귀를 pytest 게이트로 잡는다.

```
golden_set.jsonl ──[러너: 실제 EXAONE 7.8B, -m ollama]──> trace.jsonl (커밋)
                                                              │
                                        [채점기: 순수 함수, LLM 불필요]
                                                              │
                                          [게이트: baseline.json 대비 회귀 검증]
```

## 설계 원칙

- **러너와 게이트 분리.** 러너만 LLM이 필요하고(백엔드 PC), 게이트는 커밋된
  trace.jsonl을 채점만 하므로 기본 검증(`-m "not ollama"`)에 포함된다.
- **프로덕션 무손상 계측.** 인터랙터를 고치지 않는다 — 러너가 모듈 네임스페이스의
  `llm_orchestrator`를 "진짜 호출 + 기록" 프록시로 교체한다(기존 테스트와 같은 기법).
  phase 식별은 프롬프트 접두사로 확정.
- **데이터 고정, LLM만 진짜.** 허브 포트는 스냅샷 스텁(`tests/eval/snapshot_stubs.py`)
  — 상권 요약·업종은 실 DB 덤프(`scripts/dump_chat_eval_snapshot.py`), 팩트 통계는
  trdar_code 시드 합성. DB가 분기 갱신돼도 골든셋 정답이 흔들리지 않는다.
- **LLM-as-judge 불사용.** 단일 모델 정책상 7.8B가 자기 답을 심판하는 순환이 된다.
  전 지표가 규칙 기반이라 같은 트레이스는 항상 같은 점수다.

## 파일

| 파일 | 역할 |
| --- | --- |
| `tests/eval/golden_set.jsonl` | 골든셋 120문항 — market 40(지역 20·미지정 10·서울외 10) · stock 30(한국 15·해외 10·모호 5) · market_news 20 · general 20 · multiturn 10 |
| `tests/eval/snapshot_stubs.py` | 허브 포트 고정 스텁(실덤프 우선, 없으면 내장 합성) |
| `tests/eval/test_eval_runner.py` | 러너(`-m ollama`) — trace.jsonl 생성 |
| `tests/eval/trace.jsonl` | 실행 기록(케이스별 phase 호출·응답·지연) — 커밋 대상 |
| `tests/eval/test_quality_gate.py` | 게이트 — 절대 규칙 + baseline 회귀 |
| `tests/eval/baseline.json` | 기준 지표 — 게이트 첫 실행이 자동 기록 |
| `domain/services/eval_scorer.py` | 채점기(순수 도메인 서비스) |
| `domain/value_objects/eval_trace.py` | EvalCase · CaseTrace 값 객체 |
| `tests/domain/test_eval_scorer.py` | 채점 로직 단위 테스트(LLM 불필요) |

## 지표

| 지표 | 방식 | 게이트 |
| --- | --- | --- |
| intent_accuracy · 혼동행렬 | phase0 4분류 라벨 대조 | 회귀(-3%p) |
| stock_query_accuracy | 종목 질의 허용 목록 대조 | 회귀(-3%p) |
| phase0_parse_failure_rate | 의도 JSON 파싱 실패(→market 폴백) | 관측 |
| nonseoul_guard_rate | 서울 외 지역 결정론 차단(phase1 미호출 + "준비 중") | **절대 100%** |
| region_hit_rate | 지역 명시 질문의 추천 상권 어간 적중 | 회귀(-3%p) |
| phase1_guard_activation_rate | phase1 원답 ≠ 최종 추천(가드 보정) 비율 — "가드가 없었으면 틀렸을 비율" | 관측 |
| inherit_success_rate | 멀티턴 직전 추천 승계(부분집합 판정) | 회귀(-3%p) |
| hallucinated_number | 답변 숫자가 주입 컨텍스트·질문에 없음 | 회귀(건수 비증가) |
| forbidden_phrase / missing_disclaimer / location_claim | 매매지시·확률단정 / 책임 고지 / 입지 창작(호선·환승·관문) 정규식 | **절대 0건 / 100%** |
| latency p50·p95 | phase별 프록시 타이밍 | 관측 |

환각 숫자는 휴리스틱(파생 수치·어림 표현은 오탐 가능)이라 절대 0이 아니라
**건수 비증가** 회귀로 건다. 위반 목록이 리포트에 남으므로 수동 검토로 확정한다.

## 실행 순서

```bash
# 1) (선택·권장) 실 스냅샷 덤프 — 백엔드 PC, market DB 필요, 1회
docker run --rm --network host \
  -v /home/host/projects/com.redoceanmap:/work -w /work \
  -e PYTHONPATH=/work/minseok:/work/minseok/apps \
  minseok97/redoceanmap-backend:latest \
  python minseok/scripts/dump_chat_eval_snapshot.py

# 2) 러너 — 백엔드 PC, ollama(exaone3.5:7.8b) 필요, DB 불필요
docker run --rm --network host \
  -v /home/host/projects/com.redoceanmap:/work -w /work \
  -e PYTHONPATH=/work/minseok:/work/minseok/apps \
  minseok97/redoceanmap-backend:latest \
  python -m pytest minseok/apps/chat/tests/eval/test_eval_runner.py \
    -q -p no:cacheprovider -m ollama -s

# 3) 게이트 — 어디서든(LLM 불필요). 첫 실행이 baseline.json을 기록한다
docker run --rm \
  -v /home/host/projects/com.redoceanmap:/work -w /work \
  -e PYTHONPATH=/work/minseok:/work/minseok/apps \
  minseok97/redoceanmap-backend:latest \
  python -m pytest minseok/apps/chat/tests/eval/test_quality_gate.py \
    -q -p no:cacheprovider -s
```

프롬프트를 고쳤을 때: 러너 재실행 → `git diff trace.jsonl`로 품질 변화 확인 →
게이트 통과 시 trace·(개선이면) baseline 갱신 커밋.

## 한계 (정직 고지)

- 스냅샷의 팩트 통계는 합성이다 — phase2 서술의 **사실성**이 아니라
  **근거 준수**(컨텍스트 밖 숫자·입지 창작 금지)를 잰다.
- 답변의 유용함·문장 품질 같은 주관 축은 재지 않는다(LLM-judge 순환 회피 결정).
- 러너는 온도 등 샘플링 비고정 시 실행 간 변동이 있을 수 있다 — baseline 회귀
  허용폭(-3%p)이 이 변동을 흡수한다.
