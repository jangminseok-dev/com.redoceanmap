from market.domain.services import rent_matcher as rm


def test_상권명_어간으로_R_ONE_상권을_찾는다():
    assert rm.match_area("홍대입구역") == "홍대/합정"
    assert rm.match_area("성수동카페거리") == "뚝섬"
    assert rm.match_area("대학로") == "혜화동"
    assert rm.match_area("강남역") == "강남대로"
    assert rm.match_area("역삼역") == "테헤란로"


def test_긴_별칭이_먼저_이겨_잠실새내가_잠실로_빠지지_않는다():
    assert rm.match_area("잠실새내역") == "잠실새내역"
    assert rm.match_area("잠실역") == "잠실/송파"


def test_모르는_상권은_None():
    assert rm.match_area("길음시장") is None


def test_자치구는_권역으로_떨어지고_모르면_기타():
    assert rm.zone_for("종로구") == "도심" and rm.zone_for("중구") == "도심"
    assert rm.zone_for("강남구") == "강남" and rm.zone_for("서초구") == "강남"
    assert rm.zone_for("마포구") == "영등포신촌"
    assert rm.zone_for("성동구") == "기타" and rm.zone_for("") == "기타"


def test_별칭_사전은_R_ONE_상권_59개를_전부_덮는다():
    assert len(rm.RONE_AREA_ALIASES) == 59


def test_자치구가_다르면_어간이_걸려도_매칭하지_않는다():
    assert rm.match_area("삼육보건대학교", "동대문구") is None
    assert rm.match_area("영동교골목시장", "광진구") is None
    assert rm.match_area("국회의사당역", "영등포구") is None
    assert rm.match_area("면목동우체국", "중랑구") is None
    assert rm.match_area("상도약수골목형상점가", "동작구") is None
    assert rm.match_area("성수대교남단", "강남구") is None
    assert rm.match_area("동대문구청", "동대문구") is None


def test_자치구가_맞으면_매칭한다():
    assert rm.match_area("건대입구역 6번", "광진구") == "건대입구"
    assert rm.match_area("동대문역사문화공원역", "중구") == "동대문"
    assert rm.match_area("사당역 4번", "관악구") == "사당"
    assert rm.match_area("성수동카페거리", "성동구") == "뚝섬"


def test_자치구_사전은_R_ONE_상권_59개를_전부_덮는다():
    assert set(rm.RONE_AREA_DISTRICTS) == {area for area, _ in rm.RONE_AREA_ALIASES}
