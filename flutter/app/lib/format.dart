// 표시용 포맷 — www의 같은 이름 헬퍼와 기준을 맞춘다.

/// 분기 코드(20254) → "2025년 4분기"
String formatQuarter(int yearQuarter) =>
    '${yearQuarter ~/ 10}년 ${yearQuarter % 10}분기';

/// 원 단위 정수 → "19.6억"
String formatEok(int won) => '${(won / 100000000).toStringAsFixed(1)}억';

/// 1650 → "1,650" (www의 toLocaleString과 같은 자리)
String formatCount(int n) => n.toString().replaceAllMapped(
      RegExp(r'(\d)(?=(\d{3})+$)'),
      (m) => '${m[1]},',
    );

/// www의 getGreeting과 같은 기준
String greetingFor(int hour) {
  if (hour < 12) return '좋은 아침이에요';
  if (hour < 18) return '오후예요';
  return '오늘 하루 어땠어요';
}
