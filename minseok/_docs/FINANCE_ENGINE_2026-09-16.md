# 창업 재무 엔진 — 비용·손익 축 (2026-09-16)

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]] · 상권 → [[minseok/apps/market/_docs/CLAUDE|market CLAUDE]] · 대화 → [[minseok/apps/chat/_docs/CLAUDE|chat CLAUDE]]
로드맵 → [[minseok/_docs/ROADMAP|ROADMAP]] B4(창업비용·손익분기 서술) 완성. 상태: **구현·배포·검증 완료(2026-09-16)**.

"성수동에 카페, 내 돈 1억이면 몇 개월 버티고 얼마가 모자라나"를 대화에서 답한다.
계산은 결정론 코드, LLM은 해석만. 원천은 전부 서울.

---

## 새로 만드는 기능

### 1. 상권 임대료·공실률 데이터 (R-ONE)

- 한국부동산원 R-ONE 소규모 상가 임대료(천원/㎡)·공실률(%)을 분기 단위로 적재한다.
  표 `T248223134698125`(임대료)·`T241833134686576`(공실률), 2024Q3~2026Q2 8분기.
  서울은 `서울`(1) + 권역(4: 도심·강남·영등포신촌·기타) + 상권(59) = 64 분류.
- 테이블 `rent_benchmarks`(market 전용 DB): `building_type · year_quarter · cls_id · cls_fullnm · level(0/1/2) · region_name · rent_per_sqm_krw · vacancy_rate`, UNIQUE(building_type, year_quarter, cls_id).
- 수집 `scripts/collect_rone_rent.py`, 분기 1회 cron. upsert 멱등. 옛 빈티지(2024Q2 이전) 미적재.
- 상권 매칭 `domain/services/rent_matcher.py`: ① R-ONE 상권 59개 ↔ `trade_area` 이름 어간 사전 → ② 자치구 → 권역 폴백 → ③ 서울 전체. 결과에 `rent_source: area|zone|city`를 남긴다.
- 월세 환산: 면적 미입력 시 33㎡(10평) 가정.

### 2. 금리 데이터 (ECOS)

- 한국은행 기준금리 `722Y001`, 예금은행 대출금리 `121Y006`(대출평균) 월 단위 적재.
- 테이블 `interest_rates`(market 전용 DB): `stat_code · item_name · year_month · rate`, UNIQUE(stat_code, item_name, year_month).
- 수집 `scripts/collect_ecos_rates.py`, 월 1회 cron, 최근 3개월 재수집 멱등.

### 3. 원가율 벤치마크 (코드 상수)

- `domain/services/cost_benchmarks.py`: 업종군 7개(food·cafe_beverage·pub·retail·beauty_service·education·other)별 `cost_ratio`(재료비율)·`margin_ratio`(영업이익률)·출처(소상공인실태조사, 연도).
- 서울 업종명 → 업종군 매핑 `_COST_GROUP_BY_SERVICE`.
- 인건비: 미입력 = 1인 운영(0). 입력 시 `최저임금(2026) × 209h × 인원`.

### 4. 재무 계산 엔진 (`domain/services/finance_engine.py`, 순수)

입력 값마다 출처 태그(`input · history · profile · area_avg · franchise · assumed · ecos`)를 붙인다.

```
capex           = startup_cost + deposit + key_money
opex_base       = monthly_rent + monthly_payroll
funding_gap     = max(0, capex + opex_base × 3 − equity)      # 이자 전에 확정
loan            = max(desired_loan, funding_gap)
loan_interest   = loan × loan_rate / 12                        # 이자만
fixed_monthly   = opex_base + loan_interest
bep_sales       = fixed_monthly / (1 − cost_ratio)
attainment      = expected_sales / bep_sales                   # 점포당 월매출 없으면 None
monthly_profit  = expected_sales × (1 − cost_ratio) − fixed_monthly
cash_after      = max(0, equity + loan − capex)
runway_months   = cash_after / |monthly_profit|  (적자일 때만, 흑자면 None)
stress          = loan_rate +1%p / +2%p 재계산
scenarios       = expected_sales × 0.8 / 1.0 / 1.2
```

기본 가정(전부 `assumptions`로 반환): 보증금 = 월세 10개월분 · 권리금 0 · 면적 10평 · 운전자금 3개월 · 1인 운영.
침묵: 점포 5개 미만·매출 0이면 달성률·runway·시나리오 생략(BEP·gap은 냄).

### 5. 상권 재무 계산 API — market `area_finance` 슬라이스 + hub `AreaFinancePort`

