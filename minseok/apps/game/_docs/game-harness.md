# GAME-HARNESS — 게임 스포크의 경계·결정론 규칙·도입 게이트

> 한 스포크에 게임 2개가 산다. **모의투자**(가상 주가에 롱/숏)와 **상권 창업 시뮬레이터**
> (서울 상권 실데이터 위에 가게를 세워 키운다). 참조 게임은 아이러브커피(파티게임즈)이나
> 우리 게임에는 **수동 탭이 없어** 원작 장치 중 ①꾸미기 점수 ②취향 룩업 ③파산 없음
> ④퀘스트 상한만 골라 이식한다.
> 2026-07-31 현재 `apps/game/`에는 **이 문서와 game-strategy 두 개의 0바이트 파일뿐이고
> 코드는 0줄**이다. 이 문서는 기능 설계서가 아니라 *무엇을 해도 되는가*를 고정하는 배선(harness)이다.

관련: [[minseok/_docs/CLAUDE|minseok CLAUDE]] · [[_docs/harness|harness]] ·
[[minseok/apps/hub/_docs/CLAUDE|hub CLAUDE]] · [[minseok/apps/market/_docs/CLAUDE|market CLAUDE]] ·
[[minseok/apps/stock/_docs/CLAUDE|stock CLAUDE]] · [[minseok/_docs/ROADMAP|ROADMAP]] ·
도입 순서·수치 설계 → [[minseok/apps/game/_docs/game-strategy|game-strategy]]

**역할 분담:** 이 문서는 *무엇을 해도 되는가*(시간 모델·결정론·데이터 경계·DB 배치·게이트·검증)를
정한다. *어떤 순서로 · 어떤 수치로 · 무엇으로 끝났다고 판정하는가*는 game-strategy가 맡는다.
게임 규칙의 구체값(변동성 계수·매출 산식·밸런스 목표)은 전부 strategy 쪽이다.

> `minseok/apps/game/_docs/CLAUDE.md`(앱 문서)와 `game/CLAUDE.md` 심볼릭 링크는 **아직 없다.**
> strategy 1단계에서 다른 스포크와 같은 패턴으로 만든다.

---

## 0. 현재 상태 (2026-07-31, 1단계 완료 시점 갱신)

| 항목 | 실측 | 확인 방법 |
|---|---|---|
| game 앱 코드 | **4단계 완료.** 슬라이스 4개(`rulebook`·`market_price`·`wallet`·`trade`) + 도메인 5모듈. 테스트 92개 통과 | `PYTHONPATH=apps python3 -m pytest apps/game -q` |
| 결정론·경계 검사 | **위반 0건** (61파일 AST 검사) | `python3 scripts/check_game_determinism.py` |
| 응답 성능 | 12종목 × 60틱 **p95 13.8ms** / × 240틱(최대) **p95 54.5ms** — 목표 200ms | 인터랙터 직접 호출 30회 |
| DB | **테이블 3개**(`game_wallets`·`game_positions`·`game_ledger`), 마이그레이션 `a2b3c4d5e6f7`. ⏸ **적용은 미실행**(이 맥에 DB 없음) | ORM↔마이그레이션 일치 테스트 |
| 프론트 | `/game` — 시세 차트 + 자산 요약 + 주문 폼 + 포지션 청산(4단계). **수수료율은 서버가 내려준다** | `www/app/(seoul)/game/` |
| ROADMAP 스포크 판정 | `game` 행 **추가됨**(0단계). 같은 표에 `soccer = 삭제됨 (2026-07-15)` | `minseok/_docs/ROADMAP.md` |
| `.importlinter` | `root_packages` **9개** — `game` 등록 완료(6지점). **계약 5종 전부 KEPT** | `PYTHONPATH=apps lint-imports --config .importlinter` |
| 인프로세스 스케줄러 | **0건** — `APScheduler`·`asyncio.create_task`·`BackgroundTasks` grep 전부 0줄. Celery·RQ 없음. **game이 추가한 cron·배치도 0개** | `grep -rn "APScheduler\|BackgroundTasks\|asyncio.create_task" minseok/` |
| 난수 | **`import random` 0건** (`apps/`·`scripts/` 전역). game은 blake2b 시드 유도만 쓴다 | `scripts/check_game_determinism.py` |
| 검증 환경 (이 맥) | Python **3.11.15** · pytest **9.1.1** · pytest-asyncio **1.4.0** · import-linter 설치됨. **도커는 없다**(§8 참고) | `python3 -V` · `docker info` |
| 주기 실행 수단 | 호스트 OS cron뿐(저장소에 crontab 파일·systemd unit 없음). cron은 루트 `venv/` 사용 | 루트 CLAUDE.md |
| WebSocket / SSE | WS **0건**. SSE는 `chat_router.stream` 1건(`StreamingResponse` 수동 프레이밍) | `grep -rn "websocket\|StreamingResponse" minseok/apps` |
| 서버측 캐시 선례 | 모듈 전역 dict + `_CACHE_TTL_SECONDS = 30.0` | `stock/app/use_cases/stock_quote_interactor.py` |
| 허브 `CommercialDataPort` | 메서드 **7개**. `AreaRawStat`에 **매출 건수 없음** · 매출 분해축은 `weekday_sales_amount` 하나뿐(시간대·성별·연령 분해는 **유동인구에만** 있다) | `hub/app/ports/output/commercial_data_port.py` · `hub/app/dtos/commercial_data_dto.py` |
| 상권 실데이터 | 서울 1,650상권 × 업종 × 분기. `estimated_sales`가 요일7·시간대6·성별2·연령6 × (금액·건수) **50컬럼** 보유 | `market/adapter/outbound/orm/estimated_sales_orm.py` |
| 임대료·인건비·원가 | **데이터 없음.** ROADMAP이 "비용 측면(임대료 부재)"을 3대 공백으로 명시 | `minseok/_docs/ROADMAP.md` |
| 주가 실데이터 | `price_bars` 68종목 `1d`/`5m`. **종목 마스터 테이블 없음**(워치리스트 텍스트 파일 + 코드 사전) | `stock/adapter/outbound/orm/price_bar_orm.py` |
| 포트폴리오·체결 | **테이블 0개.** stock 앱 정책 "매매 실행은 다루지 않는다" | stock CLAUDE |
| 탭 온톨로지 | `TAB_KEYS = ("history","market","stock","vision","automation")` — `game` 없음. **넣지 않는다**(§10-1: 전 유저 공개라 게이팅 대상이 아니다) | `hub/domain/navigation/tab_ontology.py` |
| 지도 | `www/components/seoul/MapView.tsx` — **주어진 마커 선택만**. 임의 좌표·드래그·폴리곤·지오코딩 전무 | 파일 전문 |
| 전용 DB 선례 | market 하나뿐(:5434). compose + alembic 체인 + `core/config.py` + `core/database.py` 세트 | market CLAUDE |

