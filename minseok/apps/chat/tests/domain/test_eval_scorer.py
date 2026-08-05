"""eval_scorer 단위 테스트 — 손으로 만든 트레이스로 지표별 채점 로직을 검증한다."""
from __future__ import annotations

from chat.domain.services.eval_scorer import score
from chat.domain.value_objects.eval_trace import CaseTrace, EvalCase, LlmCall


def _case(case_id="C1", category="market_region", prompt="성수동 카페 어때?",
          expected_intent="market", **kw) -> EvalCase:
    return EvalCase(case_id=case_id, category=category, prompt=prompt,
                    expected_intent=expected_intent, **kw)


def _trace(case_id="C1", final_intent="market", stock_query="", answer_text="답변",
           **kw) -> CaseTrace:
    return CaseTrace(case_id=case_id, final_intent=final_intent,
                     stock_query=stock_query, answer_text=answer_text, **kw)


def _phase0(response='{"intent": "market", "stock_query": ""}') -> LlmCall:
    return LlmCall(phase="phase0", prompt="의도", response=response, latency_ms=100.0)


# --- 의도 분류 ---

def test_의도_정확도와_혼동행렬():
    cases = [_case("C1", expected_intent="market"),
             _case("C2", category="general", prompt="안녕", expected_intent="general")]
    traces = [_trace("C1", final_intent="market"),
              _trace("C2", final_intent="market")]  # general → market 오분류
    report = score(cases, traces)
    assert report.intent_accuracy == 0.5
    assert report.intent_confusion["general"]["market"] == 1


def test_트레이스_없는_케이스는_오류로_집계():
    report = score([_case("C1"), _case("C2", prompt="홍대?")], [_trace("C1")])
    assert report.errored == ("C2",)
    assert report.intent_accuracy == 1.0  # 채점은 정상 트레이스만


# --- 종목 질의 추출 ---

def test_종목_질의는_허용_목록_대소문자_무시_대조():
    cases = [_case("C1", category="stock_us", prompt="테슬라 어때?",
                   expected_intent="stock", accepted_queries=("TSLA",)),
             _case("C2", category="stock_kr", prompt="삼전 어때?",
                   expected_intent="stock", accepted_queries=("삼성전자",))]
    traces = [_trace("C1", final_intent="stock", stock_query="tsla"),
              _trace("C2", final_intent="market_news", stock_query="")]  # 추출 실패
    report = score(cases, traces)
    assert report.stock_query_accuracy == 0.5


# --- phase0 파싱 실패 ---

def test_phase0_파싱_실패율():
    cases = [_case("C1"), _case("C2", prompt="홍대?")]
    traces = [_trace("C1", calls=(_phase0(),)),
              _trace("C2", calls=(_phase0(response="JSON 아님"),))]
    report = score(cases, traces)
    assert report.phase0_parse_failure_rate == 0.5


# --- 결정론 가드 ---

def test_서울외_가드는_phase1_미호출과_준비중_안내를_요구():
    cases = [_case("C1", category="market_nonseoul", prompt="부산 서면 어때?",
                   region="부산"),
             _case("C2", category="market_nonseoul", prompt="수원 카페?", region="수원")]
    ok = _trace("C1", answer_text="지금은 서울 상권 데이터만… 준비 중이라…")
    leaked = _trace("C2", answer_text="수원 추천!", calls=(
        LlmCall(phase="phase1", prompt="p", response="{}", latency_ms=1.0),))
    report = score(cases, [ok, leaked])
    assert report.nonseoul_guard_rate == 0.5


def test_phase1_가드_발동은_원답과_최종_추천_차이로_판정():
    cases = [_case("C1"), _case("C2", prompt="홍대?")]
    p1 = LlmCall(phase="phase1", prompt="p", response="{}", latency_ms=1.0)
    fired = _trace("C1", calls=(p1,), phase1_raw_codes=(1, 2),
                   recommendation_codes=(3,), recommendation_labels=("성수동2가|성동구|성수동",))
    silent = _trace("C2", calls=(p1,), phase1_raw_codes=(1, 2),
                    recommendation_codes=(1, 2), recommendation_labels=("홍대|마포구|서교동",))
    report = score(cases, [fired, silent])
    assert report.phase1_guard_activation_rate == 0.5


# --- 지역 적중·멀티턴 승계 ---

def test_지역_적중은_추천_라벨의_어간_포함으로_판정():
    cases = [_case("C1", region="성수동"), _case("C2", prompt="홍대?", region="홍대")]
    hit = _trace("C1", recommendation_codes=(1,),
                 recommendation_labels=("성수동2가|성동구|성수2가1동",))
    miss = _trace("C2", recommendation_codes=(2,),
                  recommendation_labels=("강남역|강남구|역삼1동",))
    report = score(cases, [hit, miss])
    assert report.region_hit_rate == 0.5


