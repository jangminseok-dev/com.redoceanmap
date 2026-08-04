# CLAUDE.md — game 앱

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]] ·
**경계·결정론 규칙(선행 필독)** → [[minseok/apps/game/_docs/game-harness|game-harness]] ·
도입 순서·수치 설계 → [[minseok/apps/game/_docs/game-strategy|game-strategy]]

게임 스포크. 한 앱에 게임 2개가 산다 — **모의투자**(가상 주가에 롱/숏)와
**상권 창업 시뮬레이터**(서울 상권 실데이터 위에 가게를 세워 키운다). 둘은 지갑 하나를 공유한다.

**이 앱을 만지기 전에 game-harness를 먼저 읽는다.** 아래는 요약이고 정본은 그쪽이다.

---

## 이 앱의 성질 — 다른 스포크와 다른 점

| 규칙 | 내용 |
|---|---|
| **상태 = 시각의 함수** | 주가·이벤트·손님 분포를 **저장하지 않는다.** `f(EPOCH, tick, 대상)`으로 계산하며 같은 입력은 언제·누가·몇 번 물어도 같은 값이다(harness §1-A). **유일한 예외가 관리자 주가 개입**(`game_price_interventions`) — 관리자의 의도는 난수에서 유도할 수 없다. `from_tick` 이후에만 효력이 있어 과거는 바뀌지 않는다 |
| **결정론 난수만** | `random`·내장 `hash()`·`uuid4`·`time.time()` **전부 금지.** blake2b 시드 유도 하나뿐(`domain/rng/deterministic.py`) |
| **현재 시각은 1파일** | `adapter/outbound/system_game_clock_adapter.py`만 `datetime.now()`를 부른다. 도메인·유스케이스는 `tick: int`을 받는다 |
| **cron 0개** | 인프로세스 스케줄러·배치가 없다. 서버가 꺼져 있어도 게임 시간은 밀리지 않는다 |
| **가상 주가** | 실시세를 쓰지 않는다. 모든 시세 응답이 `virtual: true`를 싣는다. 종목명도 가상 회사(업종만 실제). **36종목 = 묶음 업종 9 × 4**, 그중 4개는 밈 종목(σ 배수 + 전용 뉴스) |
| **상권 데이터는 읽기 전용** | market 전용 DB(:5434)에 붙지 않는다. 허브 `AreaDemandProfilePort` 경유(5단계) |
| **가정치 표기 강제** | 금액 필드는 `observed_*`(실데이터) / `assumed_*`(게임 규칙) / `simulated_*` 접두사를 붙인다(harness §5-1) |

## 슬라이스 (1:1 컨벤션)

| 슬라이스 | 엔드포인트 | 내용 |
|---|---|---|
| rulebook | `GET /game/myself` | 자기소개(가상 주가·매매 실행 아님·가정치 고지) **+ 현재 게임 시각**(tick·game_day·game_quarter·시즌 잔여) |
| market_price | `GET /game/market/prices?ticks=` | 전 종목 현재가·등락률·최근 곡선 + **오늘 거래량·시총**(표가 36종목을 거래대금·시총으로 줄 세우는 축 — 종목당 가격 평가 1회로 봉과 **같은 값**을 낸다) + **최근 호재·악재**. `ticks` 2~240. `candle_symbol` 지정 시 선택 종목의 **일봉(최대 120일)·거래량·이동평균 5·20·60·120·RSI(14)·상태 요약(5축)·차트 형태(틱·일봉 양축)** 동반 |
| wallet | `GET /game/wallet` | 현금·투자가능액·보유 포지션(현재 시세 평가)·총자산. 계정이 없으면 초기자본 100만원으로 자동 생성 |
| trade | `POST /game/trades` · `POST /game/trades/{id}/close` | 롱/숏 진입·청산. **레버리지 1~4배**(2배 이상은 만료 180틱 + 강제청산), 손실 상한은 증거금, 체결가는 요청 도착 틱 |
| area_fitness | `GET /game/areas/{trdar_code}/fitness?service_code=` | 창업 전 입지 미리보기 — 적합도 4축(수요·시간대·경쟁·생존) + 실데이터 근거 진단 문장 + **창업 가능 여부(`openable`)와 최소 자본**(store_open의 거절 조건을 미리 답한다). 허브 `AreaDemandProfilePort` 소비 |
| store_open | `POST /game/stores` | 창업 — 투입 자본이 가게 규모를 정한다. 보증금(회수 가능)·인테리어(회수 불가) 지불 |
| store_daily | `GET /game/stores` · `GET /game/stores/{id}?days=` | 가게 목록·현황. 일별 매출·비용·반려율과 오늘 온 손님 구성. **일별 매출은 저장하지 않고 재계산한다** |
| community | `GET·POST /game/community/posts` · `POST /game/community/posts/{id}/comments` · `DELETE .../posts\|comments/{id}` · `POST /game/community/reports` | 종목별 토론방 — 글·댓글(대댓글·공감 없음). **저장하는 슬라이스**(사람이 쓴 문장은 시각의 함수로 유도할 수 없다). 작성자는 `users.name`이 아니라 user_id에서 유도한 **결정론 가명**(`domain/community/nickname.py`) — 실명 노출도, 신규 허브 포트도 없다. '보유 중' 배지는 **조회 시점**의 열린 포지션 기준. 내리는 경로 둘을 컬럼으로 분리한다(본인 `deleted_at` · 어드민 `hidden_at`+사유) |
| (운영) | `GET·POST /admin/game/*` | 어드민 전용 — 자본 지급·주가 개입 + **토론방 신고 처리**(대기줄·숨김·해제). admin은 스포크라 직접 못 부르고 허브 `GameOpsPort`를 `adapter/outbound/gateways/game_ops_gateway.py`가 구현한다. **신고는 접수만 하고 글을 내리지 않는다** — 자동 숨김을 두면 몰려서 신고하는 것만으로 남의 글을 내릴 수 있다 |
| settlement | `GET /game/settlements` | 분기 결산 — **조회가 곧 정산 시점**(지연 실행, cron 0개). 밀린 분기를 확정하고 손익을 지갑에 반영한다. 멱등 |
| limit_order | `GET·POST /game/orders` · `POST /game/orders/exits` · `POST /game/orders/{id}/{cancel,extend}` | 지정가 — 진입 예약 + 청산 예약(익절·손절, 같은 포지션이면 OCO). **조회가 곧 체결 시점**(결산과 같은 지연 실행). 체결가는 지정가 고정·부분체결 없음(잔량 초과는 접수 거부), 진입 예약은 현금을 묶는다. **강제청산이 예약보다 우선**한다. 만료 180틱은 스캔 범위를 묶는 성능 장치라 없애지 않고 연장만 한다 |

