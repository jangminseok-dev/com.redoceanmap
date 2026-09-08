# 게임 폐기 · 입지 적합도 이관 · AI 모의투자(사람 vs EXAONE) 계획

> 2026-09-07 수립. 사용자 결정(같은 날 확정):
> ① game 스포크(모의투자 게임·상권 창업 시뮬)를 지운다. ② 입지 적합도 진단만 market(상권분석)에
> 남긴다. ③ 그 자리에 **실 티커 모의투자**를 stock 앱 슬라이스로 만든다 — **EXAONE이 직접 매매를
> 판단**하고, **사람도 같은 규칙으로 참가해 AI와 성적을 겨루며**, **숏을 처음부터 포함**하고,
> 자산 곡선은 **2026-07-30부터 리플레이**한다.
> 이 문서는 "무엇을 어떤 순서로, 어떤 검증으로 끝내는가"의 정본이다.
> 관련: [[ROADMAP]] · [[minseok/apps/stock/_docs/CLAUDE|stock CLAUDE]] ·
> [[minseok/apps/market/_docs/CLAUDE|market CLAUDE]] · [[minseok/apps/game/_docs/game-harness|game-harness]](폐기 대상)

## 0. 내가 이해한 목표

- "게임" 탭이 사라지고 "AI 모의투자" 탭이 생긴다. 가상 주가·가상 회사·레버리지·창업 시뮬·토론방은 없앤다.
- 종목은 워치리스트 실 티커, 시세는 이미 수집하는 봉이다. 새 벤더 호출·새 cron은 만들지 않는다.
- "지금까지 학습한 데이터"는 stock 앱이 두 달간 쌓은 것 — 뉴스 9만 건·EXAONE 라벨 9만 건·예측
  스냅샷·사후 채점·재적합 이력. EXAONE은 **이 축적물을 매일 읽고** 종목·방향·비중을 고른다.
- "프로젝트를 시각화"란 이 파이프라인이 살아 움직이는 것을 한 화면에서 보이는 것이다. 자산 곡선만이
  아니라 **매 거래마다 EXAONE이 무엇을 보고 왜 그렇게 판단했는지**가 따라붙어야 한다.
- 사람은 관전자가 아니라 참가자다. 같은 종목·같은 규칙으로 매매하고 리더보드에서 AI와 겨룬다.

## 0-1. 결정 근거 (2026-09-07 실측)

| 항목 | 값 |
| --- | --- |
| game 지갑 사용자 | 3명 / 전체 14명 (포지션 15건·2명, 가게 3개, 토론 글 0, 지정가 0) |
| game 마지막 커밋 | 2026-08-04 |
| game 코드 | 파이썬 16,467줄 · 테스트 파일 29개 · 테이블 11개 · 프론트 3,779줄 · 설계 문서 1,628줄 |
| 원료 | `forecast_snapshots` 81종목 × 2026-07-20~ · `price_bars` 1d 83종목(시가 결측 0) · 5m 81종목(한국 2 포함) · `news_articles` 91,646건(7/30 이후 59,345) · `news_labels` 90,728건 |
| EXAONE 처리 속도 | 라벨링 2,288건/34분(짧은 프롬프트). 일일 판단 1회(프롬프트 ~3k 토큰)는 수십 초 예상 |

## 아키텍처 원칙 (변경 없음 — 명문화)

- **헥사고날/클린 + DDD/SOLID + 스타 토폴로지(허브-스포크)** 유지. 세 단계 모두 import-linter 5계약을
  통과한 상태로 커밋한다. 스포크 상호 import 0건.
- **새 슬라이스는 라우터 컨벤션(자기소개 + 프랙탈 단면)**을 따른다.
- **LLM 추론은 `core/llm/llm_orchestrator.py` 단일 수렴(단일 모델 정책)**. EXAONE 매매 판단은
  `DecisionPolicyPort`의 어댑터 하나(`ExaoneDecisionAdapter`)가 오케스트레이터 `format="json"`으로
  호출한다. 스크립트가 Ollama를 직접 부르지 않는다.
- **판단 주체는 포트 뒤에 있다.** `DecisionPolicyPort` 구현이 둘 — EXAONE, 그리고 검증된 지표 규칙.
  원장 엔진은 누가 결정했는지 모른다. 사람의 주문도 같은 엔진을 탄다.
- **정직성 원칙(stock 확률 노출 정책 준용)**: EXAONE 판단은 백테스트로 검증된 적이 없다. 화면은 항상
  **EXAONE · 지표 규칙 · SPY 보유 · 사람**을 나란히 놓고, EXAONE 계정에 "검증되지 않은 판단" 배지를
  단다. "실제 매매 아님 · 지연 시세 · 가정치" 고지 상시 표시. **화면·chat 어디서도 권유 문형을 쓰지 않는다**(4-3 — 신고 없음).
- **가정치 표기**: 수수료·환율·최대 종목 수 등 규칙값은 `assumed_*`(game에서 유일하게 가져오는 규칙).
- **공유 DB 불가침**: 새 테이블은 stock 소유로 공유 DB(:5432). market DB(:5434)는 1단계에서 읽기만.

## 기기 배정

세 단계가 순차 의존이고 EXAONE(Ollama)이 이 PC에 있어 **전부 window 세션이 맡는다.** mac 세션은
이 기간 `apps/game`·`apps/market`의 fitness·`apps/stock`의 paper 슬라이스·`www/components/game`을
건드리지 않는다. 각 단계 커밋 직후 세 브랜치 push, mac은 시작 전 fetch.

---

## 1단계 — 입지 적합도를 market으로 이관