---

## 1. 게임 시간 모델 — 결정론 계산이 유일한 답이다

사용자가 확정한 3조건이 있다. **① 오프라인 진행**(미접속 중에도 주가가 움직이고 가게가 장사한다)
**② 공용 시장**(전 유저가 같은 주가·같은 이벤트를 본다) **③ 서버 틱 프로세스 없음**(§0 실측 —
이 저장소에 인프로세스 스케줄러가 0건이고 cron은 분 단위 하한에 매번 새 프로세스로 뜬다).

| 조건 | 구현 후보 | 판정 |
|---|---|---|
| ① 오프라인 진행 | (a) 서버 틱이 상태를 갱신 / (b) 요청 시 경과분을 계산 | (a)는 ③에 막힌다 |
| ② 공용 시장 | (a) 단일 writer가 DB에 가격 기록 / (b) 유저 무관 순수 함수 | (a)는 다시 틱 프로세스를 요구한다 |
| ③ 틱 프로세스 없음 | — | **(b)만 남는다** |

> ⇒ **규칙 1-A. 게임 상태는 "저장된 값"이 아니라 "시각의 함수"다.**
> `값 = f(EPOCH, tick, 대상)` — 같은 입력이면 언제·누가·몇 번 물어도 같은 값이 나온다.
> 이 한 문장에서 아래 규칙 전부가 파생된다.

### 1-1. 고정 상수

전부 `game/domain/clock/game_epoch.py` 한 파일에 산다. **이 파일 밖에서 시간 리터럴을 쓰지 않는다.**

| 상수 | 값 | 근거 |
|---|---|---|
| `GAME_EPOCH_ID` | `1` | 시즌 식별자. 계수·모델을 바꾸면 **반드시 올린다**(1-4) |
| `GAME_EPOCH_START_UTC` | 착수일 09:00 KST에 고정, 이후 불변 | 시즌 시작 시각 |
| `TICK_SECONDS` | `60` | 프론트 폴링 하한(stock 30초·MarketBoard 60초)과 정합 |
| `TICKS_PER_GAME_DAY` | `60` | **실제 1시간 = 게임 1일**(사용자 확정) |
| `GAME_DAYS_PER_QUARTER` | `90` | 게임 90일 = 1분기 = 현실 90시간 = 3.75일 |
| `QUARTERS_PER_SEASON` | `8` | **1시즌 = 현실 약 30일**(사용자 확정) |
| `SEASON_TICKS` | `43_200` | `8 × 90 × 60`. 이 틱을 넘으면 시즌 종료 상태 |
| `DATA_QUARTER` | `20254` | **실데이터 분기를 에포크에 박는다**(1-5) |
| `RULES_VERSION` | `"v1"` | 산식 버전. 시드 유도에 들어간다 |

`current_tick = (now_utc - GAME_EPOCH_START_UTC) // TICK_SECONDS`.
**`datetime.now()` 호출은 어댑터 1파일에만 허용**하고, 도메인 함수는 `tick: int`만 받는다(§8 회귀).

### 1-2. 가격 시계열은 O(경과틱)이 아니라 O(log)로 계산한다

누적 재귀(`p[t] = p[t-1] × ...`)는 복귀 유저에서 무너진다 — 현실 10일 미접속이면 게임 240일 =
14,400틱이고, 여기에 종목 수를 곱해야 한다. **2단 브라운 브리지**를 쓴다.

```
logP(sym, t) = logP0(sym) + μ(sym)·(t / 60) + σ_tick(sym)·W(sym, t) + J(sym, t)

  W       : [0, 2^16] 구간의 표준 브라운 운동. 양 끝을 고정하고 이분 분할로 t까지
            내려간다 — 중점의 조건부 분포는 평균 (w_lo+w_hi)/2, 분산 (hi-lo)/4.
            시드가 (lo, hi) 쌍이라 같은 노드는 어느 경로로 와도 같은 값이다.
  σ_tick  : sigma_daily × SIGMA_GAME_MULTIPLIER / sqrt(60)
            — 60틱(게임 1일) 누적이 정확히 일간 변동성이 되도록 나눈다
  J       : 최근 EVENT_WINDOW(게임 3일 = 180틱) 내 이벤트 충격 합 (9단계에 도입)
```

호출당 **정규난수 16개**(= blake2b 32회)로 경과 시간과 무관하다.
가격 테이블·앵커 캐시·cron이 **전부 불필요**해진다.
구현: `domain/market/price_engine.py`.

