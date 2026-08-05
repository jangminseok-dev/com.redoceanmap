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
| inherit_rate / inherit_focus_rate | 멀티턴 승계율(직전 추천과 교집합) / 집중률(부분집합 — "그 중에서"에 그것만으로 답함). 부분집합 단일 기준은 "이어받고 이웃 추가" 케이스를 실패로 세어 첫 실측이 0%로 나왔다(실제 승계율 0.5) — 2026-08-05 이원화 | 회귀(-3%p) |
| hallucinated_number | 답변 숫자가 주입 컨텍스트·질문에 없음 | 회귀(건수 비증가) |
| forbidden_phrase / missing_disclaimer / location_claim | 매매지시·확률단정 / 책임 고지 / 입지 창작(호선·환승·관문) 정규식 | **절대 0건 / 100%** |
| latency p50·p95 | phase별 프록시 타이밍 | 관측 |

환각 숫자는 휴리스틱(파생 수치·어림 표현은 오탐 가능)이라 절대 0이 아니라
**건수 비증가** 회귀로 건다. 위반 목록이 리포트에 남으므로 수동 검토로 확정한다.

> **숫자 비교는 형식을 정규화한다**(2026-08-05). 콤마와 무의미한 소수 0을 지운 뒤 대조한다 —
> 컨텍스트의 `48,400.00`과 답변의 `48,400`을 다른 숫자로 세던 시절엔 환각 의심 63건 중
> **56건(89%)이 이 형식 차이**였다. 지표가 아니라 잡음을 세고 있었다. **반올림 인용도
> 근거로 인정한다**(같은 날 후속) — 소수 원값(`182.36`)이 컨텍스트에 있으면 정수 반올림형
> (`182`)은 창작이 아니다. 이 두 정규화 뒤 남는 것(기사 연도·점수 형식 창작, 단위 환산
> 액수)이 진짜 검토 대상이다.
>
> **종목 질의 허용 목록은 프로덕션 능력 기준이다**(2026-08-05). 미국 종목의 한국어 이름
> ("테슬라")은 `symbol_resolver` 별칭 사전이 티커로 해석하므로 추출이 이름 그대로여도
> 다운스트림이 성공한다 — 티커만 허용하던 시절의 미스 5건은 전부 이 유형이었다
> (0.767~0.833 → 재채점 1.000).

## baseline은 최고 기록이 아니라 바닥이다

회귀 게이트의 기준선은 **잡음이 넘지 않는 값**이어야 한다. 최고 기록으로 박으면 다음 실행이
평소 수준만 나와도 빨개지고, 그러면 기본 스위트(`pytest minseok/apps`)가 흔들린다.

실측 분포 예(2026-08-05, 4회): `stock_query_accuracy`가 0.767~0.833을 오간다. 폭이 6.6%p로
회귀 허용치 `-3%p`보다 넓다 — 그래서 baseline에는 **관측 최소값**을 넣는다. 같은 이유로
`truncation_count`는 관측된 발생률(4회 중 1회)을 반영해 1로 둔다. 0으로 두면 확률적 결함
하나에 게이트가 막혀, 절대 규칙에서 분리한 취지가 무효가 된다.

실행 표본이 쌓여 변동 폭이 좁아지면 그때 올린다.

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
