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


def test_멀티턴은_승계율과_집중률을_따로_잰다():
    # 첫 baseline 실측: 부분집합 단일 기준은 "이어받고 이웃 추가" 케이스를 실패로 세어 0%.
    cases = [_case("C1", category="multiturn", prompt="거기 어때?",
                   history_regions=("성수동",)),
             _case("C2", category="multiturn", prompt="그 중엔?", history_regions=("홍대",)),
             _case("C3", category="multiturn", prompt="아까 그곳?", history_regions=("잠실",))]
    focused = _trace("C1", recommendation_codes=(1,), seeded_history_codes=(1, 2))
    diluted = _trace("C2", recommendation_codes=(1, 9), seeded_history_codes=(1, 2))  # 승계+이웃 추가
    drifted = _trace("C3", recommendation_codes=(9,), seeded_history_codes=(1, 2))
    report = score(cases, [focused, diluted, drifted])
    assert report.inherit_rate == 2 / 3        # focused·diluted — 하나라도 이어받음
    assert report.inherit_focus_rate == 1 / 3  # focused만 — 그것만으로 답함


# --- 서술 골격 준수율 ---

def test_거래량_판정_포함률은_stock_답변에서_잰다():
    cases = [_case("C1", category="stock_kr", prompt="삼성전자 어때?",
                   expected_intent="stock", accepted_queries=("삼성전자",)),
             _case("C2", category="stock_kr", prompt="카카오 어때?",
                   expected_intent="stock", accepted_queries=("카카오",))]
    with_verdict = _trace("C1", final_intent="stock", stock_query="삼성전자",
                          answer_text="상승 추세에 거래량이 동반돼 신뢰가 실립니다."
                                      " 투자 판단은 본인 책임입니다.")
    without = _trace("C2", final_intent="stock", stock_query="카카오",
                     answer_text="중립 흐름입니다. 투자 판단은 본인 책임입니다.")
    report = score(cases, [with_verdict, without])
    assert report.volume_verdict_rate == 0.5


def test_리스크_문장_포함률은_모든_추천_이유에_유의가_있어야_성공():
    cases = [_case("C1"), _case("C2", prompt="홍대?")]
    all_marked = _trace("C1", recommendation_codes=(1, 2),
                        recommendation_labels=("a|b|c", "d|e|f"),
                        recommendation_reasons=("좋아요. 유의할 점: 폐업률.",
                                                "좋아요. 유의할 점: 경쟁."))
    partial = _trace("C2", recommendation_codes=(1, 2),
                     recommendation_labels=("a|b|c", "d|e|f"),
                     recommendation_reasons=("유의할 점: 경쟁.", "좋기만 해요."))
    report = score(cases, [all_marked, partial])
    assert report.risk_mention_rate == 0.5


def test_이유가_빈_결정론_비교_카드는_리스크_문장_모수에서_뺀다():
    cases = [_case("C1"), _case("C2", prompt="성수랑 연남 비교")]
    marked = _trace("C1", recommendation_codes=(1,), recommendation_labels=("a|b|c",),
                    recommendation_reasons=("좋아요. 유의할 점: 폐업률.",))
    compare_cards = _trace("C2", recommendation_codes=(1, 2), recommendation_labels=("a|b|c", "d|e|f"),
                           recommendation_reasons=("", ""))
    assert score(cases, [marked, compare_cards]).risk_mention_rate == 1.0


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


def test_소수_형식만_다른_숫자는_환각이_아니다():
    # 컨텍스트는 가격을 48,400.00으로 주는데 모델은 48,400으로 되받는다. 소수부를 안 지우면
    # 같은 숫자가 다른 숫자로 잡혀, 2026-08-05 실측에서 63건 중 56건이 이 형식 차이였다.
    gen = LlmCall(phase="stock_answer",
                  prompt="- 거래 밀집 구간: 48,400.00~50,600.00원 / 20일 이동평균: 182.36달러",
                  response="{}", latency_ms=1.0)
    cases = [_case("C1", category="stock_kr", prompt="삼성전자 어때?",
                   expected_intent="stock", accepted_queries=("삼성전자",))]
    traces = [_trace("C1", final_intent="stock", stock_query="삼성전자", calls=(gen,),
                     answer_text="48,400~50,600원 구간입니다. 투자 판단은 본인 책임입니다.")]
    report = score(cases, traces)
    assert [v.rule for v in report.violations] == []