| 계층 | 파일 |
|---|---|
| 라우터 | `area_finance_router.py` — `GET /market/trdar/{code}/finance?service_code&equity&deposit?&monthly_rent?&area_sqm?&headcount?&desired_loan?&key_money?`. `/myself`는 두지 않는다(market 조회 라우터는 전부 `prefix="/market"`이라 cartographer의 자기소개 하나뿐 — `tests/test_public_routes.py`가 고정) |
| 스키마·DTO·입력포트·인터랙터·프로바이더 | `area_finance_*` 1:1 |
| 출력 포트·리포지토리 | `area_finance_repository.py` — `find_rent(trdar_code)` · `find_loan_rate()`. 점포당 매출·창업비용은 기존 `AreaDetailRepositoryPort` 재사용 |
| 첫 줄 문장 | `domain/services/finance_narrator.py` — chat·라우터 공용 |
| 허브 | `hub/app/ports/output/area_finance_port.py` ← `market/adapter/outbound/gateways/area_finance_gateway.py`, `main.py` 주입 |
| 마이그레이션 | market 체인 1개(`rent_benchmarks` + `interest_rates`) |

### 6. 채팅 재무 질문 경로 (chat)

- **트리거**: `market` 의도 + 재무 어휘(`자기자본|자본금|내 돈|보증금|월세|임대료|대출|버틸|손익|적자|흑자`) 또는 라벨 금액 2개 이상. 상권·업종이 정해진 뒤에만.
- **라벨 금액 파서** `chat/domain/services/amount_parser.py`(기존 `parse_budget_krw` 이동·확장, 결정론):
  `자기자본|자본금|내 돈→equity · 보증금→deposit · 월세|임대료→monthly_rent(만원 단위) · 권리금→key_money · 인테리어|설비→startup_cost · 대출→desired_loan · 평|㎡→area_sqm · 직원|알바 N명→headcount`. LLM 추출 안 씀.
- **폴백 순서**: 입력 → 이력(직전 finance 카드 승계) → 프로파일(equity만: 예산 밴드 중앙값 2천/4천/7,500만/2억/3억) → 상권 평균·공정위·가정 → equity가 끝내 없을 때만 되묻기.
- **첫 줄은 코드**: `자기자본 1억(입력)·월세 320만(성수 상권 평균, 10평 가정)·창업비용 8,200만(공정위 커피 중앙값) → 손익분기 월매출 A, 점포당 월매출 B(달성률 C%), 부족 자금 D, 적자 시 N개월, 금리 +1%p면 …`. 그 뒤 LLM 해석(리스크·대안).
- **프롬프트 규칙**: 숫자 재계산 금지 · 병기 값 외 금액 생성 금지 · 대출 권유 금지 · 가정 목록 전달.
- **카드 payload `finance`**(inputs+sources+plan): 히스토리 복원·다음 턴 승계 키.

## 개선하는 기능

| 기존 | 어떻게 바뀌나 |
|---|---|
| 회수기간 서술(B8) — 창업비용 ÷ 점포당 매출, 임대료·인건비 없음 | 임대료·인건비·이자를 넣은 손익분기·runway·부족 자금으로 확장. B8 문장은 유지 |
| 예산 질문(`_budget_notice`) — 단독 금액 하나만 읽음 | 라벨 금액(보증금·월세·대출·면적·인원)까지 읽는다. 예산만 있는 질문은 무손상 |
| 프로파일 예산 밴드(M6.5) — 서술 관점 조정에만 사용 | 자기자본 미입력 시 계산 입력으로 쓴다(밴드 중앙값, 출처 병기) |
| 멀티턴 승계 — 상권·업종·예산 | 재무 입력값도 승계. "월세 250이면?"이 재계산 |
| 미지원 축 응답(I-12) — "임대료 데이터 없음" | 임대료가 생기므로 미지원 목록에서 제거. "상권 단위가 아니라 권역 평균"임을 병기 |
| 상권 상세 비용 축 — 매매 평단가만 | 임대료·공실률 **팩트 적재까지**(`rent_benchmarks.vacancy_rate` 포함). 응답·서술 노출은 후속 슬라이스 |

## 하지 않는 것

- 프론트 카드(payload만 넣음) · 지원사업·보증 연결(후속 ③) · 은행 대출상품 추천 · 원리금 상환·세금·4대보험 · 업종 교차 매핑 테이블 · R-ONE 옛 빈티지·중대형/집합 상가 · 지역 어댑터(대구)

## 검증

