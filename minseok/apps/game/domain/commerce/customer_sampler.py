"""손님 NPC 생성 — 상권 실데이터 분포에서 뽑는다 (game-strategy §4-3).

**N명의 객체를 만들지 않는다.** 하루 방문이 1,000건이어도 화면에 보이는 건 몇 명뿐이라,
표본 K명만 생성하고 나머지는 집계로 둔다. 1,000개 객체 생성은 응답 지연이고 화면에
나타나지도 않는다.

각 손님은 (요일, 시간대, 성별, 연령) 4축이며, 실데이터 비중의 누적분포에 결정론 난수를
넣어 **역변환 샘플링**한다. 같은 (에포크, 가게, 날짜)면 언제 물어도 같은 손님이 나온다.

⚠️ **축 독립을 가정한다.** 매출 테이블에 성별×연령 교차가 없다(`resident`·`working` 인구에만
있다). 이건 실측이 아니라 가정이므로 `assumed` 표기 대상이다(game-harness §5-1).
"""
from __future__ import annotations

from dataclasses import dataclass

from game.domain.rng.deterministic import uniform

SAMPLE_SIZE = 40  # 화면에 보여줄 표본 수

WEEKDAY_LABELS = ("월", "화", "수", "목", "금", "토", "일")
HOUR_LABELS = ("00-06시", "06-11시", "11-14시", "14-17시", "17-21시", "21-24시")
GENDER_LABELS = ("남성", "여성")
AGE_LABELS = ("10대", "20대", "30대", "40대", "50대", "60대 이상")

# 손님 취향 태그 — 아이러브커피의 "단골 취향 룩업"을 탭 노가다 없이 옮긴 것(§4-3).
# 유저는 개별 손님을 접대하지 않는다. 손님 분포에 가게 설정을 맞춘다.
TASTE_LABELS = ("아침 테이크아웃", "장시간 체류", "단체 방문", "가성비 추구")


@dataclass(frozen=True)
class Customer:
    hour: str
    gender: str
    age: str
    taste: str


def pick(shares: tuple[float, ...], labels: tuple[str, ...], roll: float) -> str:
    """누적분포 역변환. 분포가 비어 있으면 첫 라벨(자료 없음을 균등분포로 위장하지 않는다)."""
    total = sum(shares)
    if total <= 0:
        return labels[0]
    threshold = roll * total
    cumulative = 0.0
    for share, label in zip(shares, labels):
        cumulative += share
        if threshold < cumulative:
            return label
    return labels[-1]


def sample_customers(
    *,
    store_id: int,
    game_day: int,
    hour_share: tuple[float, ...],
    gender_share: tuple[float, ...],
    age_share: tuple[float, ...],
    count: int = SAMPLE_SIZE,
) -> tuple[Customer, ...]:
    """그날 가게에 온 손님 표본.

    분포는 **그 상권·업종의 실데이터**에서 온다 — 상권마다 오는 사람이 다르다는 것이
    이 게임의 전제다.
    """
    customers = []
    for index in range(count):
        key = f"{store_id}|{game_day}|{index}"
        customers.append(
            Customer(
                hour=pick(hour_share, HOUR_LABELS, uniform("cust-hour", key)),
                gender=pick(gender_share, GENDER_LABELS, uniform("cust-gender", key)),
                age=pick(age_share, AGE_LABELS, uniform("cust-age", key)),
                taste=pick(
                    (0.3, 0.3, 0.2, 0.2), TASTE_LABELS, uniform("cust-taste", key)
                ),
            )
        )
    return tuple(customers)


def summarize(customers: tuple[Customer, ...], key: str) -> tuple[tuple[str, int], ...]:
    """표본을 축별로 집계 — 많은 순. 화면이 "누가 오는가"를 한 줄로 말할 재료다."""
    counts: dict[str, int] = {}
    for customer in customers:
        value = getattr(customer, key)
        counts[value] = counts.get(value, 0) + 1
    return tuple(sorted(counts.items(), key=lambda kv: -kv[1]))