def test_반올림한_숫자는_환각이_아니다():
    # 컨텍스트 182.36달러를 모델이 182달러로 되받는 것(2026-08-05 SU08 실측)은 창작이 아니다.
    gen = LlmCall(phase="stock_answer", prompt="- 20일 이동평균: 182.36달러 / 50일: 175.44달러",
                  response="{}", latency_ms=1.0)
    cases = [_case("C1", category="stock_kr", prompt="삼성전자 어때?",
                   expected_intent="stock", accepted_queries=("삼성전자",))]
    traces = [_trace("C1", final_intent="stock", stock_query="삼성전자", calls=(gen,),
                     answer_text="이동평균선(20일 182달러, 50일 175달러) 근처입니다."
                                 " 투자 판단은 본인 책임입니다.")]
    report = score(cases, traces)
    assert [v for v in report.violations if v.rule == "hallucinated_number"] == []


def test_비율의_퍼센트_환산은_환각이_아니다():
    # 컨텍스트 거래량비 0.9배를 모델이 "90% 수준"으로 되받는 것(2026-08-05 SK13·SK15).
    gen = LlmCall(phase="stock_answer", prompt="- 거래량: 최근 5일이 20일 평균의 0.9배",
                  response="{}", latency_ms=1.0)
    cases = [_case("C1", category="stock_kr", prompt="삼성전자 어때?",
                   expected_intent="stock", accepted_queries=("삼성전자",))]
    traces = [_trace("C1", final_intent="stock", stock_query="삼성전자", calls=(gen,),
                     answer_text="거래량은 평균의 약 90% 수준입니다. 투자 판단은 본인 책임입니다.")]
    report = score(cases, traces)
    assert [v for v in report.violations if v.rule == "hallucinated_number"] == []


def test_만_이상_정수의_백단위_반올림은_환각이_아니다():
    # 컨텍스트 "일평균 96,703명"을 모델이 "96,700명"으로 되받는다(2026-09-03 MR09, 2회 연속).
    # 천 단위로 뭉갠 "97,000"은 여전히 창작으로 본다 — 동치는 백 단위까지만.
    gen = LlmCall(phase="phase2", prompt="- 유동인구: 일평균 96,703명 (분기 총 8,800,000명 ÷ 91일)",
                  response="{}", latency_ms=1.0)
    cases = [_case("C1"), _case("C2")]
    traces = [
        _trace("C1", answer_text="유동인구가 일평균 96,700명으로 많습니다.", calls=(gen,),
               recommendation_codes=(1,), recommendation_labels=("성수동2가|성동구|성수동",)),
        _trace("C2", answer_text="유동인구가 일평균 97,000명으로 많습니다.", calls=(gen,),
               recommendation_codes=(1,), recommendation_labels=("성수동2가|성동구|성수동",)),
    ]
    report = score(cases, traces)
    halluc = [(v.case_id, v.detail) for v in report.violations if v.rule == "hallucinated_number"]
    assert halluc == [("C2", "97000")]


def test_정수의_0은_지우지_않는다():
    # 소수부만 잘라야 한다 — 100의 0을 지우면 1이 되어 엉뚱한 숫자가 무혐의 처리된다.
    gen = LlmCall(phase="phase2", prompt="컨텍스트: 점포 100개", response="{}", latency_ms=1.0)
    cases = [_case("C1")]
    traces = [_trace("C1", answer_text="점포 1000개입니다", calls=(gen,),
                     recommendation_codes=(1,),
                     recommendation_labels=("성수동2가|성동구|성수동",))]
    report = score(cases, traces)
    halluc = [v for v in report.violations if v.rule == "hallucinated_number"]
    assert [v.detail for v in halluc] == ["1000"]


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


# --- 출처 인용 (R4) ---