> **1단계에서 2단 브리지를 단일 브리지로 합쳤다(2026-07-31).** 원안은 일 단위 브리지와
> 일중 브리지를 겹치는 구조였는데, 브라운 운동의 **자기유사성** 덕에 틱 단위 단일 브리지와
> 결과가 동등하다. 레벨 수(16)와 성능도 같고 코드는 절반이다. 일봉이 필요하면 `t = d × 60`에서
> 평가하면 된다 — 별도의 일봉 축을 둘 이유가 없었다.

> **기각한 대안:** "일봉 종가를 `game_price_days`에 캐시하고 마지막 앵커 이후만 재계산."
> 성능은 되지만 (a) 게임 규칙의 산출값을 DB에 영속시켜 **계산식과 저장값이 갈라질 수 있는
> 자리**를 만들고 (b) 앵커 채우기가 lazy면 동시성 문제가, cron이면 스케줄러 의존이 생긴다.
> 브리지가 실제로 성능 문제를 일으킬 때의 **폴백**으로만 남긴다 — 그때도 캐시는 파생본이고
> 정본은 계산식이다.

### 1-3. 시드 유도는 한 가지 방식뿐이다

```python
def _u64(ns: str, key: str) -> int:
    seed = f"{GAME_EPOCH_ID}|{RULES_VERSION}|{ns}|{key}".encode()
    return int.from_bytes(blake2b(seed, digest_size=8).digest(), "big")

# uniform = _u64(...) / 2**64        → [0, 1)
# normal  = Box-Muller(_u64_a, _u64_b)
```

- ⛔ **내장 `hash()` 금지.** `PYTHONHASHSEED`로 프로세스마다 달라진다 — 재현성이 조용히 깨지는
  가장 흔한 경로다. 워커가 여러 개면 유저마다 다른 주가를 보게 된다.
- ⛔ **`random.Random(seed)` 금지.** 결정론이긴 하나 CPython 구현 안정성에 기대게 되고,
  "`random` 0줄" 회귀 규칙(§8)이 무너진다.
- ⛔ **`uuid4()`·`time.time()`을 값 생성에 쓰지 않는다.**

### 1-4. 계수를 바꾸면 `GAME_EPOCH_ID`를 올린다

파라미터만 고치고 에포크를 유지하면 **과거 전 구간이 소급 변조된다.** 어제 100원에 산 종목의
매수 시점 가격이 오늘 조회하면 90원이 되고, 이미 저장된 체결가·분기 결산과 어긋난다.

지갑·포지션·결산 행은 `epoch_id`·`rule_version` 컬럼을 갖고, 현재 에포크와 다르면
**읽기 전용(과거 시즌 동결)**으로 표시한다. 시즌 전환(→ game-strategy §5)이 곧 계수 재조정의
정당한 창구다.

### 1-5. 실데이터 분기를 에포크에 박는다

`DATA_QUARTER = 20254`. market이 20261분기를 적재해도 **진행 중인 게임의 매출 기준선은 바뀌지
않는다.** "최신 분기 추종" 설계였다면 어느 날 갑자기 모든 유저의 가게 매출이 달라진다.
새 분기 반영은 새 에포크(= 새 시즌)에서 한다.

### 1-6. 미래 틱 조회 금지

결정론 모델의 유일한 구멍이다. **`t > current_tick`이면 400**을 낸다.
시드·상수·모델 파라미터를 클라이언트로 내려보내지 않는다 — 프론트는 가격을 **계산하지 않고 받는다.**

---

## 2. 경계 — game이 하지 않는 것

| 항목 | 판정 | 근거 |
|---|---|---|
| 실제 주문·실계좌·브로커 연동 | ⛔ | stock 앱 정책("매매 실행은 다루지 않는다")을 game이 우회하는 통로가 된다 |
| 실시세 표시 | ⛔ | 주가는 전부 서버 생성 가상값. **모든 시세 응답에 `virtual: true` 고정 필드** |
| 실제 종목명·티커 노출 | ⛔ | **가상 사명 + 실제 업종**으로 쓴다(사용자 확정). 가상 주가에 실명을 붙이면 실시세 오인이 생기고, 서버가 만든 가짜 악재가 실재 기업에 대한 허위정보처럼 읽힌다. 실 티커 매핑은 캘리브레이션 단계에서 익명화해 상수로 굽고 **서버에도 남기지 않는다** |
| 상권 실데이터 쓰기 | ⛔ **읽기 전용** | game은 market 전용 DB(:5434)에 붙지 않는다. 게임 규칙으로 만든 값을 실데이터 테이블에 섞지 않는다 |
| 결제·환전·현금 입출금 | ⛔ | ROADMAP 과설계 목록. 게임 통화는 게임 안에서만 순환한다 |
| 확률형 뽑기(가챠)·랜덤 보상 상자 | ⛔ | 사행성. 랜덤은 **시장 변동과 손님 분포에만** 존재하고 "지불하고 뽑는" 구조를 만들지 않는다 |
| 파산·게임오버 | ⛔ | 아이러브커피 ③ 이식. 실패는 전부 **기회 손실**로 표현한다. 잔고 하한 보전 + 휴업 상태로 처리 |
| 만료되고 포기 불가능한 퀘스트 | ⛔ | 아이러브커피 ④ — 원작의 실제 이탈 원인은 난이도가 아니라 퀘스트 폭주(포기 기능 없음)였다. 도입하더라도 **동시 3개 상한 + 포기 버튼 필수 + 만료 없음** |
| 유저 간 자산 이전·PvP 거래 | ⛔ | 공용 시장이라 시세 조작·현금거래 통로가 된다 |
| WebSocket·SSE 실시간 푸시 | ⛔ | 저장소 WS 0건. **폴링만 쓴다** — 결정론 모델은 폴링과 궁합이 완벽하다(언제 물어도 같은 답) |
| cron·인프로세스 스케줄러 신설 | ⛔ | 결정론 설계의 존재 이유다. **game의 cron 목표 개수는 0.** 2026-07-25~27 수집 cron 7종이 2일 6시간 멈췄는데 아무도 몰랐던 선례가 있다 — game은 멈출 것이 없다 |
| LLM으로 이벤트 문구·손님 대사 생성 | ⛔ | 결정론 위반 + EXAONE 추론 비용. **템플릿 룩업만** 쓴다 |