**목표**: `GET /market/trdar/{code}/fitness?service_code=`가 game 없이 같은 4축·진단 문장을 낸다.

| 대상 | 처리 |
| --- | --- |
| `game/domain/commerce/fitness.py` (4축 판정, 순수) | → `market/domain/services/area_fitness.py`. 게임 매출 계수 `fitness`(0.4~1.6)는 제거, `total_score`·`components`만 |
| `game/domain/commerce/diagnosis.py` (진단 문장, LLM 미사용) | → `market/domain/services/area_fitness_narrator.py` |
| 허브 `AreaDemandProfilePort` + DTO + provider | 허브에서 제거(game이 유일 소비자). market 내부 아웃바운드 포트로 내리고 DTO는 `market/app/dtos/` |
| `market/adapter/outbound/gateways/area_demand_profile_gateway.py` | → `market/adapter/outbound/pg/area_demand_profile_pg_repository.py`. 쿼리 무변경 |
| `openable`·`minimum_capital`·`viable_capital` | 버린다(game 경제 계수 위의 가정치). 창업비용은 ROADMAP B4 실데이터 후 market 팩트로 재구성 |
| 분기 고정(`DATA_QUARTER = 20254`) | 최신 적재 분기 자동 선택(area_stats 규칙) |
| 응답 | `total_score` · `components[4]` · `diagnoses[]` · `observed_sales_per_store` · `observed_ticket_price` · `year_quarter` |

```
market/adapter/inbound/api/schemas/area_fitness_schema.py
market/adapter/inbound/api/v1/area_fitness_router.py
market/app/dtos/area_fitness_dto.py · area_demand_profile_dto.py
market/app/ports/input/area_fitness_use_case.py
market/app/ports/output/area_demand_profile_port.py
market/app/use_cases/area_fitness_interactor.py
market/adapter/outbound/pg/area_demand_profile_pg_repository.py
market/dependencies/area_fitness_provider.py
market/tests/domain/test_area_fitness.py · test_area_fitness_narrator.py      # game 테스트 이동
market/tests/app/use_cases/test_area_fitness_interactor.py                    # 스텁 포트
```

프론트: `components/game/StoreFitnessCard.tsx` → `components/market/AreaFitnessCard.tsx`(상권 오버레이,
`AreaScoreCard` 옆, 업종은 area_stats의 `service_code` 공유). `fetchAreaFitness` · 타입 `AreaFitness`.
game 쪽은 이 단계에서 손대지 않는다(허브 포트만 game 로컬 복사본으로 옮겨 lint 통과, 2단계에서 통째로 삭제).

| 검증 | 확인 |
| --- | --- |
| 도메인 | 옮긴 테스트 2개 market 아래에서 통과 |
| 인터랙터 | 스텁 포트 — 자료 없음 → 앱 예외(라우터 404), 정상 → 4축 가중치 합 1.0 |
| 구조 | `lint-imports` 통과 |
| 실 응답 | 같은 분기 지정 시 `/game/areas/{code}/fitness`와 4축 점수 동일 |
| 프론트 | `pnpm run typecheck` · 오버레이 카드 렌더 |

커밋: `feat(market): 입지 적합도 슬라이스 — game에서 이관(4축·진단 문장, 창업비용 제외)`

---

## 2단계 — game 스포크 삭제

**선행**: `git tag game-archive` → 세 브랜치와 태그 push.

| 영역 | 대상 |
| --- | --- |
| 백엔드 | `minseok/apps/game/` 전체 |
| main.py | game 라우터 import·include·`dependency_overrides[get_game_ops_port]` (`124~136` · `313` · `350`) |
| 허브 | `game_ops_port.py` · `game_ops_dto.py` · `dependencies/game_ops_provider.py` |
| admin | `game_ops_{router,schema,dto,use_case,interactor,provider}` + 테스트. 권한 문자열 `game:read/write`는 라우터에만 있어 레지스트리 수정 없음 |
| import-linter | `.importlinter` game 7줄(root_packages·containers·independence·framework 2·purity·hub-isolation) |
| 스크립트 | `calibrate_game_symbols.py` · `check_game_determinism.py` · `simulate_game_balance.py` |
| DB | 리비전 `drop_game_tables`(down_revision `n3a4b5c6d7e8`): 테이블 11개 FK 순서로 drop. 기존 game 리비전 8개는 체인 무결성 때문에 남긴다. downgrade 복구 불가 명시(복원은 04:00 백업) |
| 프론트 | `app/(seoul)/game/` · `app/admin/game/` · `components/game/` · `lib/useFavorites.ts` · `lib/api.ts` game 함수 17개 · `lib/types.ts` Game* · `AppShell` "게임" · `AdminShell` "게임 운영" · `admin/members` 권한 라벨·링크 |
| 문서 | `minseok/_docs/CLAUDE.md` 앱 표 · `ROADMAP.md:112` "폐기(2026-09)" · `README.md:36` · `recommendation/_docs/CLAUDE.md:32` · `www/_docs/CLAUDE.md:126` 탭 3→2 · `www/_docs/DESIGN.md` 게임 언급 4곳 |

건지는 것: `trading_rules.py`의 수수료 0.1%·숏 개념은 3단계 `paper_rules.py`에 새로 쓴다(레버리지·강제청산·만료는 버린다).