def _stock_answer_call(prompt: str) -> LlmCall:
    return LlmCall(phase="stock_answer", prompt=prompt, response="r", latency_ms=1.0)


_CITED_PROMPT = (
    "[TSLA 분석 데이터] — 근거 [1] (가격 단위)\n- 현재가: 230.00달러\n"
    "- 근거 [2] 과거 통계: 과거 120건 중 62%가 상승\n"
    "- 관련 뉴스(감성 라벨):\n  - 근거 [5] (2026-08-01 | 호재) 실적 서프라이즈"
)


def test_citation_coverage는_수치_문장_중_마커_비율이다():
    cases = [_case("C1", category="stock_us", prompt="테슬라?",
                   expected_intent="stock", accepted_queries=("TSLA",))]
    # 수치 문장 3개 중 2개에 마커, 고지 문장은 숫자가 없어 표본 제외
    answer = ("현재가는 230달러입니다. [1] 과거 120건 중 62%가 상승했습니다. [2][5] "
              "거래량은 20일 평균 수준입니다. 투자 판단의 책임은 본인에게 있습니다.")
    traces = [_trace("C1", final_intent="stock", stock_query="TSLA", answer_text=answer,
                     calls=(_stock_answer_call(_CITED_PROMPT),))]
    report = score(cases, traces)
    assert report.citation_coverage == 2 / 3
    assert not any(v.rule == "dangling_citation" for v in report.violations)


def test_없는_근거_번호는_dangling_citation_위반이다():
    cases = [_case("C1", category="stock_us", prompt="테슬라?",
                   expected_intent="stock", accepted_queries=("TSLA",))]
    answer = "현재가는 230달러입니다. [7] 투자 판단의 책임은 본인에게 있습니다."
    traces = [_trace("C1", final_intent="stock", stock_query="TSLA", answer_text=answer,
                     calls=(_stock_answer_call(_CITED_PROMPT),))]
    report = score(cases, traces)
    assert [(v.rule, v.detail) for v in report.violations
            if v.rule == "dangling_citation"] == [("dangling_citation", "[7]")]


def test_마커_도입_전_트레이스는_커버리지_표본에서_빠진다():
    cases = [_case("C1", category="stock_us", prompt="테슬라?",
                   expected_intent="stock", accepted_queries=("TSLA",))]
    # 프롬프트에 '근거 [n]' 표기가 없다 — 구 트레이스. 마커 없는 수치 문장이 있어도 표본 아님
    traces = [_trace("C1", final_intent="stock", stock_query="TSLA",
                     answer_text="현재가는 230달러입니다. 투자 판단은 본인 책임입니다.",
                     calls=(_stock_answer_call("[TSLA 분석 데이터]\n- 현재가: 230.00달러"),))]
    report = score(cases, traces)
    assert report.citation_coverage is None
    assert not any(v.rule == "dangling_citation" for v in report.violations)


# --- 지연 ---

def test_지연_백분위는_phase별로_집계():
    calls = tuple(LlmCall(phase="phase0", prompt="p", response="{}",
                          latency_ms=float(ms)) for ms in (100, 200, 300, 400))
    report = score([_case("C1")], [_trace("C1", calls=calls)])
    assert report.latency_p50_ms["phase0"] == 200.0
    assert report.latency_p95_ms["phase0"] == 400.0


# --- 등급 결정론 가드 (grade_caution) ---

_GRADED_PROMPT = (
    "[성수역 / 성동구] (trdar_code: 1000001)\n"
    "- 서울 평균 대비: 종합 44.9점·주의 (50점=서울 평균, 이 상권은 평균 미달)\n"
    "[홍대입구 / 마포구] (trdar_code: 1000002)\n"
    "- 서울 평균 대비: 종합 67.0점·양호 (50점=서울 평균, 이 상권은 평균 상회)\n"
)


def _phase2(prompt=_GRADED_PROMPT) -> LlmCall:
    return LlmCall(phase="phase2", prompt=prompt, response="{}", latency_ms=100.0)