---

## 3. 데이터 접근 경계 — 어떤 포트를 만드는가

**스포크끼리 직접 import 금지**이므로 game은 `market`·`stock`을 import할 수 없다.
두 도메인의 처리 방식이 다르고, **그 비대칭이 이 절의 핵심이다.**

### 3-1. 판정 (a) — 상권: 허브 신규 포트 1개, 메서드 1개

| 게임이 필요한 것 | 기존 `CommercialDataPort`로 되나 | 처리 |
|---|---|---|
| 상권 목록·좌표·구·동 | ✅ `get_area_summary()` → `AreaInfo` | **기존 재사용** |
| 업종 코드 목록 | ✅ `get_service_codes()` | **기존 재사용** |
| 월매출 금액·점포수·유사업종수·폐업률 | ✅ `get_area_raw_stats()` | 기존으로 되지만 아래와 한 번에 받는 편이 낫다 |
| **월매출 건수** (객단가의 분모) | ⛔ `AreaRawStat`에 없다 | **신규** |
| **매출의 요일7·시간대6·성별2·연령6 비중** | ⛔ 없다 — `weekday_sales_amount` 하나뿐이고 시간대·성별·연령 분해는 **유동인구에만** 있다 | **신규** |

⇒ **신규 `AreaDemandProfilePort`** (`hub/app/ports/output/`) — 메서드 **1개**:

```python
async def get_demand_profile(
    self, trdar_code: int, service_code: str, year_quarter: int
) -> AreaDemandProfile | None: ...
```

**기존 포트 확장이 아니라 신설인 근거 3개:**

1. `CommercialDataPort`는 이미 **메서드 7개로 chat·admin 두 소비자**를 물고 있다. 게임 전용
   메서드를 얹으면 `CommercialDataGateway`와 그 스텁 테스트 전부가 게임 사정으로 흔들린다.
2. **소비자별 계약 분리 선례가 이미 3쌍 있다** — `RecommendationDirectoryPort`/`RecommendationRecordPort`,
   `StockAnalysisPort`/`StockForecastPort`, `StockDatasetStatsPort`(hub CLAUDE의 "Record ↔ Directory 분리").
3. 게임이 원하는 것은 원시 통계 요약(`AreaRawStat`의 결)이 아니라 **분포 프로필**이다.
   market에는 이미 `area_detail_pg_repository.find_sales_mix`가 같은 축을 읽고 있어 게이트웨이는 얇다.

`AreaDemandProfile` DTO(`hub/app/dtos/area_demand_profile_dto.py`, 순수 frozen dataclass):

```
trdar_code · service_code · year_quarter
observed_monthly_sales_amount · observed_monthly_sales_count      # 절대금액은 이 둘만
observed_store_count · observed_similar_store_count
observed_closure_rate · observed_operating_months_avg
weekday_share[7] · hour_share[6] · gender_share[2] · age_share[6]  # 합 1.0으로 정규화
floating_total · floating_hour_share[6] · floating_age_share[6]
has_sales · has_store
```

**절대금액을 2필드로 묶고 나머지를 전부 비중으로 내리는 이유:** 게임 매출은 어차피 게임 규칙으로
스케일되므로 분포만 있으면 된다. 절대값을 다 내리면 DTO가 50필드가 된다.

### 3-2. 판정 (b) — 주식: 허브 포트 0개. 빌드타임 상수로 굽는다

`scripts/calibrate_game_symbols.py`(수동·저빈도)가 `price_bars`(`1d`)에서 종목별 σ·μ를 뽑아
**게임 도메인 상수 파일** `game/domain/market/symbol_params.py`로 떨군다.

**근거 3개:**

1. 캘리브레이션 값은 **게임 규칙 파라미터**이지 런타임 데이터가 아니다. 런타임에 DB에서 읽으면
   봉이 하루 갱신될 때마다 σ가 미세하게 바뀌고 **과거 주가 전 구간이 소급 변조된다** —
   규칙 1-A/1-4 정면 위반이다.
2. **68종목 × 스칼라 2개는 상수로 굽기에 충분히 작다.** 상권은 1,650 × 업종 100 조합이라
   굽을 수 없다 — 이 크기 비대칭이 (a)와 (b)를 가르는 실질적 이유다.
3. 결과적으로 game 런타임의 DB 접근은 **자기 테이블뿐**이고, 허브 포트 소비는 상권 1개뿐이다.

---

## 4. DB 배치 판정 — 공유 DB(:5432)

| 후보 | 판정 | 근거 |
|---|---|---|
| **공유 DB(:5432)** | ✅ **채택** | ① `users.id` FK가 필요하다 — auth가 공유 DB 소유. market이 전용 DB로 갈 수 있었던 건 **유저와 무관한 공공데이터**여서였고, game은 정반대로 **전부 유저 소유 데이터**다. ② game은 market 테이블을 직접 읽지 않는다(§3 허브 포트 경유) → 전용 DB의 명분이던 "대용량 공공데이터 격리"가 해당 없음 |
| market 전용 DB(:5434) | ⛔ | 앱별 DB 불가침 위반. game 테이블을 market DB에 만들지 않는다 |
| game 전용 DB(신규) | ⛔ | `docker-compose.yml` + `alembic{,.ini}` 체인 + `core/config.py GAME_DATABASE_URL` + `core/database.py init_game_engine/get_game_db` + 백업 스크립트 + prod env **6세트**를 만들고, 그 대가로 유저 FK가 끊긴다. **soccer가 DB 컨테이너(:5433)·볼륨까지 만들었다가 통째로 삭제된 선례**가 있다 |