| 검증 | 확인 |
| --- | --- |
| 정적 | `grep -rn game minseok/apps minseok/main.py www/app www/components www/lib` → 0건 |
| 구조 | `lint-imports` · pytest 전체(`-m "not ollama and not network"`) |
| 프론트 | `pnpm run typecheck` |
| DB | 도커 `alembic upgrade head` → `\dt game_*` 0개 |
| 배포 | `infra/deploy.sh` → 파드 로그에 리비전 적용 · `/health` 200 · `/game/myself` 404 · Vercel 내비에 "게임" 없음 |

커밋: `chore(game): game 스포크 폐기 — 모의투자·창업 시뮬 삭제, 테이블 11개 drop(태그 game-archive)`

---

## 3단계 — AI 모의투자 (stock `paper` 슬라이스): 사람 vs EXAONE vs 지표 규칙

### 3-1. 참가자와 규칙

| 항목 | 값 | 비고 |
| --- | --- | --- |
| 참가 계정 종류 | `exaone`(AI 1개) · `signal`(검증 지표 규칙 1개) · `user`(사람, user_id당 1개) | 전부 같은 원장 엔진. `signal`은 EXAONE의 정직한 대조군(내 추가 — 뺄 수 있다) |
| 종목 우주 | 워치리스트(price_bars 보유 종목) | 리플레이 구간은 당시 워치리스트가 아니라 **당시 스냅샷이 존재한 종목** |
| 방향 | 롱 · 숏(레버리지 없음, 숏은 명목가 100% 현금 예치) | 사용자 결정: 숏 처음부터 |
| 초기 자본 | `assumed_initial_cash_krw = 100,000,000` | 미국 종목은 USD 봉 × `assumed_usdkrw`(고정 상수, 화면 고지) |
| 수수료 | `assumed_fee_rate = 0.001` 체결당 | game 값 승계 |
| 한도 | 종목당 비중 ≤ 20% · 동시 보유 ≤ 10종목 | AI·사람 공통. 엔진이 거부하고 사유를 남긴다 |
| AI 체결 | 판단(14:00) 다음 세션 **1d 시가**(D+1 배치에서 체결) | 스냅샷 채점과 같은 축 — 선견 없음 |
| 사람 체결 | 주문 시점 **최신 5m 봉 종가**(지연 시세) | 즉시 체결. AI와 체결 축이 다름을 규칙 고지에 적는다 |
| 평가 | 매일 14:00 배치가 최신 1d 종가로 전 계정 `equity` 기록 | 리더보드는 이 값. 화면의 실시간 평가는 quote 슬라이스 |
| 기준선 | SPY 매수보유(계정 시작일 기준, 저장 안 함·즉석 계산) | INDEX_TICKERS로 이미 1d 수집 |
| 리플레이 | 2026-07-30 ~ 배포 전날. `exaone`·`signal` 계정만, 행에 `replayed=true` | 사용자 결정. 사람 계정은 가입 시점부터 |

### 3-2. EXAONE 판단 — 하루 1회, JSON 강제

- 입력(전부 **as_of 이전 데이터만**, `decision_context.py`가 순수 함수로 조립):
  보유 포지션(미실현 손익) · 후보 ≤ 25종목(스냅샷 비중립 또는 3일 내 뉴스 라벨 보유):
  최근 종가·5일 수익률·스냅샷 방향/score/up_rate/ready·3일 감성 평균·이벤트 유형·헤드라인 2개·
  레짐·어닝 veto · 현재 현금·한도 규칙.
- 출력: `{"market_view": str, "orders": [{"ticker","action": "BUY|SELL|SHORT|COVER","weight": 0~0.2,"reason": str,"cites": {"news_ids": [int], "signals": [str]}}]}`
  — 프롬프트가 후보마다 `news_id`와 신호 키를 붙여 주고, EXAONE은 **그 id만 인용**한다. 파서가 존재하지 않는 id를 걸러낸다(환각 인용 차단, chat의 인용 배지와 같은 규칙).
  — `decision_parser.py`(순수)가 검증, 위반 주문은 `rejected[]`로 남기고 나머지 실행.
- 실패 처리: 파싱 실패 1회 재시도, 재실패면 그날 무거래 + 실패 기록. Ollama 불통이면 무거래 기록.
- 기록: `paper_decisions`에 프롬프트·원문 응답·파싱 결과·거부 목록·지연(ms). **이 행이 "왜 샀는가" 화면의 원천**이다.
- 재현성: 오케스트레이터에 `options` 인자(temperature 0) 한 줄 추가(core 변경 1건). 리플레이는 1회 실행 후
  동결 — 다시 계산하지 않는다.
- 리플레이 정직성: 프롬프트 조립 쿼리가 `published_at ≤ as_of`·`snapshot.as_of = as_of`·`bar.ts ≤ as_of`만
  본다(테스트로 고정). 라벨은 기사 내용만의 함수라 생성 시각이 늦어도 미래 정보가 아니다. EXAONE 가중치는
  우리 데이터로 학습되지 않았다.
- 비용: 리플레이 ~28회 + 매일 1회. 라벨링 실측(0.9초/건, 짧은 프롬프트) 기준 수십 초/회.

### 3-3. 데이터 (공유 DB, stock 소유 — 리비전 1개)

