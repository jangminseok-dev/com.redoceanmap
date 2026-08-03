import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:app/admin_image_gateway.dart';
import 'package:app/api.dart';
import 'package:app/auth.dart';

const _created = {
  'key': 'admin/images/2026/08/abc123.jpg',
  'url': 'https://bucket.s3.ap-northeast-2.amazonaws.com/admin/images/2026/08/abc123.jpg?sig=x',
  'urlExpiresIn': 900,
  'bucket': 'redocean-admin-images',
  'contentType': 'image/jpeg',
  'sizeBytes': 3,
};

void main() {
  setUp(() {
    // 세션 복구는 보안 저장소(플랫폼 채널)를 타므로 단위 테스트에서는 토큰을 직접 심는다.
    Session.instance.accessToken = 'test-access-token';
  });

  test('파트 이름 file · Bearer 헤더로 보내고 201을 파싱한다', () async {
    late http.Request captured;
    final gateway = AdminImageGateway(
      client: MockClient((request) async {
        captured = request;
        return http.Response(jsonEncode(_created), 201, headers: {
          'content-type': 'application/json; charset=utf-8',
        });
      }),
    );

    final result = await gateway.upload(
      bytes: [0xFF, 0xD8, 0xFF],
      filename: 'shop.jpg',
    );

    expect(captured.method, 'POST');
    expect(captured.url.path, '/admin/images');
    expect(captured.headers['Authorization'], 'Bearer test-access-token');
    // 본문에는 JPEG 바이트가 섞여 있어 utf8로 못 읽는다 — latin1로 훑는다.
    expect(latin1.decode(captured.bodyBytes), contains('name="file"'));
    expect(latin1.decode(captured.bodyBytes), contains('filename="shop.jpg"'));
    expect(result.key, 'admin/images/2026/08/abc123.jpg');
    expect(result.contentType, 'image/jpeg');
    expect(result.urlExpiresIn, 900);
  });

  test('거절은 서버의 한국어 detail을 그대로 던진다', () async {
    final gateway = AdminImageGateway(
      client: MockClient((_) async => http.Response(
            jsonEncode({'detail': '이미지 파일이 아닙니다(허용: image/gif, image/jpeg, image/png, image/webp).'}),
            400,
            headers: {'content-type': 'application/json; charset=utf-8'},
          )),
    );

    await expectLater(
      gateway.upload(bytes: [0x25, 0x50], filename: 'doc.pdf'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.status, 'status', 400)
            .having((e) => e.message, 'message', contains('이미지 파일이 아닙니다')),
      ),
    );
  });

  test('권한 없는 계정의 403은 재시도하지 않고 그대로 올린다', () async {
    var calls = 0;
    final gateway = AdminImageGateway(
      client: MockClient((_) async {
        calls++;
        return http.Response(
          jsonEncode({'detail': '권한이 없습니다.'}),
          403,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }),
    );

    await expectLater(
      gateway.upload(bytes: [0xFF, 0xD8, 0xFF], filename: 'shop.jpg'),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 403)),
    );
    expect(calls, 1);
  });
}
