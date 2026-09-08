"""답변 후처리 가드 — 채점기(eval_scorer)와 같은 판정을 코드가 보장하는지 고정."""
from chat.domain.services import answer_guard as g


def test_배정된_번호만_남기고_유령_인용은_지운다():
    context = "[삼성전자 분석 데이터] — 근거 [1]\n- 근거 [2] 과거 통계: ...\n  - 근거 [5] (…) 기사"
    assert g.allowed_citations(context) == {1, 2, 5}

    answer = "RSI가 낮습니다 [1]. 거래량은 평소 대비 낮습니다 [3]. 관련 기사가 있습니다 [5]."
    out = g.strip_dangling_citations(answer, {1, 2, 5})
    assert "[1]" in out and "[5]" in out
    assert "[3]" not in out
    assert "낮습니다." in out          # 문장은 남는다 — 마커만 걷어낸다
    assert "  " not in out             # 마커 자리의 이중 공백 정리


def test_결번은_실제로_생긴다():
    # R4 설계 — 블록이 생략되면 번호가 비고, 모델이 그 번호를 쓰면 유령 인용이다
    context = "[분석] — 근거 [1]\n- 근거 [4] 뉴스 감성: +0.2"
    assert g.allowed_citations(context) == {1, 4}
    assert g.strip_dangling_citations("A [2] B [4]", {1, 4}) == "A B [4]"


def test_책임_고지가_없으면_붙이고_있으면_두_번_붙이지_않는다():
    plain = "지표는 중립입니다."
    once = g.ensure_disclaimer(plain)
    assert once.endswith(g.DISCLAIMER)
    assert g.ensure_disclaimer(once) == once   # 멱등

    # 모델이 제 문장으로 고지했으면 그대로 둔다(채점기와 같은 판정: 꼬리 150자 · 주제어+책임어)
    own = "지표는 중립입니다. 투자 판단은 신중히 하시기 바랍니다."
    assert g.ensure_disclaimer(own) == own


def test_고지가_꼬리를_벗어나면_다시_붙인다():
    # 앞머리에만 있고 뒤가 긴 답변은 채점기가 위반으로 본다 — 가드도 같은 기준
    long_body = "투자는 본인 책임입니다. " + ("지표 설명 문장입니다. " * 20)
    assert g.ensure_disclaimer(long_body).endswith(g.DISCLAIMER)


def test_배열이_서_있으면_거래량_판정을_보장한다():
    # 급증(1.5배 이상)이면 신뢰
    out = g.ensure_volume_verdict("정배열입니다.", ma20=97.0, ma50=93.0, volume_ratio=1.8)
    assert "거래량" in out and "신뢰" in out

    # 평소·한산이면 의심 — 거래량이 추세를 확인해주지 못한다
    out = g.ensure_volume_verdict("정배열입니다.", ma20=97.0, ma50=93.0, volume_ratio=1.0)
    assert "거래량" in out and "의심" in out

    # 역배열도 추세다 — 배열이 서 있으면 방향과 무관하게 판정한다
    out = g.ensure_volume_verdict("역배열입니다.", ma20=93.0, ma50=97.0, volume_ratio=2.0)
    assert "신뢰" in out


def test_모델이_이미_판정했으면_덧붙이지_않는다():
    own = "거래량이 늘어 추세를 신뢰할 만합니다."
    assert g.ensure_volume_verdict(own, ma20=93.0, ma50=97.0, volume_ratio=0.5) == own


def test_배열이_붙어_있으면_판정을_생략한다():
    # STOCK_ANSWER_PROMPT 2번 규칙 — "추세가 뚜렷하지 않으면 판정 생략".
    # 판정 기준은 **MA 배열**이지 방향 라벨이 아니다(첫 구현이 direction을 봤다가
    # 골든셋에서 한 번도 발화하지 않았다 — 스텁이 전 케이스를 NEUTRAL로 고정한다).
    plain = "지표가 서로 상쇄됐습니다."
    assert g.ensure_volume_verdict(plain, ma20=100.0, ma50=100.2, volume_ratio=0.4) == plain