| 테이블 | 열 | 유니크 |
| --- | --- | --- |
| `paper_accounts` | id · kind(`exaone`/`signal`/`user`) · user_id(nullable) · initial_cash_krw · started_on · rules_version | (kind, user_id) |
| `paper_positions` | account_id · ticker · side · quantity · avg_price · opened_at | (account_id, ticker, side) |
| `paper_trades` | account_id · ticker · side · action · quantity · price · fee_krw · realized_pnl_krw · ts · decision_id(nullable) · **reason · evidence(JSONB: 인용 news_id[] · snapshot_id · 신호 분해)** · replayed | — |
| `paper_decisions` | account_id · as_of · model · prompt · response_raw · market_view · orders(JSONB) · rejected(JSONB) · **candidates(JSONB: 그날 후보 25종목 요약 — 되감기 화면 원천)** · latency_ms · replayed | (account_id, as_of) — 재실행 멱등 |
| `paper_decision_scores` | decision_id · ticker · action · **reason_kind**(`news`/`indicator`/`regime`/`mixed` — 파서가 evidence로 분류) · realized_return_pct(5거래일) · hit · evaluated_at | (decision_id, ticker) — 스냅샷 채점과 같은 적중 정의(`hit_unit`/`is_up_hit`, 숏은 부호 반전) |
| `paper_equity_daily` | account_id · as_of · cash_krw · positions_value_krw · equity_krw · replayed | (account_id, as_of) |

### 3-4. 파일 (프랙탈 단면)

```
core/llm/llm_orchestrator.py                          # orchestrate(options=…) 1줄
stock/domain/services/paper_rules.py                  # assumed_* 상수 · 한도 · 수수료 (순수)
stock/domain/services/paper_ledger.py                 # 체결·청산·숏 예치·일일 평가 (순수, 봉 입력)
stock/domain/services/decision_context.py             # as_of 컨텍스트 조립 → 프롬프트 텍스트 (순수)
stock/domain/services/decision_parser.py              # JSON 검증·한도 위반 분리 (순수)
stock/domain/services/signal_rule_policy.py           # 지표 규칙 판단(UP 롱·DOWN 숏·5일 청산) (순수)
stock/domain/services/decision_scorer.py              # 판단 사후 채점 — 이유 유형별 적중률 집계 (순수, hit 정의는 backtest_report 재사용)
stock/app/dtos/paper_dto.py
stock/app/ports/input/paper_use_case.py               # step(as_of) · board() · account(key) · place_order(user)
stock/app/ports/output/paper_account_repository.py    # 계정·포지션·원장·평가 (한 트랜잭션)
stock/app/ports/output/decision_policy_port.py        # decide(context) → Decision
stock/app/use_cases/paper_interactor.py               # 대장 — 기존 스냅샷·뉴스·봉 리포지토리 재사용
stock/adapter/outbound/exaone_decision_adapter.py     # DecisionPolicyPort — 오케스트레이터 format=json
stock/adapter/outbound/orm/paper_{account,position,trade,decision,equity_daily}_orm.py
stock/adapter/outbound/pg/paper_account_pg_repository.py
stock/adapter/outbound/gateways/paper_trading_gateway.py   # 허브 PaperTradingPort 구현(step)
stock/adapter/outbound/gateways/paper_decision_gateway.py  # 허브 PaperDecisionPort 구현 — chat 소비
stock/adapter/inbound/api/{schemas,v1}/paper_{schema,router}.py
stock/dependencies/paper_provider.py
hub/app/ports/output/paper_trading_port.py + dto + provider    # POST /automation/paper/step?as_of=
hub/app/ports/output/paper_decision_port.py + dto + provider   # chat용: 최근 N일 판단·거래·근거·채점 요약
chat/…                                                  # 종목 질문 보강 + "오늘 뭐 샀어/왜 팔았어" 의도 → PaperDecisionPort 소비(프롬프트 한 단락)
scripts/snapshot_forecasts.py                          # 캡처·채점 뒤 step 호출 1줄 (cron 신설 없음)
scripts/replay_paper.py                                # 1회성 — 7/30부터 날짜 순회로 step 호출
```

엔드포인트: `GET /stock/paper/myself` · `GET /stock/paper/board`(리더보드 + SPY) ·
`GET /stock/paper/accounts/{key}`(곡선·포지션·거래, exaone은 판단 근거 포함) ·
`GET /stock/paper/accounts/exaone/decisions?from=&to=`(일별 판단 + 후보 요약 + 인용 기사·라벨 조인 — 되감기 원천) ·
`GET /stock/paper/accounts/exaone/scorecard`(이유 유형별·방향별 적중률, n·Wilson 구간·기준선) ·
`GET /stock/paper/me` · `POST /stock/paper/me/orders`(`get_current_user_id`, 계정 없으면 자동 생성).

### 3-5. 프론트

`app/(seoul)/paper/page.tsx` + `components/paper/`:
`Leaderboard`(EXAONE·지표·SPY·나·다른 사람) · `EquityCurve`(recharts, 리플레이 구간 음영, **거래 마커** — 매수·매도·숏·커버 점, 클릭 시 해당 판단으로 이동) ·
`DecisionFeed`(EXAONE 일별 판단 — 시장 관점·주문·이유·거부 사유. **이유 옆에 인용 기사 제목이 링크로 붙고 펼치면 라벨(감성·이벤트 유형)과 신호 분해가 보인다**) ·
`Scorecard`(판단 사후 채점 — 이유 유형별 적중률, 표본·신뢰구간·기준선 병기. 채점 전에는 "검증되지 않은 판단" 배지, 표본 ≥30부터 숫자) ·
`TimeScrubber`(**되감기 슬라이더** — 날짜를 고르면 그날의 시장 관점·후보 25종목·판단·체결이 곡선 마커와 함께 바뀐다. 리플레이 구간 포함, 순수 프론트) ·
`PositionTable` · `TradeLog` ·
`OrderForm`(단일 객체 패턴, BUY/SELL/SHORT/COVER + 수량, 지연 시세 표시) · `RulesNotice`(고정 고지).
`AppShell` 내비 "AI 모의투자"(`/paper`). 리더보드·곡선은 일 1회 데이터라 폴링 없음, 내 평가액만 quote 30초.

