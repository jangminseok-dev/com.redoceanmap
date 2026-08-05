"""매물대(가격대별 거래량 분포) — www/lib/volumeProfile.ts의 백엔드 판.

차트(stock CandleChart · game GameChart)가 화면에서 계산하던 것을 서술에도 쓰려고
같은 알고리즘을 옮겼다. **두 곳이 같은 수치를 말해야 한다** — 사용자가 차트에서 본
밀집 구간과 챗이 말하는 구간이 다르면 둘 다 못 믿는다. 그래서 구간 수(24)와
대표가((고+저+종)/3) 근사를 그대로 유지한다.

봉 내부의 체결 분포는 알 수 없으므로 대표가 한 점에 거래량을 놓는다. 고저 범위를
여러 칸에 배분하는 쪽이 정밀해 보이지만 "봉 안에서 균등 거래됐다"는 근거 없는 가정이
하나 더 들어갈 뿐이다(프론트 주석의 판단을 그대로 승계).

**지지/저항을 판정하지 않는다.** 이건 "과거에 어느 가격대에서 많이 거래됐나"라는
팩트일 뿐이고, 그 가격이 앞으로 지지선 역할을 한다는 주장은 검증된 바 없다.
화면 문구도 "거래 밀집 구간"으로 통일돼 있다 — 소비자(chat)도 같은 말을 쓴다.

외부 의존 없는 순수 함수다(도메인 순수성 계약).
"""
from __future__ import annotations

from dataclasses import dataclass

# 차트 페인 기준으로 정한 구간 수 — 프론트 VOLUME_PROFILE_BINS와 같은 값이어야 한다
VOLUME_PROFILE_BINS = 24

# 표본이 이보다 적으면 분포가 아니라 노이즈다 (프론트 MIN_BARS와 동일)
MIN_BARS = 5


@dataclass(frozen=True)
class VolumeProfileSummary:
    """서술에 필요한 만큼만 요약한 매물대.

    24구간 전체를 나르지 않는 이유: 챗 답변에 필요한 건 "어디에 몰려 있고 지금 그
    위인가 아래인가"이고, 구간 배열을 통째로 주면 모델이 숫자를 골라 인용하다 환각이
    는다(허브 계약도 이 요약만 싣는다).
    """

    poc_low: float       # 최다 거래 구간(POC)의 하단 가격
    poc_high: float      # 최다 거래 구간의 상단 가격
    poc_share: float     # 그 구간이 전체 거래량에서 차지하는 비율 (0~1)
    price_position: str  # 현재가와 POC의 관계: above | inside | below
    bars: int            # 산출에 쓴 봉 수


def compute_volume_profile(
    bars: list, price: float, bin_count: int = VOLUME_PROFILE_BINS
) -> VolumeProfileSummary | None:
    """일봉 목록 → 매물대 요약. 표본 부족·가격 범위 없음·거래량 0이면 None.

    bars는 high/low/close/volume 속성을 가진 객체(도메인 PriceBar)면 된다.
    None은 "산출 불가"이고 소비자가 라인을 생략한다(열화 동작).
    """
    if len(bars) < MIN_BARS:
        return None

    low = min(b.low for b in bars)
    high = max(b.high for b in bars)
    if not high > low:
        return None  # 가격이 한 점에 붙어 있으면 분포가 성립하지 않는다

    size = (high - low) / bin_count
    volumes = [0.0] * bin_count
    for b in bars:
        typical = (b.high + b.low + b.close) / 3
        idx = min(bin_count - 1, max(0, int((typical - low) / size)))
        volumes[idx] += b.volume

    total = sum(volumes)
    if total <= 0:
        return None

    poc = max(range(bin_count), key=lambda i: volumes[i])
    poc_low = low + poc * size
    poc_high = poc_low + size
    if price < poc_low:
        position = "below"
    elif price > poc_high:
        position = "above"
    else:
        position = "inside"
    return VolumeProfileSummary(
        poc_low=poc_low,
        poc_high=poc_high,
        poc_share=volumes[poc] / total,
        price_position=position,
        bars=len(bars),
    )