## 레이어

```
apps/game/
├── domain/                                  # 순수 파이썬 — 프레임워크 전면 금지, 전부 def(CPU-bound)
│   ├── clock/game_epoch.py                  # 에포크 상수 단일 소유 + 틱↔게임달력
│   ├── rng/deterministic.py                 # blake2b u64/uniform/normal
│   ├── market/
│   │   ├── symbol_params.py                 # 종목 36개 σ·μ (캘리브레이션 산출물) + 밈 배수
│   │   ├── price_engine.py                  # 브라운 브리지 — price_at / price_series / 일봉 · 거래량
│   │   ├── indicators.py                    # 이동평균·RSI·볼린저·ATR·거래량비·OBV
│   │   ├── signal.py                        # 상태 분해 5축 — **예측 아님**(양수=뜨겁다)
│   │   ├── orderbook.py                     # 호가창·슬리피지 체결·VI·공매도 잔고
│   │   ├── fundamentals.py                  # 어닝 캘린더 — 분기 재무·PER·PBR·ROE + 어닝 이벤트
│   │   ├── market_events.py                 # 호재·악재 — 결정론 생성, 저장하지 않는다
│   │   └── price_intervention.py            # 관리자 개입 → MarketEvent 변환 (저장되는 유일한 사건)
│   ├── trading/trading_rules.py             # 수수료·증거금·손실상한·최소생활자금
│   ├── economy/rule_coefficients.py         # 임대료·인건비·원가 계수 — 이 파일이 유일 소유자
│   └── commerce/
│       ├── fitness.py                       # 적합도 4축 — 분포는 market, 판정은 게임 규칙
│       ├── diagnosis.py                     # 진단 문장 템플릿(LLM 미사용) + 조사 처리
│       ├── store_simulation.py              # 일일 매출·비용 — 시설이 매출 상한을 만든다
│       ├── customer_sampler.py              # 손님 표본 40명 — 실데이터 분포 역변환 샘플링
│       └── settlement.py                    # 분기 경계 계산 + 다음 분기 조언
├── app/
│   ├── dtos/{rulebook,market_price,wallet,trade,account}_dto.py
│   ├── ports/input/{rulebook,market_price,wallet,trade}_use_case.py
│   ├── ports/output/rulebook_record_port.py     # 활동 기록
│   ├── ports/output/game_clock_port.py          # 현재 틱 주입 — 전 슬라이스 공유
│   ├── ports/output/game_account_repository.py  # 지갑·포지션·원장 (한 트랜잭션이라 한 포트)
│   ├── use_cases/{rulebook,market_price,wallet,trade}_interactor.py
│   └── exceptions.py
├── adapter/
│   ├── inbound/api/{schemas,v1}/…_{schema,router}.py
│   └── outbound/
│       ├── system_game_clock_adapter.py         # datetime.now()를 부르는 유일한 파일
│       ├── log_rulebook_record_adapter.py
│       ├── orm/game_{wallet,position,ledger}_orm.py
│       └── pg/game_account_pg_repository.py     # 쓰기는 전부 커밋 한 번
├── dependencies/…_provider.py
└── tests/{domain,app/use_cases,adapter}/
```

