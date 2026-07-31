"""입지 진단 문구 — 왜 이 점수가 나왔는지 숫자로 말한다 (game-strategy §4-6).

**템플릿 룩업이다. LLM을 쓰지 않는다** — 결정론 위반이고 추론 비용이 든다(game-harness §2).
같은 상권·업종이면 언제 물어도 같은 문장이 나온다.

문장에 쓰는 숫자는 전부 실데이터에서 온 것이다. 게임 규칙으로 만든 값(임대료 등)은 여기
들어오지 않는다 — 그건 `assumed_*` 접두사를 달고 따로 나간다(§5-1).
"""
from __future__ import annotations

from dataclasses import dataclass

_AGE_LABELS = ("10대", "20대", "30대", "40대", "50대", "60대 이상")
_HOUR_LABELS = ("00-06시", "06-11시", "11-14시", "14-17시", "17-21시", "21-24시")


@dataclass(frozen=True)
class Diagnosis:
    tone: str  # good | warn | bad
    message: str


def josa(word: str, with_final: str, without_final: str) -> str:
    """받침 유무로 조사를 고른다.

    업종명이 100종이라 "커피-음료이"처럼 어색해지는 자리가 생긴다. 한글 음절은
    `(코드 - 0xAC00) % 28`이 0이면 받침이 없다.
    """
    if not word:
        return without_final
    last = word[-1]
    if not ("가" <= last <= "힣"):
        return without_final  # 영문·숫자·기호로 끝나면 받침 없는 쪽으로 읽는다
    return with_final if (ord(last) - 0xAC00) % 28 else without_final


def _peak(shares: tuple[float, ...], labels: tuple[str, ...]) -> tuple[str, float]:
    if not shares or max(shares) <= 0:
        return ("자료 없음", 0.0)
    index = max(range(len(shares)), key=lambda i: shares[i])
    return (labels[index], shares[index])


def diagnose(
    *,
    service_name: str,
    industry_age_share: tuple[float, ...],
    floating_age_share: tuple[float, ...],
    industry_hour_share: tuple[float, ...],
    floating_hour_share: tuple[float, ...],
    saturation_percentile: float,
    closure_rate_percentile: float,
    similar_store_count: int,
    operating_months_avg: float,
    has_sales: bool,
    has_store: bool,
) -> tuple[Diagnosis, ...]:
    """진단 문장 목록. 나쁜 신호를 앞에 둔다."""
    out: list[Diagnosis] = []

    if not has_sales:
        out.append(
            Diagnosis("warn", f"이 상권에는 {service_name} 업종의 매출 기록이 없습니다. "
                              "아무도 하지 않았거나, 통계에 잡힐 만큼 크지 않았습니다.")
        )

    # 수요 정합 — 업종이 팔리는 나이와 거리에 있는 나이
    industry_age, industry_ratio = _peak(industry_age_share, _AGE_LABELS)
    floating_age, floating_ratio = _peak(floating_age_share, _AGE_LABELS)
    if industry_ratio > 0 and floating_ratio > 0:
        if industry_age == floating_age:
            out.append(
                Diagnosis(
                    "good",
                    f"{service_name} 매출의 {industry_ratio:.0%}가 {industry_age}에서 나오고, "
                    f"이 상권 유동인구도 {floating_age}가 가장 많습니다.",
                )
            )
        else:
            out.append(
                Diagnosis(
                    "bad",
                    f"{service_name} 매출의 {industry_ratio:.0%}는 {industry_age}에서 나오는데, "
                    f"이 상권 유동인구는 {floating_age}({floating_ratio:.0%})가 가장 많습니다.",
                )
            )

    # 시간대 정합
    industry_hour, industry_hour_ratio = _peak(industry_hour_share, _HOUR_LABELS)
    if industry_hour_ratio > 0 and floating_hour_share:
        index = _HOUR_LABELS.index(industry_hour) if industry_hour in _HOUR_LABELS else -1
        area_at_peak = floating_hour_share[index] if index >= 0 else 0.0
        if area_at_peak > 0 and area_at_peak < 0.12:
            out.append(
                Diagnosis(
                    "bad",
                    f"{service_name}{josa(service_name, '이', '가')} 가장 많이 팔리는 "
                    f"{industry_hour}에 이 상권 유동인구의 {area_at_peak:.0%}만 지나갑니다.",
                )
            )
        elif area_at_peak >= 0.20:
            out.append(
                Diagnosis(
                    "good",
                    f"{service_name}의 성수 시간대({industry_hour})에 "
                    f"이 상권 유동인구의 {area_at_peak:.0%}가 몰립니다.",
                )
            )

    # 포화
    if has_store and saturation_percentile >= 0.9:
        out.append(
            Diagnosis(
                "bad",
                f"같은 업종 {similar_store_count}곳 — 유동인구 대비 경쟁 밀도가 "
                f"서울 상위 {(1 - saturation_percentile):.0%} 안에 듭니다.",
            )
        )
    elif has_store and saturation_percentile <= 0.3:
        out.append(
            Diagnosis(
                "good",
                f"같은 업종이 {similar_store_count}곳뿐이라 유동인구 대비 경쟁이 여유롭습니다.",
            )
        )

    # 생존
    if has_store and closure_rate_percentile >= 0.9:
        out.append(
            Diagnosis(
                "bad",
                f"이 상권·업종 조합의 폐업률이 서울 상위 {(1 - closure_rate_percentile):.0%}입니다.",
            )
        )
    if operating_months_avg > 0:
        years = operating_months_avg / 12
        tone = "good" if years >= 8 else "warn" if years >= 5 else "bad"
        out.append(
            Diagnosis(
                tone,
                f"이 상권 점포의 평균 영업 기간은 {years:.1f}년입니다.",
            )
        )

    order = {"bad": 0, "warn": 1, "good": 2}
    return tuple(sorted(out, key=lambda d: order[d.tone]))