⇒ 마이그레이션은 `minseok/alembic/versions/`에 수기 revision hex(관례: `a1b2c3d4e5f7` 형태),
`minseok/alembic/env.py`에 ORM import 한 줄 추가(autogenerate 인식용).
⇒ **신규 env 키 0개.** `MARKET_DATABASE_URL` 유실로 3일간 조용히 메인 DB에 적재된 2026-07-24
사고를 game은 구조적으로 겪을 수 없다.

### 4-1. 테이블 (전량 `int` 단일 PK `id` — ENTITY_RULES 준수)

| 테이블 | 도입 단계 | 핵심 컬럼 |
|---|---|---|
| `game_wallets` | 3 | `user_id`(UNIQUE) · `cash_krw`(BigInteger) · `epoch_id` · `rule_version` |
| `game_positions` | 3 | `user_id` · `symbol` · `side` · `quantity` · `entry_tick` · `entry_price_krw` · `closed_tick` · `realized_pnl_krw` · `fee_krw` · `epoch_id` |
| `game_ledger` | 3 | `user_id` · `game_day` · `source`(`initial`\|`trade`\|`store`\|`settlement`) · `amount_krw` · `ref_type` · `ref_id` |
| `game_stores` | 6 | `user_id` · `trdar_code` · `service_code` · `opened_game_day` · `status` · `facility_score` · `deposit_krw` · `epoch_id` |
| `game_store_decisions` | 6 | `store_id` · `effective_from_day` · `payload`(JSONB) — **결정론 재계산의 입력** |
| `game_quarter_settlements` | 8 | `store_id` · `game_quarter` · 수익·비용 분해 · `payload`(JSONB) |

**한 번에 6개를 만들지 않는다**(§6 게이트 ⑤). 3단계에 3개, 6단계에 2개, 8단계에 1개다.

### 4-2. 저장하는 것과 계산하는 것 — 이 문서의 핵심 비대칭

| 대상 | 저장 | 이유 |
|---|---|---|
| 주가·이벤트·손님 분포 | ⛔ **저장하지 않는다** | 순수 파생본이다. 언제든 재계산되고, 저장하는 순간 계산식과 갈라질 자리가 생긴다 |
| 체결가(`entry_price_krw`) | ✅ 저장하되 **정본은 계산식** | 저장값은 대조용 스냅샷이다. 재계산값과 어긋나면 그건 캐시 불일치가 아니라 **버그 알람**이다(§8 회귀 대상) |
| 지갑·원장·결산 | ✅ **도메인 사실** | 유저 행위의 결과이지 시각의 함수가 아니다. 분기 결산은 캐시가 아니라 게임 규칙상 실재하는 사건이다 |

---

## 5. "실측이 아닌 값" 표기 규칙

임대료·인건비·원가 데이터가 **통째로 없다**(§0). 게임 규칙으로 산식을 정의하되,
**실데이터와 가정치가 섞여 보이는 것을 구조적으로 막는다.**

### 5-1. 필드 접두사로 출처를 강제한다 (DTO·스키마 공통)

| 접두사 | 의미 | 예 |
|---|---|---|
| `observed_*` | market 실데이터 유래 | `observed_monthly_sales_amount` |
| `assumed_*` | 게임 규칙 유래(실측 아님) | `assumed_monthly_rent_krw` · `assumed_labor_cost_krw` |
| `simulated_*` | 게임 규칙 + 결정론 난수 유래 | `simulated_daily_sales_krw` |

**접두사 없는 금액 필드는 리뷰 반려**다(§8 grep 회귀). 예외는 게임 내부 통화 필드
(`cash_krw`·`deposit_krw`·`fee_krw`·`realized_pnl_krw`)뿐이며, 이건 출처를 물을 대상이 아니다.

### 5-2. 응답 객체마다 근거 블록을 단다

```json
{
  "basis": {
    "observed_quarter": 20254,
    "epoch_id": 1,
    "rule_version": "v1",
    "assumed_fields": ["assumed_monthly_rent_krw", "assumed_labor_cost_krw", "assumed_cogs_krw"],
    "note": "임대료·인건비·원가는 실데이터가 없어 게임 규칙으로 산정한 가정치입니다."
  }
}
```

프론트는 `assumed_fields` 배열을 읽어 **가정치 배지를 자동으로** 붙인다.
**수기로 붙이지 않는다** — 필드가 늘어날 때 반드시 빠뜨린다.

### 5-3. 계수는 한 파일에만 산다

`game/domain/economy/rule_coefficients.py`. 각 계수는 값과 출처의 쌍이다.

```python
RENT_RATIO = Coefficient(0.10, source="rule")   # 실데이터가 생기면 source="observed"
```

실데이터가 확보되면 `source`를 바꾸는 것만으로 §5-2의 배지가 사라진다 —
이것이 "**계수만 교체 가능한 구조**"의 실제 구현이다.
이 파일 밖의 임대료·인건비·원가 리터럴은 grep 회귀로 막는다(§8).

### 5-4. 실데이터 분기와 게임 분기의 이름을 절대 섞지 않는다

`year_quarter`(실데이터, `20254`) vs `game_quarter`(게임, `1~8`).
같은 단어를 쓰면 조용한 버그가 난다 — 값의 자릿수가 달라 타입 검사로도 안 걸린다.

---

## 6. 스켈레톤 금지 게이트 — ✅ 6개 전부 통과 (2026-07-31, 0단계에서 채움)