### 3-6. 배치 순서 (14:00, 기존 cron 한 줄 안)

1. (기존) 스냅샷 채점 → 캡처
2. step(as_of=오늘): 전 계정 대기 주문을 어제 세션 시가로 체결 → 지표 규칙 계정 청산 판정 →
   전 계정 평가 기록 → **5거래일 도래한 EXAONE 판단 채점**(`paper_decision_scores`) →
   EXAONE 판단 호출·기록 → 지표 규칙 판단 → 두 계정 대기 주문 생성

### 3-7. 검증

| 단계 | 확인 |
| --- | --- |
| 도메인 | `paper_ledger`: 롱/숏 체결·청산 손익·예치금·수수료·한도 거부·같은 입력 재실행 동일. `decision_parser`: 잘못된 JSON·한도 초과·미보유 SELL 거부. `decision_context`: as_of 이후 행 0건 |
| 인터랙터 | 스텁 리포지토리·스텁 정책 — step 멱등(같은 as_of 2회 → 판단·체결 1회), 사람 주문 현금 부족 거부 |
| EXAONE 실호출 | `@pytest.mark.ollama` 1건 — 실제 컨텍스트로 JSON 파싱 성공, 인용 news_id가 프롬프트에 준 집합의 부분집합 |
| 채점 | `decision_scorer`: 롱/숏 부호 반전·NEUTRAL 없음·이유 유형 집계·스냅샷 채점과 같은 hit 정의(같은 입력 → 같은 hit) |
| chat 연동 | chat 스텁 테스트 — "오늘 뭐 샀어" 의도가 PaperDecisionPort를 부르고 답에 인용 배지가 붙는다 |
| 되감기 | 리플레이 구간 임의 날짜 선택 → 그날 `candidates`·`orders`·곡선 마커 일치(수기 1일 대조) |
| 리플레이 | 7/30~어제 재생 → `paper_equity_daily` 행수 = 거래일 × 2계정, `paper_decisions` = 거래일 수, 수기 검산 1일치 일치 |
| 구조·타입 | `lint-imports` · pytest · `pnpm run typecheck` |
| 운영 | 배포 다음 날 14:00 로그에 step 1줄 · `/stock/paper/board` 200 · 화면에 오늘 판단 추가 · 사람 계정 주문 1건 체결 |

커밋: `feat(stock): AI 모의투자 — EXAONE 일일 판단·지표 규칙 대조군·사람 참가 원장·리더보드`

---

## 3-8. 풍성함 추가 4건 (2026-09-07 사용자 확정 — 위 3단계에 녹였다)

| # | 항목 | 어디에 | 새 저장 |
| --- | --- | --- | --- |
| 1 | 근거 링크 | EXAONE 출력 `cites` + `paper_trades.evidence` + `DecisionFeed` | 열 2개 |
| 2 | 판단 사후 채점 | `decision_scorer.py` + `paper_decision_scores` + `Scorecard` + 배치 한 스텝 | 테이블 1개 |
| 3 | 거래 마커·되감기 | `paper_decisions.candidates` + `EquityCurve` 마커 + `TimeScrubber` | 열 1개 |
| 4 | chat 연동 | 허브 `PaperDecisionPort` + stock 게이트웨이 + chat 의도 1개 | 없음 |

출시 뒤 후보(이 계획에 없음): 페르소나 2개 · 알림(n8n 신호 알림 재사용) · 월간 회고 · 한국 대형주 10~20 확장(7/21 결정 번복이라 별도 결정).

## 실행 결과 (2026-09-08, window)

| 단계 | 커밋 | 검증 |
| --- | --- | --- |
| 1 입지 적합도 이관 | 337c0e1 | pytest 1331 · lint 5 kept · tsc · 실 DB 같은 분기 4축·진단 game과 일치 |
| 2 game 삭제 | 46bd4d2 (태그 `game-archive`) | pytest 1007 · lint · tsc · 배포 후 game_* 0개 · `/game/myself` 404 |
| 3 paper 백엔드 | 35b6f2e | pytest 1045(도메인 30·인터랙터 8 신규) · lint · main import 8 라우트 · alembic p5c6d7e8f9a0 |
| 3 paper 프론트 | de8c28d | tsc · `next build` |
| 배포·리플레이 | de8c28d 라이브 | paper 테이블 6개 생성 · 7/30 첫 step 45초(EXAONE 매수 4·지표 9, 거부 0) · 7/31~9/7 리플레이 `~/replay_paper.log` |

리플레이 결과(7/30~9/4, 거래일 30일, HTTP 실패 0):

| 계정 | 판단 | 주문 | 거부 | 체결(진입/청산) | 채점 n(적중) | 자산 1억 → |
| --- | --- | --- | --- | --- | --- | --- |
| EXAONE | 30(파싱 실패 1) | 57 | 74 | 13 / 4 | 롱 9(4) · 숏 3(1) | **0.94억** |
| 지표 규칙 | 30 | 76 | 10 | 38 / 28 | 롱 28(11) | **1.07억** |

- EXAONE 거부 사유 상위: 현금·비중 한도로 0주(38) · 알 수 없는 주문 유형(21, HOLD류) · 반대 포지션 보유(9) · 미보유 매도(5). 전부 파서·원장이 의도대로 막은 것이고 화면에 사유가 그대로 보인다.
- 평균 응답 18초(첫 호출 45초). 하루 1회라 14:00 cron 안에서 문제없다.
- 첫 6주 성적은 지표 규칙 > EXAONE. 화면의 "검증되지 않은 판단" 배지가 하는 말 그대로다 — 표본 30 미만이라 적중률 숫자는 아직 비노출.

