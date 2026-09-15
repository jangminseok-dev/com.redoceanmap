# LLM 교체 판정 실측 — ③-M5② (2026-09-14, 백엔드 PC)

EXAONE 3.5 7.8B는 NC 라이선스(연구 전용)라 공개 서비스 전 교체가 필수다(ROADMAP E5·③-M5②).
상용 가능 후보를 골든셋 134문항 러너(`apps/chat/tests/eval/test_eval_runner.py`, `-m ollama`)로 돌려
`baseline.json`(EXAONE, 2026-09-08 박제)과 대조했다. 판정 규칙은 `test_quality_gate.py`와 같다
(회귀 -3%p, 환각·잘림 건수 비증가, 절대 규칙 위반 0).

## 환경

- RTX 3050 8GB · WSL2 RAM 12GB · Ollama 0.32.0(systemd, GPU) · 러너는 도커 이미지에서 `--network host`.
- 교체 스위치는 `LLM_MODEL` env 하나(코드 무수정). **`LLM_THINK` env를 이번에 추가**했다 —
  Gemma 4 계열은 Ollama 기본이 사고(thinking) 모드 켜짐이라 답변당 수십 초가 걸리고, Modelfile에는
  이를 끄는 파라미터가 없어 오케스트레이터의 chat 호출에 `think`를 넘기는 길밖에 없었다.
  비사고 모델(EXAONE)에 `think=False`를 넘겨도 Ollama는 오류 없이 무시한다(실측).
- 8GB VRAM에 KV 캐시(num_ctx 8192)까지 올릴 수 있는 크기만 후보로 삼았다.
  Gemma 4 12B(QAT 7.2GB)는 CPU로 넘쳐 제외(8/28 OOM 전례).

## 후보와 결과

| 지표 | EXAONE 기준 | Gemma4 e2b<br>사고 off | Gemma4 e4b QAT<br>사고 off | Gemma4 e2b<br>사고 on | Kanana 1.5 8B | Llama 3.1 8B |
| --- | --- | --- | --- | --- | --- | --- |
| 의도 정확도 | 0.993 | 0.970 | 0.978 | 0.978 | 0.948 ✗ | 0.955 ✗ |
| 종목 질의 정확도 | 1.000 | 1.000 | 0.938 ✗ | 1.000 | 0.969 ✗ | 0.969 ✗ |
| 지역 적중률 | 1.000 | 1.000 | 0.964 ✗ | 1.000 | 0.929 ✗ | 0.929 ✗ |
| 멀티턴 계승률 | 1.000 | 0.917 ✗ | 0.833 ✗ | 0.917 ✗ | 0.667 ✗ | 0.833 ✗ |
| 거래량 판정·유의 문장 | 1.0 / 1.0 | 1.0 / 1.0 | 1.0 / 1.0 | 1.0 / 1.0 | 1.0 / 1.0 | 1.0 / 1.0 |
| 출처 인용 커버리지 | 0.972 | 0.426 ✗ | 0.880 ✗ | 0.817 ✗ | 0.316 ✗ | 0.327 ✗ |
| 환각 숫자 | 0 | 0 | 0 | 0 | 0 | 2 ✗ |
| 답변 잘림 | 0 | 0 | 0 | 6 ✗ | 0 | 1 ✗ |
| 절대 규칙 위반 | 0 | 0 | 0 | 0 | 0 | 1 ✗ (입지 창작 "호선") |
| phase0 / phase2 / 주식 답변 p50 | 0.7 / 15.3 / 4.6초 | 0.9 / 6.6 / 2.1초 | 1.1 / 8.1 / 3.8초 | 6.2 / 19.9 / 13.3초 | 0.8 / 10.9 / 4.2초 | 0.8 / 8.9 / 3.9초 |
| 134문항 실행 시간 | 17분 | 11분 | 15분 | 56분 | 18분 | 17분 |

태그: `gemma4:e2b`(Q4_K_M) · `gemma4:e4b-it-qat` · `cookieshake/kanana-1.5-8b-instruct-2505:Q4_K_M`(커뮤니티
업로드 — 공식 태그 없음) · `llama3.1:8b`. Gemma4 e4b 사고 on은 14분에 12건이라 중단(완주 2.5시간 예상, 판정 가치 없음).

## 판정

**게이트를 그대로 통과하는 후보는 없다.** 다만 갈리는 축이 분명하다.