> **근거: soccer 삭제(2026-07-15).** 스켈레톤 금지 원칙으로 코드·DB 컨테이너(:5433)·볼륨까지
> 통째로 지웠다. 같은 표에 "CRUD 2-3개짜리 새 스포크는 과설계"라는 판정 문구도 있다.
> **게임이 두 개라는 사실은 게이트 면제가 아니다.**

### ✅ ① ROADMAP 스포크 판정

`minseok/_docs/ROADMAP.md`의 `## 새 도메인(스포크) 판정` 표에 행을 추가했다.
판정은 **새 스포크**, 근거는 *"listing과 동일 논리 — 유저 진행상태(쓰기)는 공공데이터
스포크와 액터·라이프사이클이 다르다. 게다가 두 도메인을 지갑 하나로 가로질러 market·stock
어느 쪽에도 넣을 수 없다"*.

### ✅ ② 첫 커밋에 응답이 나오는 엔드포인트 2개

1단계 커밋에 **수직 슬라이스 2개**가 들어간다. 둘 다 인터랙터가 실제 계산을 수행한다.

| 슬라이스 | 엔드포인트 | 내용 |
|---|---|---|
| `rulebook` | `GET /game/myself` | 자기소개(가상 주가 · 매매 실행 아님 · 가정치 고지) **+ 현재 게임 시각**(`tick` · `game_day` · `game_quarter` · 시즌 잔여) |
| `market_price` | `GET /game/market/prices` | 종목별 가격 곡선(`symbol` · `ticks` 파라미터) |

`rulebook`이 게임 시각을 함께 반환하는 것이 핵심이다 — **프론트가 첫 진입에 반드시 부르는
엔드포인트**가 되어 자기소개가 빈 껍데기로 남지 않는다(라우터 컨벤션 4항: 아웃바운드 포트는
빈 껍데기 금지).

### ✅ ③ 허브 포트는 소비자와 같은 커밋

`AreaDemandProfilePort`는 **5단계 단일 커밋**에 소비자(적합도 미리보기 슬라이스)와 함께 들어간다.
포트만 먼저 정의하는 커밋을 만들지 않는다.

### ⚠️→✅ ④ 화면 없이 슬라이스 4개 금지 — **위반을 발견해 단계를 재배치했다**

이 게이트를 검증하다 **원래 단계 표가 스스로를 위반**하고 있었다:
구 1단계(슬라이스 2) + 구 2단계(슬라이스 2) = **화면 없이 4개**가 쌓이고 화면은 구 3단계였다.

재배치 후 "화면 하나가 붙기 전에 연속으로 쌓이는 슬라이스 수"는 다음과 같다.

| 구간 | 연속 슬라이스 | 화면 |
|---|---|---|
| 1단계 | 2 (`rulebook` · `market_price`) | 2단계 |
| 3단계 | 2 (`wallet` · `trade`) | 4단계 |
| 5·6단계 | 3 (`area_fitness` · `store_open` · `store_daily`) | 7단계 |
| 8단계 | 1 (`settlement`) | **같은 단계에 결산 화면 포함** |

전 구간 3개 이하다. 새 단계 표 → game-strategy §2.

### ✅ ⑤ 테이블은 인터랙터가 실제로 쓰는 것만

6개를 한 번에 만들지 않는다. **3단계 3개 · 6단계 2개 · 8단계 1개**(§4-1 표).
각 마이그레이션은 그 테이블을 읽고 쓰는 인터랙터가 있는 단계에서만 나간다.

### ✅ ⑥ 호출되지 않는 도메인 모듈을 미리 두지 않는다

1단계에 만드는 `game/domain/` 모듈과 **그 호출자**를 미리 못박는다.

| 모듈 | 호출자 |
|---|---|
| `clock/game_epoch.py` | `rulebook` · `market_price` 인터랙터 |
| `rng/deterministic.py` (blake2b 시드) | `price_engine` |
| `market/symbol_params.py` (캘리브레이션 상수) | `price_engine` |
| `market/price_engine.py` | `market_price` 인터랙터 |

**1단계에 만들지 않는 것:** `economy/`(비용 산식 — 6단계) · `simulation/`(손님 샘플러 — 6단계) ·
`quest/`·`ranking/`·`season/`(범위 밖, §9).

---

## 7. 계층·구조 규칙

### 7-1. `.importlinter` 등록 — 6지점

| # | 위치 | 추가 |
|---|---|---|
| 1 | `[importlinter] root_packages` | `game` |
| 2 | 계약 1 `clean-architecture` → `containers` | `game` |
| 3 | 계약 2 `spoke-independence` → `modules` | `game` |
| 4 | 계약 2.5 `framework-isolation` → `source_modules` | `game.app` · `game.domain` (2줄) |
| 5 | 계약 2.6 `domain-purity` → `source_modules` | `game.domain` |
| 6 | 계약 3 `hub-isolation` → `forbidden_modules` | `game` |

### 7-2. 도메인 순수성이 강제하는 것

계약 2.5·2.6에 따라 `game.domain`은 fastapi·sqlalchemy·ollama·langchain·neo4j·**pydantic**을
전부 import할 수 없다.

⇒ **가격 엔진·매출 산식·적합도 계산·손님 샘플러는 전부 순수 파이썬**이다.
전부 CPU-bound이므로 `async def`가 아니라 **`def`**로 쓴다(minseok CLAUDE의 async 규칙).
무거워지면 호출 측에서 `asyncio.to_thread`로 분리한다.

### 7-3. 라우터 컨벤션

새 라우터마다 `GET /game/myself` 자기소개 + 프랙탈 8파일. 표본은 `apps/stock`의 `analyst` 슬라이스
(`analyst_router.py` / `analyst_schema.py` / `analyst_dto.py` / `analyst_use_case.py` /
`analyst_record_port.py` / `analyst_interactor.py` / `log_analyst_record_adapter.py` /
`analyst_provider.py` + 테스트).