계획과 달라진 점:
- 대기 주문 테이블을 따로 두지 않고 `paper_decisions.filled_at`과 `paper_trades.decision_id`로 미체결을 유도한다. 체결 봉이 7일 안에 없으면 폐기.
- `paper_decision_scores`의 이유 유형은 `news / indicator / mixed / none`(regime 축은 인용 키에 없어 뺐다).
- 4-①(근거 링크)을 위해 인용에 기사 url을 실었다. 4-④ chat 연동은 허브 `PaperDecisionPort`·stock 게이트웨이까지 만들었고, chat 의도 추가는 C3(window, mac C0~C2 뒤)로 미룬다 — chat_interactor를 두 세션이 동시에 만지지 않기 위해서다.
- **사람 참가는 같은 날 저녁 사용자 결정으로 제거했다**(9b45285 화면 단순화 뒤 → 열람 전용). 이유: 체결 축이
  달라(사람 즉시·AI 다음 세션 시가) 비교가 공정하지 않고, 사용자 14명이라 "나" 타일이 비어 보였다. 의미 있는
  비교(EXAONE · 지표 규칙 · SPY 보유)는 남는다. `paper_accounts.user_id` 열은 비어 있는 채로 둔다(행 0).
- 화면은 게임 순서로 재배치했다: 점수판 3타일 → AI가 한 일(샀어요/팔았어요 카드) → AI 지갑(손익률 카드) →
  자세히 보기(곡선·판단 원문 되감기·채점·지표 규칙 계정).

## 미결 (기본값으로 진행, 사용자가 뒤집을 수 있다)

1. `signal` 대조군 계정은 내가 추가했다. 빼도 엔진은 같다.
2. 환율은 고정 상수. 환율 수집 cron을 새로 만들지 않는다.
3. 사람 주문은 시장가 즉시 체결만(지정가 없음).
4. 사람 계정도 숏 가능. 레버리지는 없다.

---

# 4장 — chat 명쾌함 개선 (2026-09-07 조사 → 개선안)

> 사용자 불만: "상권이든 주식이든 명쾌한 답이 없다. '지표를 알 수 없다'가 나온다. '이 금액이면 어디',
> '네 상황이면 여기', '너와 비슷한 사람들은 이걸 샀다' 같은 대화가 없다."
> 조사 근거는 `apps/chat/app/use_cases/chat_interactor.py` · `domain/services/{verdict,answer_guard}.py` ·
> `_docs/SIGNAL_OVERHAUL_2026-08.md` · `SERVICE_QUALITY_2026-08.md` · `tests/eval/golden_set.jsonl`.

## 4-0. 원인 (확인된 사실 5개)

| # | 원인 | 근거 |
| --- | --- | --- |
| 1 | **"데이터 없음" 문자열 12종이 컨텍스트에 그대로 실려 답변 본문이 된다.** 결측 상권을 고르면 phase2가 인용할 값이 그 문자열뿐이고 프롬프트는 "제공된 수치를 인용"하라고 한다 | `chat_interactor.py:819-919` `_format_stats`, `:243` |
| 2 | **상권에 비용 축이 없어 "이 금액이면 어디"가 원리적으로 불가.** 랭킹 DTO에 임대료·창업비용 없음, 조건 라우팅 축은 폐업률·유동인구·매출 3개뿐, 프로파일 예산은 "이 예산으로 가능하다고 단정하지 말 것"과 함께 주입. 골든셋 MN02("1억으로 치킨집")는 intent만 채점 | `commercial_data_dto.py:106-121`, `chat_interactor.py:542-546`, `:1415`, `golden_set.jsonl:22` |
| 3 | **주식 결론은 `verdict.py`가 하드코딩한다.** `ready=False`(실측 78건 중 59건)면 "근거는 약합니다", NEUTRAL이면 "방향을 말하기 어렵습니다". 프롬프트로 못 뚫는다. 배경은 규제(유사투자자문업 신고 미완)보다 **데이터**("결론 단정은 데이터가 아직 허락하지 않는다") | `verdict.py:32,47`, `SIGNAL_OVERHAUL:15,17,69` |
| 4 | **가드가 누적돼 답이 고지·유의·면책으로 채워진다.** 문두 삽입 3종 + "추천→검토" 전면 치환 + 위험 문장 강제 + 면책 무조건 부착 + 용어 괄호. 본문은 상권 3곳·3~4문장으로 압축 | `answer_guard.py:141-259`, `chat_interactor.py:98,146,1298-1300` |
| 5 | **품질 게이트가 명쾌함을 재지 않는다.** baseline은 전부 0.98~1.0인데 자체 페르소나 테스트는 유용 11·애매 12·실패 7. 처방 I-21(질문 유형별 서술 프레임)은 "LLM 교체 뒤"로 미뤄져 미착수 | `EVAL.md:120`, `SERVICE_QUALITY:239,358` |

개인화: `user_profiles`(목적·위험 1~5·예산 구간·부채·기간)가 있으나 chat에서는 "서술 강조점 조정"만 하고
후보 선정·정렬에 전혀 쓰이지 않는다. "비슷한 사람들이 샀다"는 설계상 없다(M8 착수 조건 "실사용자 확보").

## 4-1. 판단 — 무엇이 풀리고 무엇이 남는가

- **상권은 규제 제약이 없다.** 유사투자자문업은 금융투자상품 얘기다. 상권 추천을 유보하게 만든 것은
  자체 규칙(임대료 없음 → 예산 단정 금지)뿐이다. 비용 데이터만 넣으면 "1억이면 여기 3곳"을 **단정해도 된다**.
