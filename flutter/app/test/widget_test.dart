// 네트워크를 타지 않는 순수 함수와 JSON 파싱만 검증한다.

import 'package:flutter_test/flutter_test.dart';

import 'package:app/api.dart';
import 'package:app/format.dart';

void main() {
  test('분기 코드를 사람이 읽는 형태로 바꾼다', () {
    expect(formatQuarter(20254), '2025년 4분기');
    expect(formatQuarter(20211), '2021년 1분기');
  });

  test('원 단위 금액을 억 단위로 줄인다', () {
    expect(formatEok(1957919616), '19.6억');
    expect(formatEok(100000000), '1.0억');
  });

  test('천 단위로 쉼표를 넣는다', () {
    expect(formatCount(1650), '1,650');
    expect(formatCount(67), '67');
    expect(formatCount(1234567), '1,234,567');
  });

  test('www와 같은 기준으로 시간대 인사를 고른다', () {
    expect(greetingFor(9), '좋은 아침이에요');
    expect(greetingFor(13), '오후예요');
    expect(greetingFor(20), '오늘 하루 어땠어요');
  });

  test('showcase 응답을 백엔드 필드명 그대로 파싱한다', () {
    final showcase = Showcase.fromJson({
      'yearQuarter': 20254,
      'quarterFrom': 20211,
      'areaCount': 1650,
      'rows': [
        {
          'trdarCode': 3130093,
          'trdarName': '동서시장',
          'districtName': '동대문구',
          'divisionName': '전통시장',
          'salesPerStore': 1957919616,
          'storeCount': 67,
        },
      ],
    });

    expect(showcase.yearQuarter, 20254);
    expect(showcase.quarterFrom, 20211);
    expect(showcase.areaCount, 1650);
    expect(showcase.rows.single.trdarName, '동서시장');
    expect(showcase.rows.single.storeCount, 67);
  });

  test('chat 응답을 파싱한다', () {
    final answer = ChatAnswer.fromJson({'sessionId': 12, 'answer': '성수동은…'});
    expect(answer.sessionId, 12);
    expect(answer.answer, '성수동은…');
  });

  test('401은 로그인이 필요한 오류로 구분한다', () {
    const unauthorized = ApiException(401, '인증이 필요합니다.');
    const serverError = ApiException(500, '서버 오류');
    expect(unauthorized.needsLogin, isTrue);
    expect(serverError.needsLogin, isFalse);
  });
}