| # | 항목 | 기준 |
|---|---|---|
| G1 | 엔진 단위테스트 | ≥12: BEP·달성률·gap 하한 0·흑자 runway None·스트레스 단조·출처 태그 보존·소표본 침묵·시나리오·가정 목록 |
| G2 | 파서 | 표기 20종 |
| G3 | 인터랙터 스텁 | 임대료 상권/권역/서울 3경로 + 매출 소표본 + 창업비용 없음 |
| G4 | chat 골든셋 +10 | 입력 ≤3으로 첫 답 · 출처 전부 병기 · 프로파일로 자기자본 대체 · 없으면 자기자본만 되묻기 · 재계산 · 대출 권유 0 · 환각 0 |
| G5 | R-ONE 실적재 | 64 CLS × 8분기, 상권 직접 매칭률 기록, 나머지 권역 폴백 — (2026-09-16 실적재: small level0 8·level1 32·level2 472행, medium_large level2 544행, aggregate level2 320행. **상권 직접 매칭률 실측(2026-09-16, 백엔드 PC 실 DB): 1,650곳 중 333곳 20.2%가 R-ONE 상권 직접 매칭, 나머지 79.8%는 권역 폴백.** 어간만으로는 삼육보건대→건대입구 등 8건이 오매칭돼 자치구 게이트(`RONE_AREA_DISTRICTS`)를 넣어 제거(커밋 96fceaf)) |
| G6 | ECOS 실적재 | 최신월 기준금리·대출평균 — (2026-09-16 실적재: 722Y001 최신 202608, 121Y006 최신 202607 — 한은 공표 지연으로 실행월 전전월) |
| G7 | 구조 | lint-imports 5 KEPT · pytest 전체 · 라우트 표 diff(+1: `/market/trdar/{code}/finance`, 인증 필수) — (2026-09-16 Task 11 실행: pytest `minseok/apps minseok/tests -m "not ollama and not network"` **1193 passed, 7 deselected**, 실패 0 · lint-imports **5 kept, 0 broken** · 라우트 표 diff는 `test_public_routes.py`에 포함돼 통과에 반영됨) |

**배포 체크리스트**: ① `infra/k8s/load-image.sh`로 이미지 재빌드(cron 스크립트는 이미지 `/app`에 들어간다)
② `alembic -c apps/market/alembic.ini upgrade head` 수동 실행 ③ `/market/trdar/{code}/finance` curl 1회
④ `collect_rone_rent.py --dry-run`·`collect_ecos_rates.py --dry-run`.

**백엔드 PC 실행 기록(2026-09-16)**:
- ✅ 배포 체크리스트 ①~④ 완료 — `deploy.sh`(커밋 6155110) → market 체인 수동 마이그레이션(`f5a6b7c8d9e0`) → cron 수동 실행으로 R-ONE 1,456행·ECOS 186행(2020-01~) 적재 → 실 DB 인터랙터 호출(성수동카페거리=뚝섬 상권 직접, 인사동=도심 권역 폴백, 금리 2026-07 4.27%).
- ✅ R-ONE 상권 직접 매칭률 20.2%(G5) — 오매칭 8건은 자치구 게이트로 제거(96fceaf).
- ✅ 골든셋 러너 재박제(2026-09-16 22:40, 백엔드 PC, 27분) — 144문항 오류 0 · intent_accuracy 1.000 · region_hit 1.0 · inherit 1.0 · citation_coverage 0.987 · **finance_answer_rate 1.0(MF01~10 전부 정답, MF09 되묻기 포함)** · 환각 숫자 0 · 잘림 0 · 절대 규칙 위반 0(loan_solicitation 0). `baseline.json`에 `finance_answer_rate: 1.0` 추가(관측 최소값 정책).

## 선행·구현 순서

- 키: `RONE_API_KEY`·`ECOS_API_KEY` 등록·실호출 완료(2026-09-16). `.env.example`·`core/config.py` 상수는 구현에 포함.
- 확정(2026-09-16 실호출): R-ONE 서울 상권 59개 — 도심 11(광화문·남대문·동대문·명동·방산시장·북촌·서촌·시청·을지로·종로·충무로) · 강남 9(강남대로·교대역·남부터미널·논현역·도산대로·신사역·압구정·청담·테헤란로) · 영등포신촌 7(공덕역·당산역·동교/연남·망원역·신촌/이대·영등포역·홍대/합정) · 기타 32. 권역↔자치구는 상권 소속으로 확정: 도심=종로·중구, 강남=강남·서초, 영등포신촌=영등포·마포·서대문, 나머지=기타.
- 2026 최저임금 시급 10,320원(2025-07 고시). 원가율은 잠정 상수로 시작하고 소상공인실태조사 최신 표 대조 뒤 교체(출처 문자열에 "잠정" 표기).
- 순서: ① 마이그레이션·수집·실적재 → ② 도메인 서비스 4종 + 테스트 → ③ `area_finance` 슬라이스·허브 포트 → ④ chat 파서·폴백·첫 줄·승계·골든셋 → ⑤ 문서(market·chat CLAUDE, ROADMAP B4)