- **주식은 두 겹이다.** "사세요"는 유사투자자문업 신고가 있어야 하는데, **사업자 등록·행정 신고는 하지 않는다**
  (2026-09-07 사용자 확정) — 따라서 매매 지시·권유 표현은 **영구 금지**다. 그러나 "결론 먼저 + 숫자 +
  기준선" 형태는 데이터 제공이지 권유가 아니라 지금도 허용된다 — 예측 페이지가 이미 표본·신뢰구간·기준선을 병기해 확률을 노출한다.
  chat만 "확률 단정 금지(페이지 전용)"로 묶여 있는 것은 **정책 불일치**이며 사용자 승인으로 풀 수 있다.
- **"비슷한 사람들이 샀다"는 3단계 모의투자가 원천이 된다.** 참가자(사람·EXAONE·지표 규칙)의 실제 거래
  기록은 사실 보고이지 권유가 아니다. 사용자가 적을 때는 EXAONE·지표 계정 거래가 내용을 채운다.
  "당신에게 적합"을 시스템이 판정하는 것만 계속 금지한다(투자자문 경계).
- **파이프라인은 바꾼다.** 지금은 LLM이 결론까지 쓰고 가드가 사후에 깎는다. 뒤집어서 **결론·순위·한계를
  결정론 골격(AnswerSkeleton)으로 먼저 만들고 LLM은 그 골격을 문장으로 옮기기만** 한다. 골격의
  결론 문장은 답변 첫 줄에 그대로 들어간다. 이미 `_answer_condition_ranking`·`_answer_signal_board`가
  이 방식이고 성적이 좋다(환각 0). 이것을 전 의도로 일반화하는 것이 4장의 핵심이다.

## 4-2. 단계

### C0 — 즉시 (프롬프트·가드·평가, 1~2일) — **mac 세션**

| 항목 | 변경 | 검증 |
| --- | --- | --- |
| "데이터 없음" 누출 제거 | `_format_stats`가 결측 필드를 **줄에서 빼고** 끝에 "제외 지표: …" 한 줄만 남긴다. phase1 표의 `'-'`도 동일 | 새 eval 지표 `missing_data_leak_count = 0` |
| 결론 우선 프레임(I-21 착수) | 답변 구조를 프롬프트로 고정: **1줄 결론 → 근거 2~3 → 한계 1줄**. 진단·데이터 질문에는 추천 문형 금지, 추천 질문에는 유보 문형 금지 | `verdict_first_rate`(첫 문장에 "알 수 없/어렵/약합니다/데이터 없음" 부재) |
| 고지 통합·후미 이동 | 문두 삽입 3종(`_unsupported_notice`·등급 고지·반경 미적용)을 **꼬리 "한계" 한 줄로 병합**. 면책은 1회. 용어 괄호는 첫 등장만 | `hedge_density`(유보 어구 수 ÷ 문장 수) baseline 대비 감소 |
| "추천→검토" 치환 해제 (상권만) | `suppress_recommendation`을 stock 의도에만 적용 | 골든셋 MR·MN에서 "추천" 허용, SF·MW는 유지 |
| 급등주 거절문 대체 | `_SURGE_PICK_RE` 거절 대신 신호 보드 + (3단계 뒤) EXAONE 오늘 거래로 답한다 | 결정론 경로 테스트 |
| 평가 확장 | 골든셋 각 행에 `expected_shape`(`recommend`/`diagnose`/`data`) 추가, 위 3지표 + `budget_addressed`(MN02류) 결정론 채점. LLM-judge는 계속 쓰지 않는다 | `baseline.json` 재박제(134 → 134, 지표 3개 추가) |

### C1 — 상권 예산 축 (데이터 2종, 1주) — **mac 세션**

| 항목 | 내용 |
| --- | --- |
| 창업비용(업종·브랜드) | data.go.kr 공정위 가맹정보 API(ROADMAP B4·B7 — 업종별 창업비용 15110293, 브랜드별 창업금액 15110265, 가맹점 현황·평균매출 15110241·15143710). **기존 `DATA_GO_KR_API_KEY`**, 수집 패턴 재사용. market 전용 DB에 `franchise_industry_costs`·`franchise_brands` (주 1회 cron) |
| 임대료(상권·자치구) | 한국부동산원 R-ONE 임대동향. **회원가입 수준의 키 발급이면 넣고, 사업자·서류가 필요하면 영구 생략**(기존 data.go.kr·서울열린데이터·DART 키는 개인 발급). 없으면 창업비용만으로 답하고 "임대료 제외"를 한계 줄에 적는다 — 이 상태로도 예산 질문은 답이 나온다 |
| 예산 라우팅 | `_CONDITION_AXES`에 **예산 축**(`\d+억|\d+천만|예산`) 추가. 예산 → 가능한 업종(창업비용 중앙값 ≤ 예산×0.7) → 그 업종의 상권 순위(점포당 월매출·폐업률). 프로파일 `budget_band`는 질문에 예산이 없을 때 기본값 |
| 프로파일을 정렬에 쓴다 | 상권 한정: `risk_level` 1~2면 폐업률 가중, 4~5면 매출 가중. `purpose`가 창업이면 업종 필터 우선. (주식은 계속 표시 필터만) |
| 허브 계약 | `AreaRankingInfo`에 `startup_cost_median`·`rent_monthly`(nullable) 추가, `CommercialDataPort.get_industry_costs(service_code)` 1개 |
| 단정 허용 | `_profile_market_block`의 "이 예산으로 가능하다고 단정하지 말 것" 삭제. 대신 "창업비용은 공정위 정보공개서 평균이며 임대료·권리금은 별도" 한계 줄 |