- **탈락(모델 자체 문제)**: Llama 3.1 8B — 컨텍스트에 없는 지하철 노선을 지어냈고(절대 규칙) 숫자 환각 2건.
  Kanana 1.5 8B — 환각·위반은 0이지만 지시 준수(인용 마커 0.32, 멀티턴 0.67, 지역 0.93)가 전반적으로 약하다.
- **후보 확정: Gemma 4 (사고 off)** — 환각 0·잘림 0·절대 규칙 위반 0이고 지연은 EXAONE의 절반 수준.
  남은 회귀는 전부 **EXAONE에 맞춰 튜닝된 프롬프트를 덜 따르는 것**이라 프롬프트 재튜닝(I-21) 영역이다.
  - e4b QAT: 인용 커버리지 0.88(주식·뉴스 답변 52/52건 마커 사용). 실패는 종목 질의 정규화 2건
    (SU04 "마이크로소프트"→`MS`, SF06 두 종목 질문→`TSLA/AAPL`), 멀티턴 후속 발화 2건(MT11·MT12)이
    general로 빠짐, MN12(점수 계산 방식 질문) general.
  - e2b: 더 빠르고 종목·지역은 완벽하지만 **주식 답변에서 마커를 절반만 씀**(34건 중 18건 — 뉴스 답변은
    18/18). 테마주 질문 2건(MW11 방산주·MW15 엔터주)을 stock으로 분류. MT12·MN12는 e4b와 동일.
- 사고 on은 품질이 조금 낫지만(e2b 인용 0.82) 답변당 수십 초라 운영 불가. `LLM_THINK=off` 고정.

**권고**: `LLM_MODEL=gemma4:e4b-it-qat` + `LLM_THINK=off`를 교체 대상으로 확정하고, 다음 순서로 간다.
1. 프롬프트 재튜닝(I-21과 묶음): ① phase0 의도 분류 — 멀티턴 후속 발화("~말고 ~이면", "엥 나는 ~")·
   서비스 질문(MN12)을 market으로, ② 종목 질의 정규화 — 한글 종목명→티커 표 강제·복수 종목 질문은 첫 종목,
   ③ 주식 답변 마커 규칙 강조(e2b 대비용). 가드는 결정론이라 그대로.
2. 러너 재실행 → 게이트 통과 확인 → `.env`에 두 키 설정 → baseline 재박제(모델 교체는 baseline 교체 사유).
3. 그 뒤 E5의 라이선스 표기(Gemma Terms → Gemma 4는 Apache 2.0, `ollama show` 실측) 문서 반영.

## 재현

```bash
docker run --rm --network host -v /home/host/projects/com.redoceanmap:/work -w /work \
  -e PYTHONPATH=/work/minseok:/work/minseok/apps -e PYTHONUNBUFFERED=1 \
  -e LLM_MODEL=gemma4:e4b-it-qat -e LLM_THINK=off \
  minseok97/redoceanmap-backend:latest \
  python -m pytest minseok/apps/chat/tests/eval/test_eval_runner.py -q -s -p no:cacheprovider -m ollama
# 채점: test_quality_gate.py(baseline 대조). 러너는 trace.jsonl을 덮어쓰므로 기준본은 git으로 복원한다.
```

trace·채점 원본은 세션 스크래치패드에만 남겼다(저장소 미포함 — 1.5MB×6).

## 2차 실측 — 프롬프트·가드 재튜닝 뒤 게이트 통과 (2026-09-15, 백엔드 PC)

같은 러너·같은 조건(`gemma4:e4b-it-qat` + `LLM_THINK=off`)으로 두 번 더 돌렸다(1회 16분 22초·16분 20초).

| 지표 | EXAONE 기준(9/8) | 1차(의도·종목 수정) | 2차(근거 번호·지목 가드 추가) |
| --- | --- | --- | --- |
| 의도 정확도 | 0.993 | **1.000** | **1.000** |
| 종목 추출 | 1.0 | 1.0 | 1.0 |
| 지역 적중 | 1.0 | 0.964 (MR03) | **1.0** |
| 인용 커버리지 | 0.972 | 0.871 | **0.976** |
| 환각·잘림·절대 위반 | 0·0·0 | 0·0·0 | 0·0·0 |
| p50 phase0/phase1/phase2/stock/news(ms) | — | 1086/4362/8901/3747/3740 | 1073/4355/8746/3521/3750 |

