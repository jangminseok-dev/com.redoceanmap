"""summarize_payload — 대화 목록의 domain/label 파생 규칙.

목록이 "작업 재개 지점"으로 읽히려면 행에 어느 워크스페이스의 무엇이었는지가 보여야 한다.
payload는 저장 시점 형태가 여럿(stock 카드·추천 목록·뉴스만·NULL)이라 파생이 조용히
열화하는지가 핵심이다 — 형태가 어긋나도 500이 아니라 None이어야 한다.
"""
from chat.domain.entities.conversation_entity import summarize_payload


def test_stock_카드는_심볼이_라벨이_된다():
    domain, label = summarize_payload({"stock": {"symbol": "005930.KS", "price": 74500}})
    assert (domain, label) == ("stock", "005930.KS")


def test_추천_1곳은_이름_그대로():
    payload = {"recommendations": [{"name": "성수동 카페거리"}]}
    assert summarize_payload(payload) == ("market", "성수동 카페거리")


def test_추천_여러_곳은_외_N곳으로_접는다():
    payload = {"recommendations": [{"name": "성수동 카페거리"}, {"name": "연남동"}, {"name": "망원동"}]}
    assert summarize_payload(payload) == ("market", "성수동 카페거리 외 2곳")


def test_stock과_recommendations가_함께_있으면_stock이_우선이다():
    payload = {"stock": {"symbol": "NVDA"}, "recommendations": [{"name": "성수동"}]}
    assert summarize_payload(payload) == ("stock", "NVDA")


def test_뉴스만_있는_payload는_None으로_열화():
    assert summarize_payload({"news": [{"title": "기사"}]}) == (None, None)


def test_NULL_payload는_None():
    assert summarize_payload(None) == (None, None)


def test_형태가_어긋난_payload도_500이_아니라_None():
    # 구버전·부분 저장 — stock이 dict가 아니거나 추천 항목에 name이 없다
    assert summarize_payload({"stock": "NVDA"}) == (None, None)
    assert summarize_payload({"recommendations": [{}]}) == (None, None)
    assert summarize_payload({"recommendations": ["성수동"]}) == (None, None)
