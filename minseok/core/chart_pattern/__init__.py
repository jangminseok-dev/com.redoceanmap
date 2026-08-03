"""차트 패턴 탐지 — 앱 무관 순수 알고리즘.

게임(가상 주가)과 stock(실데이터)이 같은 규칙으로 형태를 읽어야 해서 여기 둔다.
스포크끼리는 직접 import할 수 없고(`.importlinter` 계약 2), 허브는 앱 간 협력 계약을
소유하는 곳인데 이 모듈에는 제공자-소비자 관계가 없다 — 입력이 숫자 배열뿐이다.

pydantic·프레임워크에 의존하지 않는다(도메인 순수성 계약).
"""
from core.chart_pattern.detector import DetectedPattern, detect
from core.chart_pattern.pivots import Pivot, find_pivots

__all__ = ["DetectedPattern", "Pivot", "detect", "find_pivots"]