검증: MN02 "1억으로 치킨집" → 후보 3곳 + 각 창업비용·점포당 월매출·폐업률 + 한계 1줄. `budget_addressed = 1.0`.

### C2 — 파이프라인 재설계: AnswerSkeleton (2주) — **mac 세션, 상권 먼저**

```
질문 → phase0 의도 → [결정론] SkeletonBuilder(의도별)
        → AnswerSkeleton{ verdict: str, ranked_facts: list[Fact], limits: list[str], citations: list[int] }
        → [LLM] Renderer 프롬프트: "다음 골격을 자연스러운 한국어 3~5문장으로. verdict는 첫 문장에 그대로."
        → [결정론] 검사: 첫 문장 == verdict, 숫자는 골격에 있는 값만, 인용은 골격 id만 → 위반 시 골격을 그대로 출력(LLM 없이)
```

| 항목 | 내용 |
| --- | --- |
| 도메인 | `chat/domain/services/skeleton/{market,stock,market_news}_skeleton.py` (순수). verdict 문장 템플릿은 의도×상황별 표 |
| market 골격 | 조건 랭킹·지역 지정·업종 추천을 하나로: 후보 ≤3 · 각 후보 Fact(점포당 월매출·폐업률·창업비용·유동 피크) · verdict("예산 1억이면 A·B·C 순") · limits(임대료 제외 등) |
| stock 골격 | `verdict.py`를 흡수. NEUTRAL·ready=False도 **숫자로 말한다**: "신호 중립 · 과거 같은 상황 n=87 중 상승 52%(기준선 51%) — 우위 없음". 문장은 유보가 아니라 사실 |
| 렌더러 | phase2 프롬프트를 골격 렌더링 전용으로 교체. 컨텍스트가 골격뿐이라 토큰이 줄어 **상권 20~86초 지연 단축** 기대 |
| 폴백 | LLM 실패·검사 위반 시 골격을 그대로 문장화한 결정론 답(지금 조건 랭킹 답과 같은 품질) |
| 가드 | `answer_guard`의 사후 삭제·치환 대부분이 불필요해진다. 남기는 것: 면책 1회·금지 패턴 검사 |

검증: 골든셋 134 전부 통과 + 환각 0(골격 밖 숫자 0) + `verdict_first_rate = 1.0` + 상권 p50 지연 절반.

### C3 — 주식 명쾌함 (3단계 뒤) — **window 세션**

| 항목 | 내용 | 조건 |
| --- | --- | --- |
| chat 확률 인용 허용 | 예측 페이지와 같은 형식(표본·Wilson 구간·기준선·"과거 통계" 고지)이면 chat도 숫자를 말한다. stock CLAUDE "chat 확률 단정 금지(페이지 전용)" 개정 | **사용자 승인(정책)** |
| 다종목 비교 | "테슬라 vs 애플" → 2~3종목 analyze 병렬 + 비교 골격(같은 지표 표) | 없음 |
| "AI·참가자는 이걸 샀다" | 허브 `PaperDecisionPort`(3단계) — "오늘 EXAONE이 산 종목", "이번 주 참가자 순매수 상위", 프로파일 `risk_level` 같은 참가자 집계(표본 n 병기, n<10이면 EXAONE·지표 계정만) | 3단계 완료 |

## 4-3. 계속 막아 두는 것 (영구)

- **매매 지시·권유 표현("사세요/파세요/매수 추천")** — 유사투자자문업 신고를 하지 않으므로 해제 시점이 없다.
  ROADMAP [0-2]·[0-3]과 SIGNAL_OVERHAUL의 "신고 후 해제" 항목은 **폐기**한다. 주식은 끝까지 "정보 제공 +
  모의투자 기록"이며, 3단계 모의투자 화면·chat 답변의 "AI는 이걸 샀다"도 **기록 보고** 문형만 쓴다
  ("EXAONE 계정이 오늘 A를 샀다"는 되고 "A를 사라"는 안 된다). SITE_SPLIT 계획의 "주식 사이트 공개 게이트 = 신고"는
  "주식 사이트는 권유 없는 정보·기록 서비스로 공개"로 바꾼다.
- 시스템이 프로파일로 "당신에게 적합한 종목"을 자동 판정하는 것(투자자문업 경계). 상권은 해당 없음.
- 표본·기준선 없는 확률 숫자, "확실히/무조건/100%".
- LLM-judge로 주관 품질을 재는 것(순환 회피 결정 유지) — 명쾌함은 결정론 지표 3개로 잰다.

## 4-4. 기기·순서

- **2026-09-08 변경: 4장 전부 window 담당**(사용자 결정 — mac은 chat을 만지지 않음). C0·C3 상당분과 C1·C2의
  일부(예산 고지·프로필 정렬·업종 초점·숫자 가드·최상급 결정론)는 같은 날 페르소나 QA 후속으로 구현했다(b7b8d94).
  남은 C1: 공정위 창업비용 적재·예산 라우팅 축. 남은 C2: AnswerSkeleton 전면 전환(현재는 가드 조합).
- 확정(2026-09-07): 사업자 등록·행정 신고 없음 → 유사투자자문업 미신고 영구, 권유 표현 영구 금지.
- 미결(사용자): chat 확률 인용 정책 개정 승인(데이터 제공 형식 — 신고와 무관) · R-ONE 키가 개인 발급인지 확인(아니면 생략).