자기소개는 **배역·은유가 아니라 실제 기능**을 적는다. game의 경우 반드시 포함할 것:
*"주가는 실제 시세가 아니라 서버가 생성한 가상값입니다"* · *"실제 매매를 실행하지 않습니다"* ·
*"임대료·인건비는 실데이터가 없어 게임 규칙으로 산정한 가정치입니다"*.

### 7-4. 합성 루트

`minseok/main.py`에 라우터 import + `include_router(..., dependencies=_authenticated)`.
허브 포트를 추가하면 `app.dependency_overrides` 줄이 하나 더 붙는다(현재 23줄).
game 라우터는 **공개 화이트리스트에 넣지 않는다** — 전부 JWT 필수다.

---

## 8. 검증 명령

호스트에 파이썬 개발환경이 없어 테스트·린트는 전부 도커 경유다.
MCP 도구로도 노출돼 있다: `run_backend_tests` · `run_import_linter` · `run_tsc`.

```bash
# ── 결정론·경계 회귀 (AST 검사 — 아래 "왜 grep이 아닌가" 참고) ────
cd minseok && PYTHONPATH=apps python3 scripts/check_game_determinism.py

# ── 구조 계약 5종 ─────────────────────────────────────────────────
cd minseok && PYTHONPATH=apps lint-imports --config .importlinter

# ── 테스트 ────────────────────────────────────────────────────────
cd minseok && PYTHONPATH=apps python3 -m pytest apps/game -q -p no:cacheprovider

# ── 프론트 (2단계 이후) ───────────────────────────────────────────
grep -rn "Math.random" www/components/game www/app    # 0줄 — 프론트는 가격을 만들지 않는다
cd www && npx tsc --noEmit
```

> **이 맥에는 파이썬 개발환경이 있다**(2026-07-31 실측: Python 3.11.15 · pytest 9.1.1 ·
> pytest-asyncio 1.4.0 · import-linter). 반면 **도커는 없다.** 루트 CLAUDE.md의
> "호스트에 파이썬 개발 환경이 없다 · 검증은 전부 도커 경유"는 백엔드 PC 기준이다.
> game 앱은 도메인이 순수 파이썬이고 DB·프레임워크에 의존하지 않아 **맥에서 그대로 검증된다.**
> 백엔드 PC에서는 위 명령을 도커로 감싼다(루트 CLAUDE.md 참고).

**아직 코드가 없어 지금은 비어 있는 검사** — 해당 단계에서 위 스크립트에 규칙을 추가한다.

| 검사 | 도입 단계 |
|---|---|
| 계수 리터럴이 `rule_coefficients.py` 밖에 있는가 | 6단계 |
| 금액 DTO 필드에 `observed_`/`assumed_`/`simulated_` 접두사가 붙었는가 | 6단계 |
| `get_market_db`·`MARKET_DATABASE_URL` 접근 | 5단계(현재는 import 검사가 이미 막는다) |

### 8-0. 왜 grep이 아니라 AST인가

원래 이 절은 grep 목록이었다. **1단계에서 실행해보니 오탐률이 100%였다** — 위반 3건이 전부
docstring이었다.

| grep 결과 | 실제 |
|---|---|
| `datetime.now\|utcnow` → 3파일 | 실제 호출 1줄. 나머지 2개는 *"현재 시각은 여기서 읽지 않는다"*는 설명 |
| `hash(` → 2줄 | 둘 다 *"내장 hash()를 쓰지 않는다"*는 설명 |
| `price_bars` → 1줄 | 캘리브레이션 출처를 밝히는 주석 |

결정론 규칙을 설명하는 문서에는 금지어가 필연적으로 등장한다. **오탐이 나는 검증은 결국
아무도 보지 않으므로** `scripts/check_game_determinism.py`가 AST로 실제 코드만 본다
(주석·docstring·문자열은 구조상 걸리지 않는다). 검사기 자체도 위반을 주입해 탐지되는지
양방향으로 확인했다.

### 8-1. 재현성 테스트 3종 (필수)

**이게 없으면 §1의 결정론 규칙은 문서상의 주장일 뿐이다.**

| # | 테스트 | 무엇을 잡는가 |
|---|---|---|
| ① 반복 | `price_at(sym, t)` 100회 호출 → 전부 동일 | 숨은 난수·시각 의존 |
| ② **호출 순서 무관** | `t`를 오름차순·역순·무작위 순서로 물어도 같은 값 | 전역 상태·누적 캐시 의존 |
| ③ **프로세스 경계 무관** | `PYTHONHASHSEED`가 다른 서브프로세스의 계산값과 일치 | 내장 `hash()` 혼입(가장 조용한 실패) |

### 8-2. 분포 회귀 테스트

"조용히 잘못된 값"을 잡는다 — 예측 스냅샷이 **전량 NEUTRAL**이었던 것을 오래 몰랐던 선례
(커밋 `a382df4`)와 같은 유형이다. 90게임일 시뮬 후 확인한다.

- [ ] 종목별 수익률 **분산 > 0** (전 종목이 같은 값이 아니다)
- [ ] 적합도(fitness)가 **한 값에 몰리지 않는다** (전 상권 동일 점수가 아니다)
- [ ] 손님 4축(요일·시간대·성별·연령)이 **전부 최빈값만 나오지 않는다**

---

## 9. 범위 밖 — 하지 않는다

