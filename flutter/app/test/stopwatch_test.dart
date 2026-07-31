import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app/stopwatch_page.dart';

void main() {
  test('분:초.1/100초 형식으로 만든다', () {
    expect(formatLapTime(Duration.zero), '00:00.00');
    expect(
      formatLapTime(const Duration(minutes: 1, seconds: 9, milliseconds: 440)),
      '01:09.44',
    );
    // 1/100초 아래는 버린다
    expect(formatLapTime(const Duration(milliseconds: 4119)), '00:04.11');
    expect(formatLapTime(const Duration(minutes: 62)), '62:00.00');
  });

  testWidgets('시작 전에는 랩/재설정 버튼이 눌리지 않는다', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: StopwatchPage()));

    expect(find.text('00:00.00'), findsOneWidget);
    expect(find.text('시작'), findsOneWidget);

    final resetButton = tester.widget<TextButton>(
      find.ancestor(of: find.text('재설정'), matching: find.byType(TextButton)),
    );
    expect(resetButton.onPressed, isNull);
  });

  testWidgets('시작하면 버튼이 중단·랩으로 바뀌고, 랩을 기록한다', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: StopwatchPage()));

    await tester.tap(find.text('시작'));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('중단'), findsOneWidget);
    expect(find.text('랩'), findsOneWidget);
    // 진행 중인 랩 한 줄이 목록에 보인다
    expect(find.text('랩 1'), findsOneWidget);

    await tester.tap(find.text('랩'));
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('랩 2'), findsOneWidget);

    // 타이머를 남긴 채 테스트가 끝나지 않도록 정지시킨다
    await tester.tap(find.text('중단'));
    await tester.pump();
  });
}