**1차에서 고친 것(9/14 판정 문서의 잔여 5건 전부 해소)**
- phase0 프롬프트: 서비스 자체(점수 계산 방식) 질문은 market · 이전 대화가 있으면 업종 변경/정정 후속은 이전 도메인 ·
  해외 종목은 프롬프트 안 표(12종)에 있는 것만 티커, 없으면 한국어 이름 · 복수 종목은 첫 종목 하나.
- 결정론: `_normalize_stock_queries`가 슬래시 결합("TSLA/AAPL")도 분리 · `_DOMAIN_FOLLOWUP_RE`에 `말고|추천`
  (직전 카드가 있을 때만 걸리는 승계 백스톱).

**1차에서 드러난 회귀 2건과 원인**
- 인용 커버리지 0.871: Gemma가 `[분석 데이터] — 근거 [1]` 블록의 **항목 순서를 근거 번호로 오해**해
  `[2][3][7]`처럼 썼다(주식 답변 52건 중 29건). `strip_dangling_citations`가 지우면서 수치 문장이 마커를 잃었다.
  → 컨텍스트 끝에 "쓸 수 있는 근거 번호: [1] [4]" 줄을 결정론으로 붙이고, 프롬프트에 "블록 항목은 전부 [1]"을 명시.
- 지역 적중 MR03("강남역 근처 샐러드"): 자치구 어간 "강남"으로 ★가 30곳에 찍혀 모델이 학동사거리·압구정로데오·논현역을
  골랐다. → 상권명을 그대로 지목한 질문은 그 상권(매출 상위 1곳)을 반드시 포함하는 가드(`_named_codes`)를 반경 가드 뒤에 추가.

**확정 조치**
- `.env`: `LLM_MODEL=gemma4:e4b-it-qat` · `LLM_THINK=off`. 코드 기본값(`core/config.py`·오케스트레이터·
  `check_llm_health.py`)도 같은 값으로 바꿨다 — `.env`가 비어도 NC 모델로 조용히 되돌아가지 않게.
- baseline.json 재박제(위 2차 값). trace.jsonl은 2차 실행본.
- 골든셋 러너의 `register("exaone-7.8b", …)`는 기본값이 아니라 무해.

## 후속 — 뉴스 라벨링·상주 시간 (2026-09-15 오후)

- **뉴스 라벨링 cron도 Gemma로**: NC 라이선스는 출력물(라벨)까지 걸리므로 EXAONE 라벨 10.5만 건을 전량 재라벨한다.
  판단 근거 — Gemma 80건 표본: 파싱 실패 0, EXAONE 라벨과 감성 부호 일치 62/80, 정반대 3(셋 다 Gemma가 맞음:
  "공급제약 전례 없는 수준"을 EXAONE이 규제·소송 −0.5로 봤다), 이벤트 일치 60/80, 1건 1.08초.
  - `scripts/label_news.py`: 모델·사고 모드를 `LLM_MODEL`·`LLM_THINK`로, labeler 태그는 `core/llm/labeler.py`의
    `labeler_tag()`(읽는 쪽 `stock news_pg_repository.DEFAULT_LABELER`와 같은 함수) → `gemma4-e4b-it-qat`.
  - 미라벨 조회(`news_label_pg_repository.unlabeled`)를 **최신 기사 우선**으로 바꿨다 — 전량 미라벨 상태에서
    소비처(RAG·피드·알림)가 먼저 보는 최근 기사를 먼저 채운다. 1건 1.08초 → 10.5만 건 ≈ 32시간, 밤 cron
    (02:30, `--limit 25000`) 4~5일. 첫날은 배포 직후 최신 6,000건을 즉시 배치로 채워 낮 동안의 공백을 줄였다.
  - 재라벨 완료 뒤 `labeler='exaone-7.8b'` 행 삭제(라이선스 정리)는 별도 실행 — 완료 확인:
    `select labeler, count(*) from news_labels group by 1`.
- **모델 상주**: Ollama 기본 keep_alive 5분이라 유휴 뒤 첫 질문에 10~20초 콜드 로드. 백엔드 PC는 sudo 없이
  systemd 오버라이드를 못 바꾸므로 오케스트레이터가 요청마다 `keep_alive`(`LLM_KEEP_ALIVE`, 기본 24h)를 넘긴다
  — 채팅·임베딩(bge-m3) 둘 다. Gemma 2.9GiB + bge-m3 1.1GiB 상주는 8GB VRAM 안.
- 라이선스: `ollama show gemma4:e4b-it-qat`는 Apache 2.0(9/14 실측) — E5 표기 갱신은 이 문서와 ROADMAP ③-M5②에 반영.