| 항목 | 사유 |
|---|---|
| game 전용 DB | §4 판정. 6세트 비용 + 유저 FK 단절. soccer 선례 |
| cron 신설·인프로세스 스케줄러 | 결정론 설계의 존재 이유. **cron 목표 개수 0** |
| WebSocket·SSE | 저장소 WS 0건. 결정론이라 폴링 간격이 정확도에 영향을 주지 않는다 |
| LLM 이벤트·대사 생성 | 결정론 위반 + 추론 비용. 템플릿 룩업만 |
| **임의 좌표 창업** | `MapView.tsx`는 주어진 마커 선택만 지원한다. **1,650 상권 핀 선택으로 한정**한다. 임의 좌표를 받으려면 지도 신규 개발 + 좌표→상권 매핑이 선행인데, **상권 폴리곤 데이터가 없다**(중심점 + 면적값뿐, PostGIS 미사용) |
| 상권 경계 폴리곤 표시 | 데이터에 없다 |
| 레버리지·강제청산 | 오프라인 진행과 최악의 궁합. 근거 → game-strategy §3-2 |
| 랭킹·리더보드·PvP·길드 | 공용 시장이라 자연스러워 보이지만 조작 유인과 감사 부담이 붙는다. 수요 확인 후 재검토 |
| game 전용 어드민 페이지 | admin 6페이지 전면 구현은 ROADMAP 과설계 목록 |
| 전국 확장 | 상권 실데이터가 **서울만**이다(적재 스크립트에 `SIDO_SEOUL = "11"` 하드코딩) |

---

## 10. 프론트 배치 — `/game` 독립 라우트 (2026-07-31 확정)

게임은 **URL `/game`의 독립 페이지**이고 상단 내비게이션에 **게임 탭이 새로 생긴다**(사용자 확정).

| 항목 | 결정 | 근거 · 2단계 실측 |
|---|---|---|
| URL | **`/game`** | 신규 탭 페이지 |
| 파일 위치 | **`www/app/(seoul)/game/page.tsx`** | Next.js route group은 URL에 나타나지 않는다 — `(seoul)/market/page.tsx`가 `/market`인 것과 같다. **`layout.tsx`는 없다**(아래 `TabGuard` 항목) |
| `WorkspaceShell` 3패널 | **쓰지 않는다** | 게임은 자료\|스테이지\|채팅 구조가 아니다. 채팅 패널이 붙을 자리가 없다 |
| `TabGuard` | **쓰지 않는다** | `TabKey` 타입을 요구하는데 game은 `TAB_KEYS`에 없다(§10-1). 게이팅할 것이 없으면 가드도 없다 |
| 차트 | **SVG 폴리라인**(`components/game/GamePriceLine.tsx`) | lightweight-charts는 캔들·거래량·지표용이다. 게임 시세는 틱 단위 종가 하나뿐이고 종목 12개에 인스턴스 12개를 만들 이유가 없다. 한 컴포넌트가 큰 차트와 스파크라인을 겸한다 |
| `MapView` | **재사용한다** | 상권 창업의 입지 선택(7단계). 단 마커 선택만 — 임의 좌표는 §9 범위 밖 |
| 실시간 갱신 | **폴링만** — 30초, 에러 시 5분 저속 | WS·SSE는 §2 금지. 결정론이라 같은 틱을 다시 물어도 같은 값이다 |
| 상태 | `useState` **1개**(선택 종목) | 나머지는 서버 응답이라 상태로 들 것이 없다(`REACT_RULES`) |
| 접근 권한 | **전 유저 공개.** 등급(RBAC) 제한 없음 | 사용자 확정(2026-07-31). 단 **로그인은 필수** — 지갑이 `users.id` FK다. 401이면 로그인 유도 카드 |
| `TAB_KEYS` 편입 | ⛔ **넣지 않는다** | 아래 |

### 10-1. `TAB_KEYS`에 `game`을 넣지 않는 이유

`hub/domain/navigation/tab_ontology.py`의 `TAB_KEYS`는 "**등급 게이팅 대상** 상단 탭의 공유
어휘"다. 전 유저 공개라면 게이팅할 것이 없으므로 키가 필요 없다.

**같은 선례가 이미 있다** — 그 파일 주석: *"새로 물어보기(`/`)는 게이팅 대상이 아니라 키가 없다."*
즉 **게이팅하지 않는 화면은 키를 만들지 않는 것**이 이 저장소의 확립된 컨벤션이다.

| 후보 | 판정 | 근거 |
|---|---|---|
| **미편입(전체 공개 고정)** | ✅ **채택** | 게이팅 장치를 만들지 않는다. `/` 선례와 동일 |
| 편입 + 전 등급에 `game` 부여 | ⛔ | 결과는 같은데 **운영 부담만 는다** — 등급을 새로 만들 때마다 `game` 체크를 기억해야 하고, 빠뜨리면 그 등급 유저에게 탭이 조용히 사라진다 |

⚠️ **"전 유저 공개"는 "비로그인 공개"가 아니다.** 지갑·포지션·가게가 전부 `users.id` FK이므로
**로그인은 구조상 필수**다(§7-4 — game 라우터는 공개 화이트리스트에 넣지 않는다).
등급 제한만 없다는 뜻이다.

> 나중에 제한이 필요해지면 그때 편입한다 — `TAB_KEYS`에 한 줄 + `role_tabs` 부여로 끝난다.
> **미리 편입해두지 않는다**(스켈레톤 금지 원칙과 같은 결).

---

## 11. 미해결 — 착수 전 확인할 것

- **동시 운영 가게 수 상한.** 제안: 1분기 1개 → 2호점은 `facility_score ≥ 300` + 흑자 2분기 연속.
- **게임에 쓸 종목 수.** 제안 12~16(68 전부는 화면·밸런스가 감당 못 한다). 확정은 game-strategy §3-1.
- **`GAME_EPOCH_START_UTC` 실값.** 1단계 착수일에 정하고 그 뒤 불변이다.
- **시즌 종료 후 기록 보관 방식.** `epoch_id`로 동결한 행을 그대로 두는가, 별도 요약 테이블로
  압축하는가? 8시즌이 지나면 `game_ledger`가 커진다.