def test_주의_등급_추천_어휘를_중립으로_되돌린다():
    src = "성수역을 강력히 추천합니다. 유동인구 성장률이 높습니다."
    out = g.suppress_recommendation(src)
    # eval_scorer grade_caution과 같은 어휘가 남지 않는다
    assert "추천" not in out and "강력히" not in out
    assert "성수역을 검토해볼 만합니다." in out
    assert "유동인구 성장률이 높습니다." in out  # 수치 서술 문장은 지우지 않는다


def test_추천_활용형과_명사형도_치환된다():
    assert "검토해 보시길 바랍니다" in g.suppress_recommendation("추천드립니다")
    assert g.suppress_recommendation("추천 상권입니다") == "검토 상권입니다"
    assert "적극적으로" not in g.suppress_recommendation("적극적으로 추천해요")


def test_등급_고지_문장():
    line = g.grade_caution_notice("성수역", "주의", 44.9)
    assert line.startswith("※ 성수역 상권은 상권 전체 건강 점수 44.9점 '주의' 등급")
    assert "서울 평균(50점)에 못 미칩니다" in line


def test_데이터_없는_지표명이_든_문장만_걷어낸다():
    # 2026-08-31 실측 m1: 폐업률 '데이터 없음'인데 영업 기간을 폐업률로 재라벨
    src = "유동인구가 많습니다. 유의할 점: 높은 폐업률(평균 49개월 내 폐업)이 있어요."
    out = g.strip_unsupported_metric(src, "폐업률")
    assert out == "유동인구가 많습니다."


def test_지표명이_없으면_그대로_둔다():
    src = "유동인구가 많습니다. 유의할 점: 경쟁 밀집."
    assert g.strip_unsupported_metric(src, "폐업률") == src


def test_먼_매물대를_근처라_부르면_실제_위치로_교체한다():
    # 2026-08-31 실측 q09: 현재가 227.97, 매물대 180.10~186.34(23% 아래)를 "근처"로 서술
    answer = "과거 거래량 밀집 구간(180.10~186.34달러) 근처에 있습니다. 지지선 근처도 보세요."
    out = g.enforce_distance_claim(
        answer, price=227.97, band_low=180.10, band_high=186.34,
        atr_value=227.97 * 0.064,  # ATR 6.4% — 거리 41.6 > 2×ATR 29.2
    )
    assert "(현재가보다 18% 아래)에 있습니다" in out
    assert "지지선 근처" in out  # 매물대 문장이 아니면 손대지 않는다


def test_구간_안이거나_ATR_2배_이내면_근처를_허용한다():
    answer = "매물대 근처입니다."
    assert g.enforce_distance_claim(
        answer, price=183.0, band_low=180.0, band_high=186.0, atr_value=5.0,
    ) == answer  # 구간 안
    assert g.enforce_distance_claim(
        answer, price=190.0, band_low=180.0, band_high=186.0, atr_value=5.0,
    ) == answer  # 거리 4 ≤ 2×ATR 10


def test_질문에_없는_전문용어에_괄호_풀이를_붙인다():
    out = g.attach_glossary("수급 유출 우위이고 모멘텀도 약합니다. 수급 개선 필요.", "애플 어때?")
    assert out.startswith("수급(사자·팔자 자금의 흐름) 유출 우위")
    assert "모멘텀(최근 1년 주가 흐름의 힘)" in out
    assert out.count("수급(") == 1  # 첫 등장에만


def test_질문자가_쓴_용어와_이미_괄호가_붙은_용어는_건드리지_않는다():
    src = "수급이 약합니다."
    assert g.attach_glossary(src, "삼성전자 수급 어때?") == src  # 질문자가 아는 용어
    src2 = "ATR(14) 기준 변동성이 큽니다."
    assert g.attach_glossary(src2, "애플 어때?") == src2  # 기존 괄호 설명 유지