**의존 방향:** `adapter → app → domain`. 컨벤션 → [[minseok/_docs/CLAUDE|minseok CLAUDE]].

## 아직 없는 것 (단계별로 들어온다)

**10단계까지 구현됐다.** 새 기능은 harness §6 게이트를 다시 통과해야 한다 —
특히 ⑥ "호출되지 않는 도메인 모듈을 미리 두지 않는다".

| 남은 단계 | 내용 | 정본 |
|---|---|---|
| ~~12~~ | ~~지정가 주문~~ → **백엔드 완료 2026-08-03**(`limit_order` 슬라이스 · `game_limit_orders`). 프론트 주문 UI가 남았다 | game-strategy §7-12 |
| 이후 | SLM 빌드타임 코퍼스 → 가상 인물·국가 → 종목 간 상관 | game-strategy §13 |

**11·13~20단계는 완료됐다**(2026-08-03) — 뉴스 UX·주식 화면 고도화·차트 패턴 분석·상권 화면/
밸런스/운영 액션·레버리지 1~4배, 그리고 시즌 1 재시작 배포.

> **지수 선물은 폐지됐다(2026-08-04, 사용자 결정).** 프론트 `1102965`가 화면을, 뒤이어
> 백엔드가 `futures` 슬라이스(라우터·유스케이스·DTO·포트·`domain/market/futures_contract.py`)와
> `game_positions.instrument` 컬럼(`g4d5e6f7a8b9`)을 걷어냈다. **제거 전 실측**: 선물 포지션이
> DB에 한 건도 없었고(10행 전부 STOCK·미청산 0) 지정가 주문도 0행이라, 프론트 커밋이 경고한
> "미정산 선물이 영영 정산되지 않는다"는 상황은 만들어진 적이 없어 강제 정산이 불필요했다.
> **한 건이라도 있었다면 정산이 제거보다 먼저다** — 만기 정산이 조회 시점 지연 실행이라
> 화면이 사라지면 정산 트리거도 함께 사라진다.

**다른 기기에서 이어받는다면 game-strategy §14를 먼저 읽는다** — 맥에서 되는 검증과
안 되는 것(마이그레이션 적용·σ 캘리브레이션·배포)이 갈린다.

> ⚠️ **시즌 1을 재초기화했다(21단계, 2026-08-03 15:00 KST).** 계수를 크게 바꿨지만
> `game_*` 테이블을 **전부 비우고** 여는 재초기화라 소급될 과거가 없다 — 20단계와 같은
> 근거로 `GAME_EPOCH_ID`는 **1로 유지**하고 `RULES_VERSION`만 `v2`로 올렸다(harness §1-4).
> 비우지 않고 유지하면 남은 지갑·포지션의 과거가 통째로 다른 값이 된다.
>
> | 바뀐 것 | 전 | 후 |
> |---|---|---|
> | 종목 수 | 12 (묶음 4 × 3) | **36** (묶음 9 × 4, 밈 4) |
> | 밈 종목 | 없음 | σ ×1.5 + 전용 이벤트(즉시 8~28%) |
> | 이벤트 확률 | 0.25 (게임 1일 1건) | **0.40** (1.6건) |
> | 가격 밴드 | 없음 | tanh 압축 ×10 / 밈 ×20 |
> | `MIN_STORE_SCALE` | 0.02 | **0.0005** (창업 가능 조합 61% → 99.7%) |
> | 변동성 | 상수 σ | **확률적**(시간 변경) — 클러스터링 +0.012 → +0.083 |
> | 레버리지 효과 | 없음(+0.009) | **−0.012** (실시장 −0.008과 부호 일치) |
> | 어닝 → 가격 | 무관계(ρ −0.03) | **연결**(ρ +0.33 · 상회 +5.3% / 하회 −1.5%) |
> | 상하한가·호가단위 | 없음 | **±30% · 한국거래소 호가 격자** |
> | 체결 | 현재가 즉시 전량 | **호가창 소진(슬리피지)** · VI 발동 시 매매 정지 |
> | 배당·유상증자 | 없음 | **배당(롱 수령·숏 지급) + 배당락 · 증자 희석**(밈이 잦다) |
> | 어드민 개입 | 없음 | 자본 지급 · 주가 개입(`/admin/game/*`) |

## 검증

```bash
cd minseok

# 테스트 — 도메인이 순수 파이썬이라 도커 없이 이 맥에서 돈다
PYTHONPATH=apps python3 -m pytest apps/game -q

# 결정론·경계 회귀 (AST — grep은 주석까지 잡아 오탐률 100%였다, harness §8-0)
PYTHONPATH=apps python3 scripts/check_game_determinism.py

# 구조 계약 5종
PYTHONPATH=apps lint-imports --config .importlinter
```