def test_주의_등급_상권의_추천_어휘는_절대_규칙_위반():
    traces = [_trace("C1", answer_text="성수역을 추천합니다",
                     calls=(_phase2(),),
                     recommendation_codes=(1000001, 1000002),
                     recommendation_reasons=("강력히 추천합니다", "추천합니다"))]
    report = score([_case("C1")], traces)
    rules = [v for v in report.violations if v.rule == "grade_caution"]
    # 주의 상권 이유 1건 + 본문 1건 — 양호 상권 이유의 '추천'은 위반이 아니다
    assert len(rules) == 2


def test_등급_가드를_통과한_답변은_위반이_없다():
    traces = [_trace("C1", answer_text="성수역은 '주의' 등급입니다. 검토해볼 만합니다.",
                     calls=(_phase2(),),
                     recommendation_codes=(1000001,),
                     recommendation_reasons=("검토해볼 만합니다. 유의할 점: 경쟁 밀집.",))]
    report = score([_case("C1")], traces)
    assert [v for v in report.violations if v.rule == "grade_caution"] == []


# --- 재무 답변(FINANCE_ENGINE) ---

def test_재무_케이스는_손익분기와_부족자금_또는_되묻기를_답으로_친다():
    cases = [_case("F1", category="market_finance", prompt="성수동 카페 자기자본 1억 월세 300"),
             _case("F2", category="market_finance", prompt="혜화동 카페 월세 200"),
             _case("F3", category="market_finance", prompt="홍대 술집 내 돈 5천")]
    traces = [_trace("F1", answer_text="…손익분기 월매출은 434만원이에요. 부족 자금 1,900만원이 필요해요."),
              _trace("F2", answer_text="※ 자기자본(내 돈)을 알려주시면 손익분기·부족 자금·버틸 기간을 계산해 드려요."),
              _trace("F3", answer_text="이 상권은 유동인구가 많아요.")]
    report = score(cases, traces)
    assert report.finance_answer_rate == 2 / 3


def test_재무_답변의_대출_권유는_절대_규칙_위반():
    cases = [_case("F1", category="market_finance", prompt="성수동 카페 자기자본 1억")]
    traces = [_trace("F1", answer_text="손익분기… 부족 자금 2천만원은 A은행 대출을 추천해요.")]
    report = score(cases, traces)
    assert any(v.rule == "loan_solicitation" for v in report.violations)


def test_자기자본을_말한_질문에_되묻기로_답하면_실패다():
    cases = [_case("F1", category="market_finance", prompt="성수동 카페 자기자본 1억 월세 300"),
             _case("F2", category="market_finance", prompt="홍대 술집 내 돈 5천 월세 250")]
    traces = [_trace("F1", answer_text="※ 자기자본(내 돈)을 알려주시면 손익분기·부족 자금·버틸 기간을 계산해 드려요."),
              _trace("F2", answer_text="※ 자기자본(내 돈)을 알려주시면 손익분기·부족 자금·버틸 기간을 계산해 드려요.")]
    assert score(cases, traces).finance_answer_rate == 0.0


def test_자기자본이_충분하면_충당돼요_문구도_계산_성공으로_친다():
    cases = [_case("F1", category="market_finance", prompt="성수동 카페 자기자본 1억 월세 300")]
    traces = [_trace("F1", answer_text="…손익분기 월매출은 434만원이에요. 자기자본으로 개업 비용과 3개월 운전자금이 충당돼요.")]
    assert score(cases, traces).finance_answer_rate == 1.0


def test_코드가_쓴_상권_리포트의_수치는_환각_숫자로_세지_않는다():
    from chat.domain.services.compare import REPORT_HEADING
    from chat.domain.value_objects.eval_trace import LlmCall
    cases = [_case("C1")]
    trace = _trace("C1", answer_text=f"결론 문장.\n\n{REPORT_HEADING}성수** — 서울 1,064곳 중 246위",
                   calls=(LlmCall(phase="phase2", prompt="컨텍스트", response="{}", latency_ms=1.0),))
    assert not [v for v in score(cases, [trace]).violations if v.rule == "hallucinated_number"]