def test_중립_RSI의_과매수_서술은_중립_구간으로_교정된다():
    # 4차 실측 S2 t3: RSI 40.3을 "과매수 영역"으로 서술
    out = g.enforce_overheat_claim(
        "현재 주가는 과매수 영역에 위치하고 있으며 (RSI 40.3) 주의가 필요합니다.",
        rsi=40.3, bb_percent_b=0.5,
    )
    assert "과매수" not in out
    assert "중립 구간" in out


def test_과매도_원값이면_과매수_서술을_과매도로_뒤집는다():
    out = g.enforce_overheat_claim("과매수 구간입니다.", rsi=25.0, bb_percent_b=0.5)
    assert out == "과매도 구간입니다."
    same = g.enforce_overheat_claim("과매도 상태입니다.", rsi=25.0, bb_percent_b=0.5)
    assert same == "과매도 상태입니다."  # 원값과 일치하는 서술은 무손상


def test_볼린저_상단_돌파면_과매수_서술을_허용한다():
    text = "과매수 구간에 진입했습니다."
    assert g.enforce_overheat_claim(text, rsi=55.0, bb_percent_b=1.05) == text


def test_긍정_감성을_악재로_반전한_문장을_교정한다():
    # 4차 실측 S2 t3: 평균 감성 +0.30을 "주로 악재 관련 기사 다수"로 서술
    out = g.enforce_sentiment_claim(
        "뉴스 감성 지표가 부정적입니다 (평균 감성 +0.30, 악재 기사 다수). 거래량은 적습니다.",
        sentiment=0.30,
    )
    assert "긍정적입니다" in out and "호재 기사" in out
    assert "거래량은 적습니다" in out  # 감성 무관 문장은 무손상


def test_감성_모호_구간은_교정하지_않는다():
    text = "뉴스 감성이 부정적입니다."
    assert g.enforce_sentiment_claim(text, sentiment=0.05) == text


def test_volume_verdict_cell_추세가_서면_신뢰_의심_아니면_배수만():
    assert g.volume_verdict_cell(ma20=97.0, ma50=93.0, volume_ratio=1.8) == "1.8배 · 신뢰"
    assert g.volume_verdict_cell(ma20=97.0, ma50=93.0, volume_ratio=0.9) == "0.9배 · 의심"
    assert g.volume_verdict_cell(ma20=100.0, ma50=100.0, volume_ratio=2.0) == "2.0배(추세 불명확)"


def test_strip_forecast_claims_전망_문장만_지우고_사실_문장은_남긴다():
    text = ("수서역 상권은 점포당 월평균 6,181만원의 매출을 보입니다. 이는 3천만원 초기 자본으로도 빠르게 회수가 가능함을 시사합니다.\n"
            "유의할 점: 유동인구의 주요 연령대가 60대 이상입니다. 빠른 매출 성장이 예상됩니다.")
    out = g.strip_forecast_claims(text)
    assert "6,181만원" in out and "60대 이상" in out
    assert "회수" not in out and "성장이 예상" not in out
    assert g.strip_forecast_claims("전망 문구 없는 문장.") == "전망 문구 없는 문장."


def test_normalize_citation_markers_괄호_번호를_대괄호_마커로_되돌린다():
    text = "12-1 모멘텀이 -8.5%로 하락 추세를 나타내고 있어 (1), 뉴스 감성(-0.40)으로 신뢰도가 떨어집니다(4). 2024년(3)에는"
    out = g.normalize_citation_markers(text, {1, 4})
    assert "[1]" in out and "[4]" in out
    assert "(3)" in out and "(-0.40)" in out   # 배정 밖 번호·음수는 그대로
    assert g.normalize_citation_markers(text, set()) == text


def test_ensure_disclaimer_자리표시자_고지는_걷어내고_실제_고지를_붙인다():
    text = "**투자 판단 고지:** 제공된 정보는 참고용입니다. [투자 판단 책임 고지]"
    out = g.ensure_disclaimer(text)
    assert "[투자 판단 책임 고지]" not in out
    assert out.rstrip()[-1] in ".!?…" and "본인" in out[-80:]