def test_멀티턴_승계는_시딩_코드의_부분집합이어야_성공():
    cases = [_case("C1", category="multiturn", prompt="거기 어때?",
                   history_regions=("성수동",)),
             _case("C2", category="multiturn", prompt="그 중엔?", history_regions=("홍대",))]
    ok = _trace("C1", recommendation_codes=(1,), seeded_history_codes=(1, 2))
    drifted = _trace("C2", recommendation_codes=(9,), seeded_history_codes=(1, 2))
    report = score(cases, [ok, drifted])
    assert report.inherit_success_rate == 0.5


# --- 절대 규칙 ---

def test_환각_숫자_판정():
    gen = LlmCall(phase="phase2", prompt="컨텍스트: 월매출 4,500만원, 점포 32개",
                  response="{}", latency_ms=1.0)
    cases = [_case("C1")]
    traces = [_trace("C1", answer_text="월매출 4500만원에 점포 32개, 유동인구 78000명입니다",
                     calls=(gen,), recommendation_codes=(1,),
                     recommendation_labels=("성수동2가|성동구|성수동",))]
    report = score(cases, traces)
    halluc = [v for v in report.violations if v.rule == "hallucinated_number"]
    assert [v.detail for v in halluc] == ["78000"]  # 4500·32는 컨텍스트에 있어 무혐의


def test_금지_표현과_고지_누락은_stock_답변에서_잡는다():
    cases = [_case("C1", category="stock_kr", prompt="삼성전자 어때?",
                   expected_intent="stock", accepted_queries=("삼성전자",))]
    traces = [_trace("C1", final_intent="stock", stock_query="삼성전자",
                     answer_text="무조건 매수하세요.")]
    report = score(cases, traces)
    rules = sorted(v.rule for v in report.violations)
    assert "forbidden_phrase" in rules
    assert "missing_disclaimer" in rules


def test_잘린_답변은_잘림으로_세고_고지_누락으로_겹쳐_세지_않는다():
    cases = [_case("C1", category="stock_kr", prompt="삼성전자 어때?",
                   expected_intent="stock", accepted_queries=("삼성전자",))]
    traces = [_trace("C1", final_intent="stock", stock_query="삼성전자",
                     answer_text="변동성은 낮은 편이고 거래량도 평소 수준이며,")]
    report = score(cases, traces)
    rules = sorted(v.rule for v in report.violations)
    assert "truncated_answer" in rules
    # 끊긴 뒤에 올 고지를 "없다"고 셀 수는 없다 — 같은 결함을 두 번 세지 않는다
    assert "missing_disclaimer" not in rules


def test_마크다운_강조로_끝나도_잘림이_아니다():
    cases = [_case("C1", category="stock_kr", prompt="삼성전자 어때?",
                   expected_intent="stock", accepted_queries=("삼성전자",))]
    traces = [_trace("C1", final_intent="stock", stock_query="삼성전자",
                     answer_text="**투자 판단은 본인 책임입니다.**")]
    report = score(cases, traces)
    assert [v.rule for v in report.violations] == []


def test_고지가_있고_금지_표현이_없으면_위반_없음():
    cases = [_case("C1", category="stock_kr", prompt="삼성전자 어때?",
                   expected_intent="stock", accepted_queries=("삼성전자",))]
    traces = [_trace("C1", final_intent="stock", stock_query="삼성전자",
                     answer_text="지표상 중립입니다. 투자 판단의 책임은 본인에게 있습니다.")]
    assert score(cases, traces).violations == ()


def test_입지_창작은_market_추천_답변에서_잡는다():
    cases = [_case("C1")]
    traces = [_trace("C1", recommendation_codes=(1,),
                     recommendation_labels=("성수동2가|성동구|성수동",),
                     recommendation_reasons=("5,8호선 환승역이라 좋아요",))]
    report = score(cases, traces)
    assert any(v.rule == "location_claim" for v in report.violations)


# --- 지연 ---

def test_지연_백분위는_phase별로_집계():
    calls = tuple(LlmCall(phase="phase0", prompt="p", response="{}",
                          latency_ms=float(ms)) for ms in (100, 200, 300, 400))
    report = score([_case("C1")], [_trace("C1", calls=calls)])
    assert report.latency_p50_ms["phase0"] == 200.0
    assert report.latency_p95_ms["phase0"] == 400.0
