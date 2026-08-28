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
